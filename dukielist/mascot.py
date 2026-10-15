"""Render the DukieList mascot as cached Unicode True Color terminal art."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sysconfig
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rich.text import Text
from textual.widgets import Static


MASCOT_SETTING_KEY = "mascot_enabled"
_SGR = re.compile(r"\x1b\[[0-9;]*m")
_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_OSC = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\\\)")


@dataclass(frozen=True)
class MascotLayout:
    variant: str
    columns: int
    rows: int


def choose_layout(context: str, width: int, height: int, enabled: bool = True) -> MascotLayout | None:
    """Pick a preset that fits its UI region without shrinking task controls."""
    if not enabled or width < 60 or height < 18:
        return None

    if context == "welcome":
        if width >= 140 and height >= 42:
            return MascotLayout("duck-do", 36, 18)
        if width >= 100 and height >= 38:
            return MascotLayout("duck-do-compact", 22, 11)
        return None

    if context == "main":
        # Reuse the existing header row beside the clock so the calendar keeps
        # its full vertical workspace.
        if width >= 220 and height >= 44:
            return MascotLayout("duck-do-small", 9, 5)
        return None

    if context == "about":
        if width >= 100 and height >= 26:
            return MascotLayout("duck-do-compact", 26, 13)
        if width >= 70 and height >= 20:
            return MascotLayout("duck-do-small", 15, 8)
        return None

    raise ValueError(f"Contexto de mascote desconhecido: {context}")


def mascot_asset_dir() -> Path:
    """Find project assets in a checkout or in an installed package."""
    package_parent = Path(__file__).resolve().parent.parent
    candidates = (
        package_parent / "assets" / "mascot",
        Path(sysconfig.get_path("data")) / "share" / "dukielist" / "assets" / "mascot",
    )
    return next((candidate for candidate in candidates if (candidate / "duck-do.png").is_file()), candidates[0])


def supports_truecolor(console, environ: dict[str, str] | None = None) -> bool:
    """Only emit image colors when Textual's active terminal supports them."""
    env = os.environ if environ is None else environ
    if "NO_COLOR" in env or env.get("TERM", "").lower() == "dumb":
        return False
    if console is None or not getattr(console, "is_terminal", False):
        return False
    color_system = getattr(console, "color_system", None)
    name = getattr(color_system, "name", color_system)
    return str(name).lower() in {"truecolor", "true_color", "24bit"}


def _safe_chafa_output(output: str) -> str:
    """Keep only SGR color codes; drop cursor movement and other controls."""
    def keep_color(match: re.Match[str]) -> str:
        sequence = match.group(0)
        return sequence if _SGR.fullmatch(sequence) else ""

    cleaned = _OSC.sub("", output)
    cleaned = _CSI.sub(keep_color, cleaned)
    cleaned = re.sub(r"\x1b(?!\[[0-9;]*m)", "", cleaned)
    return "".join(
        char
        for char in cleaned
        if char in "\x1b\n\t" or ord(char) >= 32 and ord(char) != 127
    ).rstrip("\n")


@lru_cache(maxsize=48)
def _convert(path: str, mtime_ns: int, size_bytes: int, columns: int, rows: int) -> str | None:
    del mtime_ns, size_bytes  # Included in the cache key so changed assets are converted again.
    executable = shutil.which("chafa")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [
                executable,
                path,
                "--format", "symbols",
                "--symbols", "vhalf",
                "--colors", "full",
                "--size", f"{columns}x{rows}",
                "--polite", "on",
                "--animate", "off",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return _safe_chafa_output(result.stdout)


class MascotDisplay(Static):
    """A non-focusable mascot view; expensive conversion runs off the UI loop."""

    def __init__(self, context: str, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.context = context
        self._enabled = True
        self._signature: tuple | None = None
        self._request = 0

    def on_mount(self) -> None:
        self._enabled = getattr(self.app, "mascot_enabled", True)
        self._schedule_render()

    def on_resize(self, event) -> None:
        self._schedule_render()

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled == enabled:
            return
        self._enabled = enabled
        self._signature = None
        self._schedule_render()

    def _schedule_render(self) -> None:
        app = self.app
        if app is None:
            return
        layout = choose_layout(self.context, app.size.width, app.size.height, self._enabled)
        self._request += 1
        request = self._request
        if layout is None:
            self.display = False
            self._signature = None
            self.update("")
            return

        self.display = True
        self.set_classes(
            f"mascot-display mascot-{self.context} mascot-size-{layout.variant}",
        )
        console = getattr(app, "console", None)
        truecolor = supports_truecolor(console)
        asset = mascot_asset_dir() / f"{layout.variant}.png"
        try:
            stat = asset.stat()
            asset_key = (str(asset), stat.st_mtime_ns, stat.st_size)
        except OSError:
            asset_key = (str(asset), 0, 0)
        signature = (layout, truecolor, asset_key)
        if signature == self._signature:
            return
        self._signature = signature
        self.update(Text("DUKIELIST", style="#00e5ff bold"))
        self.run_worker(
            self._load_art(layout, truecolor, request),
            group=f"mascot-{id(self)}",
            exclusive=True,
        )

    async def _load_art(self, layout: MascotLayout, truecolor: bool, request: int) -> None:
        text = await asyncio.to_thread(self._render_sync, layout, truecolor)
        if request == self._request and self.is_mounted:
            self.update(text)

    @staticmethod
    def _render_sync(layout: MascotLayout, truecolor: bool) -> Text:
        fallback = Text("DUKIELIST", style="#00e5ff bold")
        if not truecolor:
            return fallback
        asset = mascot_asset_dir() / f"{layout.variant}.png"
        try:
            stat = asset.stat()
        except OSError:
            return fallback
        converted = _convert(
            str(asset), stat.st_mtime_ns, stat.st_size, layout.columns, layout.rows
        )
        if converted is None:
            return fallback
        try:
            return Text.from_ansi(converted)
        except (ValueError, TypeError):
            return fallback


__all__ = [
    "MASCOT_SETTING_KEY",
    "MascotDisplay",
    "MascotLayout",
    "_convert",
    "choose_layout",
    "mascot_asset_dir",
    "supports_truecolor",
]
