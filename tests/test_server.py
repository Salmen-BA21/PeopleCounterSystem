import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.count_people import PeopleCounter
from src.server import StreamManager, VideoStreamWorker, create_app, write_daily_csv


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.manager = StreamManager(
            model=MagicMock(),
            confidence=0.35,
            device="cpu",
            jpeg_quality=75,
        )
        self.manager.config_path = Path(tempfile.mkdtemp()) / "sources.json"
        worker = self.manager.add("test.mp4", "test.mp4")
        self.worker = worker
        self.app = create_app(self.manager)
        self.client = TestClient(self.app)

    def tearDown(self):
        for worker in self.manager.sources.values():
            worker.stop()

    def test_list_sources(self):
        response = self.client.get("/api/sources")
        self.assertEqual(response.status_code, 200)
        sources = response.json()["sources"]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], "test-mp4")
        self.assertEqual(sources[0]["source"], "test.mp4")

    def test_add_and_remove_source(self):
        response = self.client.post("/api/sources", json={"source": "test1.mp4", "name": "Second"})
        self.assertEqual(response.status_code, 200)
        source_id = response.json()["id"]
        self.assertEqual(source_id, "second")

        remove_resp = self.client.delete(f"/api/sources/{source_id}")
        self.assertEqual(remove_resp.status_code, 200)
        remaining = self.client.get("/api/sources").json()["sources"]
        self.assertEqual(len(remaining), 1)

    def test_add_source_rejects_empty(self):
        response = self.client.post("/api/sources", json={"source": "  "})
        self.assertEqual(response.status_code, 400)

    def test_set_line_per_source(self):
        response = self.client.post(
            "/api/sources/test-mp4/line",
            json={"x1": 50, "y1": 60, "x2": 70, "y2": 80, "entering_direction": "north_to_south"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["line"], [50, 60, 70, 80])
        self.assertEqual(self.worker.counter.count_line, (50, 60, 70, 80))

    def test_set_line_unknown_source(self):
        response = self.client.post(
            "/api/sources/nope/line",
            json={"x1": 0, "y1": 0, "x2": 1, "y2": 1},
        )
        self.assertEqual(response.status_code, 404)

    def test_reset_counts(self):
        self.worker.counter.in_count = 7
        response = self.client.post("/api/sources/test-mp4/reset")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(self.worker.counter.in_count, 0)

    def test_reset_unknown_source(self):
        response = self.client.post("/api/sources/nope/reset")
        self.assertEqual(response.status_code, 404)

    def test_list_videos(self):
        response = self.client.get("/api/videos")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("videos", data)
        self.assertIsInstance(data["videos"], list)

    def test_upload_video_adds_source(self):
        import src.server as srv
        from unittest.mock import patch

        with patch.object(srv, "UPLOADS_DIR", Path(tempfile.mkdtemp())):
            file_content = b"fake-video-bytes"
            response = self.client.post(
                "/api/upload",
                files={"file": ("sample.mp4", file_content, "video/mp4")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["filename"], "sample.mp4")
        self.assertIn("id", response.json()["source"])
        sources = self.client.get("/api/sources").json()["sources"]
        self.assertEqual(len(sources), 2)

    def test_upload_rejects_oversize(self):
        import src.server as srv
        from unittest.mock import patch

        baseline = len(self.client.get("/api/sources").json()["sources"])
        file_content = b"x" * 10
        with patch.object(srv, "MAX_UPLOAD_BYTES", 5):
            response = self.client.post(
                "/api/upload",
                files={"file": ("big.mp4", file_content, "video/mp4")},
            )
        self.assertEqual(response.status_code, 413)
        sources = self.client.get("/api/sources").json()["sources"]
        self.assertEqual(len(sources), baseline)

    def test_set_model_keeps_counts(self):
        self.worker.counter.in_count = 7
        response = self.client.post(
            "/api/sources/test-mp4/model",
            json={"model": "quick"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model"], "quick")
        self.assertEqual(self.worker.counter.in_count, 7)

    def test_set_model_unknown(self):
        response = self.client.post("/api/sources/test-mp4/model", json={"model": "nope"})
        self.assertEqual(response.status_code, 400)

    def test_pause_and_resume_source(self):
        response = self.client.post("/api/sources/test-mp4/running", json={"running": False})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.worker.paused)
        response = self.client.post("/api/sources/test-mp4/running", json={"running": True})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.worker.paused)
        missing = self.client.post("/api/sources/nope/running", json={"running": False})
        self.assertEqual(missing.status_code, 404)

    def test_write_daily_csv_per_source(self):
        self.worker.counter.in_count = 12
        self.worker.counter.out_count = 3
        self.worker.counter.current_people = 9
        day = date(2026, 8, 18)
        with tempfile.TemporaryDirectory() as directory:
            path = write_daily_csv(self.worker, day, Path(directory))
            self.assertEqual(path.name, "2026-08-18_test-mp4.csv")
            self.assertEqual(
                path.read_text(),
                "date,in,out,current\n2026-08-18,12,3,9\n",
            )

    def test_write_daily_csv_merges_existing(self):
        self.worker.counter.in_count = 12
        self.worker.counter.out_count = 3
        self.worker.counter.current_people = 9
        day = date(2026, 8, 18)
        with tempfile.TemporaryDirectory() as directory:
            path = write_daily_csv(self.worker, day, Path(directory))
            self.worker.counter.in_count = 5
            self.worker.counter.out_count = 1
            self.worker.counter.current_people = 4
            write_daily_csv(self.worker, day, Path(directory))
            self.assertEqual(
                path.read_text(),
                "date,in,out,current\n2026-08-18,17,4,4\n",
            )

    def test_list_reports(self):
        import src.server as srv
        from unittest.mock import patch

        with patch.object(srv, "REPORTS_DIR", Path(tempfile.mkdtemp())):
            write_daily_csv(self.worker, date(2026, 8, 18), srv.REPORTS_DIR)
            response = self.client.get("/api/reports")
            self.assertEqual(response.status_code, 200)
            reports = response.json()["reports"]
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0]["filename"], "2026-08-18_test-mp4.csv")
            self.assertEqual(reports[0]["date"], "2026-08-18")
            self.assertEqual(reports[0]["name"], "test.mp4")
            self.assertEqual(reports[0]["in"], 0)

    def test_download_report(self):
        import src.server as srv
        from unittest.mock import patch

        with patch.object(srv, "REPORTS_DIR", Path(tempfile.mkdtemp())):
            write_daily_csv(self.worker, date(2026, 8, 18), srv.REPORTS_DIR)
            response = self.client.get("/api/reports/2026-08-18_test-mp4.csv")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"2026-08-18", response.content)
            missing = self.client.get("/api/reports/nope.csv")
            self.assertEqual(missing.status_code, 404)

    def test_persistence_round_trip(self):
        self.manager.set_line("test-mp4", 10, 20, 30, 40, "north_to_south")
        with tempfile.TemporaryDirectory() as directory:
            self.manager.config_path = Path(directory) / "sources.json"
            self.manager._persist()
            restored = StreamManager(
                model=MagicMock(),
                confidence=0.35,
                device="cpu",
                jpeg_quality=75,
            )
            restored.config_path = self.manager.config_path
            restored.load()
            self.assertEqual(len(restored.sources), 1)
            restored_worker = restored.get("test-mp4")
            self.assertIsNotNone(restored_worker)
            self.assertEqual(restored_worker.counter.count_line, (10, 20, 30, 40))
            self.assertEqual(restored_worker.counter.entering_direction, "north_to_south")
            for worker in restored.sources.values():
                worker.stop()


if __name__ == "__main__":
    unittest.main()