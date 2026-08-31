"""Checks for model/device switching: device naming + worker restart safety."""

import threading
import unittest

from src.server import VideoStreamWorker, canonical_device, restart_worker_with


class _FakeCounter:
    """Minimal counter so the worker can run its loop without YOLO."""

    def __init__(self):
        self.device = "cpu"

    def get_counts(self):
        return {"in": 0, "out": 0, "current": 0}

    def process_frame(self, frame):
        return frame, self.get_counts()

    def reset_counts(self):
        pass


class TestCanonicalDevice(unittest.TestCase):
    def test_cuda_alias_matches_chip_name(self):
        self.assertEqual(canonical_device("cuda"), "cuda:0")

    def test_explicit_and_cpu_unchanged(self):
        self.assertEqual(canonical_device("cuda:1"), "cuda:1")
        self.assertEqual(canonical_device("cpu"), "cpu")


class TestRestartWorkerWith(unittest.TestCase):
    def tearDown(self):
        self.worker.stop()

    def test_job_applied_and_worker_restarted(self):
        self.worker = VideoStreamWorker(source="", counter=_FakeCounter(), model_name="m")
        self.worker.start()
        gen_before = self.worker.generation
        box = {}

        def job():
            box["done"] = True

        restart_worker_with(self.worker, job)

        self.assertTrue(box.get("done"))
        self.assertTrue(self.worker.running)
        self.assertGreater(self.worker.generation, gen_before)
        self.assertIsNotNone(self.worker.thread)

    def test_stale_loop_exits_even_when_running_flips_back_true(self):
        """Regression: stop() join timeout used to leave two loops running."""
        self.worker = VideoStreamWorker(source="", counter=_FakeCounter(), model_name="m")
        self.worker.generation = 1
        self.worker.running = True
        stale = threading.Thread(target=self.worker._run_loop, args=(1,), daemon=True)
        stale.start()
        self.worker.generation = 2  # what start() does while the old loop is mid-frame
        stale.join(timeout=2.0)
        self.assertFalse(stale.is_alive())


if __name__ == "__main__":
    unittest.main()
