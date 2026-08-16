import unittest

from src.discover_cameras import _json_value, build_parser


class DiscoverCameraTests(unittest.TestCase):
    def test_parser_and_json_serialization(self):
        args = build_parser().parse_args(["--host", "192.168.1.20", "--port", "8000"])
        self.assertEqual((args.host, args.port), ("192.168.1.20", 8000))
        self.assertEqual(_json_value({"host": "camera", "port": 80}), {"host": "camera", "port": 80})


if __name__ == "__main__":
    unittest.main()
