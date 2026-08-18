import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.count_people import PeopleCounter
from src.server import VideoStreamWorker, create_app, write_daily_csv


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.mock_counter = PeopleCounter(
            model=MagicMock(),
            count_line=(10, 20, 30, 40),
            entering_direction="north_to_south",
        )
        self.worker = VideoStreamWorker(
            source="test.mp4",
            counter=self.mock_counter,
            jpeg_quality=75,
        )
        self.worker.width = 1280
        self.worker.height = 720
        self.app = create_app(self.worker)
        self.client = TestClient(self.app)

    def test_get_config(self):
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "test.mp4")
        self.assertEqual(data["line"], [10, 20, 30, 40])
        self.assertEqual(data["width"], 1280)
        self.assertEqual(data["height"], 720)

    def test_get_and_set_line(self):
        response = self.client.get("/api/line")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["line"], [10, 20, 30, 40])

        update_resp = self.client.post(
            "/api/line",
            json={"x1": 50, "y1": 60, "x2": 70, "y2": 80, "entering_direction": "north_to_south"},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["line"], [50, 60, 70, 80])
        self.assertEqual(self.mock_counter.count_line, (50, 60, 70, 80))

    def test_reset_counts(self):
        response = self.client.post("/api/reset")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_list_videos(self):
        response = self.client.get("/api/videos")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("videos", data)
        self.assertIsInstance(data["videos"], list)

    def test_change_source(self):
        response = self.client.post("/api/source", json={"source": "test1.mp4"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["source"], "test1.mp4")

    def test_upload_video(self):
        file_content = b"fake-video-bytes"
        response = self.client.post(
            "/api/upload",
            files={"file": ("sample.mp4", file_content, "video/mp4")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["filename"], "sample.mp4")

    def test_write_daily_csv(self):
        self.mock_counter.in_count = 12
        self.mock_counter.out_count = 3
        self.mock_counter.current_people = 9
        day = date(2026, 8, 18)
        with tempfile.TemporaryDirectory() as directory:
            path = write_daily_csv(self.worker, day, Path(directory))
            self.assertEqual(path.name, "2026-08-18.csv")
            self.assertEqual(
                path.read_text(),
                "date,in,out,current\n2026-08-18,12,3,9\n",
            )


if __name__ == "__main__":
    unittest.main()

