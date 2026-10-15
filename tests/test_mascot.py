from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from rich.console import Console

from dukielist.mascot import (
    MascotLayout,
    MascotDisplay,
    _convert,
    choose_layout,
    mascot_asset_dir,
    supports_truecolor,
)


class MascotRendererTest(unittest.TestCase):
    def tearDown(self):
        _convert.cache_clear()

    def test_responsive_sizes_preserve_task_area(self):
        self.assertEqual(choose_layout("welcome", 168, 52), MascotLayout("duck-do", 36, 18))
        self.assertEqual(choose_layout("welcome", 120, 40), MascotLayout("duck-do-compact", 22, 11))
        self.assertEqual(choose_layout("main", 220, 52), MascotLayout("duck-do-small", 9, 5))
        self.assertIsNone(choose_layout("main", 168, 52))
        self.assertIsNone(choose_layout("main", 128, 46))
        self.assertIsNone(choose_layout("main", 99, 50))
        self.assertIsNone(choose_layout("main", 168, 40))
        self.assertIsNone(choose_layout("welcome", 80, 30))
        self.assertIsNone(choose_layout("main", 55, 50))
        self.assertIsNone(choose_layout("main", 168, 52, enabled=False))

    def test_project_has_original_and_prepared_assets(self):
        assets = mascot_asset_dir()
        for filename in ("duck-do.png", "duck-do-compact.png", "duck-do-small.png"):
            self.assertTrue((assets / filename).is_file(), filename)

    def test_chafa_uses_unicode_truecolor_and_caches_output(self):
        _convert.cache_clear()
        raw = "\x1b[?25l\x1b[38;2;0;229;255m▄\x1b[0m\x1b[?25h\n"
        completed = subprocess.CompletedProcess([], 0, raw, "")
        with (
            patch("dukielist.mascot.shutil.which", return_value="/usr/bin/chafa"),
            patch("dukielist.mascot.subprocess.run", return_value=completed) as run,
        ):
            first = MascotDisplay._render_sync(MascotLayout("duck-do", 20, 10), True)
            second = MascotDisplay._render_sync(MascotLayout("duck-do", 20, 10), True)

        self.assertEqual(run.call_count, 1)
        args = run.call_args.args[0]
        self.assertEqual(args[1], str(mascot_asset_dir() / "duck-do.png"))
        self.assertIn("--format", args)
        self.assertIn("symbols", args)
        self.assertIn("vhalf", args)
        self.assertIn("full", args)
        self.assertIn("20x10", args)
        self.assertIn("--polite", args)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(first.plain, "▄")
        self.assertEqual(second.plain, "▄")
        self.assertEqual(first.get_style_at_offset(Console(), 0).color.triplet, (0, 229, 255))

    def test_missing_chafa_and_non_tty_use_plain_identity(self):
        _convert.cache_clear()
        layout = MascotLayout("duck-do", 20, 10)
        with patch("dukielist.mascot.shutil.which", return_value=None):
            art = MascotDisplay._render_sync(layout, True)
        self.assertEqual(art.plain, "DUKIELIST")
        self.assertFalse(supports_truecolor(None, {"TERM": "xterm-256color"}))
        self.assertFalse(
            supports_truecolor(
                type("Console", (), {"is_terminal": True, "color_system": "truecolor"})(),
                {"TERM": "xterm-256color", "NO_COLOR": "1"},
            )
        )
        self.assertTrue(
            supports_truecolor(
                type("Console", (), {"is_terminal": True, "color_system": "truecolor"})(),
                {"TERM": "xterm-kitty", "COLORTERM": "truecolor"},
            )
        )


if __name__ == "__main__":
    unittest.main()
