import tempfile
import unittest
from pathlib import Path

from src.count_people import (
    build_parser,
    crossing_direction,
    current_people_after_crossing,
    default_entering_direction,
    line_from_args,
    parse_line,
    source_with_credentials,
)


class CountPeopleTests(unittest.TestCase):
    def test_line_parser(self):
        self.assertEqual(parse_line("10, 20, 300,400"), (10, 20, 300, 400))
        args = build_parser().parse_args(["--source", "clip.mp4"])
        self.assertIsNone(args.line)
        self.assertFalse(args.no_preview)
        self.assertEqual((args.display_width, args.display_height), (1920, 1080))
        self.assertEqual(args.device, "cuda")
        self.assertEqual(
            source_with_credentials("rtsp://192.168.1.23:554/profile1", "admin", "p@ss"),
            "rtsp://admin:p%40ss@192.168.1.23:554/profile1",
        )

    def test_crossing_direction(self):
        horizontal = (178, 222, 399, 224)
        vertical = (320, 100, 322, 500)

        self.assertEqual(default_entering_direction(horizontal), "north_to_south")
        self.assertEqual(default_entering_direction(vertical), "west_to_east")
        self.assertEqual(crossing_direction((250, 200), (250, 260), horizontal), "north_to_south")
        self.assertEqual(crossing_direction((250, 260), (250, 200), horizontal), "south_to_north")
        self.assertEqual(crossing_direction((280, 200), (360, 200), vertical), "west_to_east")
        self.assertEqual(crossing_direction((360, 200), (280, 200), vertical), "east_to_west")
        self.assertIsNone(crossing_direction((250, 200), (260, 210), horizontal))

    def test_current_people_never_goes_negative(self):
        self.assertEqual(current_people_after_crossing(0, "south_to_north", "north_to_south"), 0)
        self.assertEqual(current_people_after_crossing(0, "north_to_south", "north_to_south"), 1)
        self.assertEqual(current_people_after_crossing(2, "south_to_north", "north_to_south"), 1)

    def test_line_from_args(self):
        self.assertEqual(line_from_args((1, 2, 3, 4), None, 100, 200), (1, 2, 3, 4))
        self.assertEqual(line_from_args(None, None, 100, 200), (50, 0, 50, 200))

        with tempfile.TemporaryDirectory() as directory:
            line_file = Path(directory) / "line.txt"
            line_file.write_text("10,20,30,40")
            self.assertEqual(line_from_args(None, str(line_file), 100, 200), (10, 20, 30, 40))

        with self.assertRaises(ValueError):
            line_from_args((1, 2, 3, 4), "line.txt", 100, 200)


if __name__ == "__main__":
    unittest.main()
