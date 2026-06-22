from pathlib import Path

import pytest

from nanosync.pipeline import (
    build_ffmpeg_command,
    build_ytdlp_command,
    convert_video,
    ensure_ffmpeg_available,
    sync_to_ipod,
)


def test_build_ffmpeg_command_contains_ipod_profile():
    source = Path("sample.mp4")
    target = Path("output.mp4")

    cmd = build_ffmpeg_command(source, target)

    assert cmd[0] == "ffmpeg"
    assert "-vf" in cmd
    assert "scale=320:240" in cmd
    assert str(source) in cmd
    assert str(target) in cmd


def test_ensure_ffmpeg_available_raises_when_missing(monkeypatch):
    monkeypatch.setattr("nanosync.pipeline.shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        ensure_ffmpeg_available()


def test_convert_video_dry_run_skips_ffmpeg_check(monkeypatch):
    monkeypatch.setattr("nanosync.pipeline.shutil.which", lambda name: None)

    result = convert_video("sample.mp4", "output.mp4", dry_run=True)

    assert result.returncode == 0
    assert result.stdout == "dry-run"


def test_build_ytdlp_command_contains_source_and_output(tmp_path):
    output = tmp_path / "download.mp4"

    cmd = build_ytdlp_command("https://example.com/video", output)

    assert cmd[0] == "yt-dlp"
    assert "https://example.com/video" in cmd
    assert str(output) in cmd


def test_sync_to_ipod_creates_ipod_folder_and_db(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video-data")
    ipod_root = tmp_path / "ipod"

    target = sync_to_ipod(source, ipod_root, title="Demo")

    assert target.exists()
    assert target.parent.name == "Movies"
    assert (ipod_root / "nanosync.db").exists()
    assert target.read_bytes() == b"video-data"
