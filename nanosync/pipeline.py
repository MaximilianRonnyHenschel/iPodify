from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# --- Optional local yt-dlp checkout ---

workspace_root = Path(__file__).resolve().parents[1]
local_yt_dlp = workspace_root / "yt-dlp-master"


def _local_ytdlp_main() -> Path | None:
    main_py = local_yt_dlp / "yt_dlp" / "__main__.py"
    return main_py if main_py.exists() else None


def _resolve_ytdlp_runner() -> list[str]:
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]

    local_main = _local_ytdlp_main()
    if local_main is not None:
        return [sys.executable, str(local_main)]

    return ["yt-dlp"]


def _looks_like_playlist_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "youtube" not in host and "youtu.be" not in host:
        return False

    if parsed.path.rstrip("/").endswith("/playlist"):
        return True

    query = parse_qs(parsed.query)
    return "list" in query and bool(query["list"] and query["list"][0])


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg was not found on PATH. Install FFmpeg first.")


def ensure_ytdlp_available() -> None:
    if shutil.which("yt-dlp") is None and _local_ytdlp_main() is None:
        raise RuntimeError("yt-dlp was not found on PATH and no local checkout is available.")


def build_ffmpeg_command(source: Path | str, target: Path | str) -> list[str]:
    source = Path(source)
    target = Path(target)
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        "scale=320:240",
        str(target),
    ]


def _playlist_output_template(output: Path | str) -> str:
    output_path = Path(output)
    base_dir = output_path.with_suffix("") if output_path.suffix else output_path
    return str(base_dir / "%(playlist_index)03d - %(title)s.%(ext)s")


def build_ytdlp_command(url: str, output: Path | str, *, playlist: bool = False) -> list[str]:
    if playlist:
        return [
            "yt-dlp",
            "--yes-playlist",
            "-o",
            _playlist_output_template(output),
            url,
        ]

    return [
        "yt-dlp",
        "-o",
        str(output),
        url,
    ]


def _prepare_output_path(output: Path | str, *, playlist: bool) -> None:
    output_path = Path(output)
    if playlist:
        playlist_root = output_path.with_suffix("") if output_path.suffix else output_path
        playlist_root.mkdir(parents=True, exist_ok=True)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)


def convert_video(source: Path | str, target: Path | str, *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = build_ffmpeg_command(source, target)
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="dry-run", stderr="")

    ensure_ffmpeg_available()
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def download_youtube(url: str, output: Path | str, *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    """Download a YouTube video or playlist."""

    playlist = _looks_like_playlist_url(url)
    cmd = build_ytdlp_command(url, output, playlist=playlist)
    cmd = _resolve_ytdlp_runner() + cmd[1:]

    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="dry-run", stderr="")

    ensure_ytdlp_available()
    _prepare_output_path(output, playlist=playlist)
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def sync_to_ipod(source: Path | str, ipod_root: Path | str, *, title: str = "video") -> Path:
    source = Path(source)
    ipod_root = Path(ipod_root)
    movies_dir = ipod_root / "Movies"
    movies_dir.mkdir(parents=True, exist_ok=True)

    target = movies_dir / f"{title}.mp4"
    target.write_bytes(source.read_bytes())

    db_path = ipod_root / "nanosync.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, source_path TEXT NOT NULL, target_path TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO items (title, source_path, target_path) VALUES (?, ?, ?)",
            (title, str(source), str(target)),
        )
        connection.commit()
    finally:
        connection.close()

    return target
