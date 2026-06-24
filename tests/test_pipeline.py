from pathlib import Path

import pytest

from nanosync.pipeline import (
    build_ffmpeg_command,
    build_ytdlp_command,
    convert_video,
    ensure_ffmpeg_available,
    download_youtube,
    sync_to_ipod,
)


def test_build_ffmpeg_command_contains_ipod_profile():
    source = Path("sample.mp4")
    target = Path("output.mp3")

    cmd = build_ffmpeg_command(source, target)

    assert cmd[0] == "ffmpeg"
    assert "-vn" in cmd
    assert "-codec:a" in cmd
    assert "libmp3lame" in cmd
    assert "192k" in cmd
    assert "44100" in cmd
    assert str(source) in cmd
    assert str(target) in cmd


def test_ensure_ffmpeg_available_raises_when_missing(monkeypatch):
    monkeypatch.setattr("nanosync.pipeline.shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        ensure_ffmpeg_available()


def test_convert_video_dry_run_skips_ffmpeg_check(monkeypatch):
    monkeypatch.setattr("nanosync.pipeline.shutil.which", lambda name: None)

    result = convert_video("sample.mp4", "output.mp3", dry_run=True)

    assert result.returncode == 0
    assert result.stdout == "dry-run"


def test_build_ytdlp_command_contains_source_and_output(tmp_path):
    output = tmp_path / "download.mp3"

    cmd = build_ytdlp_command("https://example.com/video", output)

    assert cmd[0] == "yt-dlp"
    assert "-x" in cmd
    assert "--audio-format" in cmd
    assert "mp3" in cmd
    assert "https://example.com/video" in cmd
    assert str(output) in cmd


def test_build_ytdlp_command_playlist_uses_playlist_template(tmp_path):
    output = tmp_path / "playlist"

    cmd = build_ytdlp_command("https://example.com/playlist?list=abc", output, playlist=True)

    assert cmd[0] == "yt-dlp"
    assert "--yes-playlist" in cmd
    assert str(output / "%(playlist_index)03d - %(title)s.%(ext)s") in cmd


def test_download_youtube_playlist_uses_playlist_mode(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, check, capture_output, text):
        calls["cmd"] = cmd
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("nanosync.pipeline.shutil.which", lambda name: "yt-dlp")
    monkeypatch.setattr("nanosync.pipeline.subprocess.run", fake_run)

    output = tmp_path / "playlist"
    result = download_youtube("https://www.youtube.com/watch?v=1&list=abc", output)

    assert result.returncode == 0
    assert "--yes-playlist" in calls["cmd"]
    assert any("%(playlist_index)" in part for part in calls["cmd"])
    assert output.exists()


def test_sync_to_ipod_creates_ipod_folder_and_db(tmp_path):
    source = tmp_path / "source.mp3"
    source.write_bytes(b"audio-data")
    ipod_root = tmp_path / "ipod"

    target = sync_to_ipod(source, ipod_root, title="Demo")

    assert target.exists()
    assert target.parent.name == "Music"
    assert (ipod_root / "nanosync.db").exists()
    assert target.read_bytes() == b"audio-data"
