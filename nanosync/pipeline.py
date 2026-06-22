from __future__ import annotations

import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Sequence


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg was not found on PATH. Install FFmpeg first.")


def ensure_ytdlp_available() -> None:
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp was not found on PATH. Install yt-dlp first.")


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


def build_ytdlp_command(url: str, output: Path | str) -> list[str]:
    return [
        "yt-dlp",
        "-o",
        str(output),
        url,
    ]


def convert_video(source: Path | str, target: Path | str, *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = build_ffmpeg_command(source, target)
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="dry-run", stderr="")

    ensure_ffmpeg_available()
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def download_youtube(url: str, output: Path | str, *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = build_ytdlp_command(url, output)
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="dry-run", stderr="")

    ensure_ytdlp_available()
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
