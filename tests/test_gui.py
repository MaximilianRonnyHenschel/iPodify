import asyncio
import json
from types import SimpleNamespace
from pathlib import Path

from nanosync import gui


def test_search_results_are_returned_for_query():
    results = gui.search_music_results("queen")

    assert results
    assert any("queen" in item["artist"].lower() for item in results)
    assert all(item["source"] in {"youtube", "local"} for item in results)


def test_unmatched_queries_fall_back_to_sample_suggestions():
    gui.SEARCH_CACHE.clear()
    original_ytdlp = gui.yt_dlp
    original_path = gui.local_yt_dlp
    gui.yt_dlp = None
    gui.local_yt_dlp = Path("missing")
    results = gui.search_music_results("zzzznotfound")
    gui.yt_dlp = original_ytdlp
    gui.local_yt_dlp = original_path

    assert results
    assert all(item["source"] in {"youtube", "local"} for item in results)


def test_search_results_parse_ytdlp_json(monkeypatch, tmp_path):
    fake_result = type("Completed", (), {"stdout": '[{"title": "Bohemian Rhapsody", "uploader": "Queen", "url": "https://youtube.com/watch?v=1", "duration": 355}]', "returncode": 0})()

    def fake_run(cmd, capture_output, text, check, timeout):
        return fake_result

    (tmp_path / "yt_dlp").mkdir()
    gui.SEARCH_CACHE.clear()
    monkeypatch.setattr(gui, "local_yt_dlp", tmp_path)
    monkeypatch.setattr(gui.subprocess, "run", fake_run)
    monkeypatch.setattr(gui, "yt_dlp", object())

    results = gui.search_music_results("queen")

    assert results[0]["title"] == "Bohemian Rhapsody"
    assert results[0]["artist"] == "Queen"


def test_search_results_recognize_playlist_url(monkeypatch, tmp_path):
    fake_payload = {
        "title": "Queen Playlist",
        "uploader": "Queen",
        "webpage_url": "https://youtube.com/playlist?list=PL123",
        "entries": [
            {"title": "Track One", "uploader": "Queen", "url": "https://youtube.com/watch?v=1"},
            {"title": "Track Two", "uploader": "Queen", "url": "https://youtube.com/watch?v=2"},
        ],
    }
    fake_result = type("Completed", (), {"stdout": json.dumps(fake_payload), "returncode": 0})()

    def fake_run(cmd, capture_output, text, check, timeout):
        return fake_result

    (tmp_path / "yt_dlp").mkdir()
    gui.SEARCH_CACHE.clear()
    monkeypatch.setattr(gui, "local_yt_dlp", tmp_path)
    monkeypatch.setattr(gui.subprocess, "run", fake_run)
    monkeypatch.setattr(gui, "yt_dlp", object())

    results = gui.search_music_results("https://youtube.com/playlist?list=PL123")

    assert results[0]["kind"] == "playlist"
    assert results[0]["track_count"] == "2"
    assert any(item["title"] == "Track One" for item in results[1:])


def test_playlist_download_target_uses_playlist_id():
    target = gui._playlist_download_target("https://www.youtube.com/playlist?list=PL123ABC")

    assert target is not None
    assert target.parts[-2:] == ("playlists", "playlist_PL123ABC")


def test_playlist_download_target_rejects_non_playlist_url():
    assert gui._playlist_download_target("https://www.youtube.com/watch?v=123") is None


def test_read_clipboard_text_trims_whitespace():
    class FakeClipboard:
        async def get(self):
            return "  https://youtube.com/playlist?list=PL123  "

    assert asyncio.run(gui._read_clipboard_text(FakeClipboard())) == "https://youtube.com/playlist?list=PL123"


def test_items_from_payload_extracts_cover_url():
    payload = {
        "title": "Bohemian Rhapsody",
        "uploader": "Queen",
        "url": "https://youtube.com/watch?v=1",
        "thumbnail": "https://img.example/cover.jpg",
    }

    items = gui._items_from_payload(payload)

    assert items[0]["cover"] == "https://img.example/cover.jpg"


def test_ensure_logo_ico_creates_icon_file():
    ico_path = gui._ensure_logo_ico()

    assert ico_path is not None
    assert ico_path.exists()
    assert ico_path.read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_configure_window_sets_borderless_model_window():
    class DummyWindow(SimpleNamespace):
        def center(self):
            self.center_called = True

        def update(self):
            self.update_called = True

    page = SimpleNamespace(
        window=DummyWindow(),
        padding=None,
        spacing=None,
    )

    gui._configure_window(page, {"background": "#111111"})

    assert page.window.frameless is True
    assert page.window.title_bar_hidden is True
    assert page.window.width == gui.IPOD_STAGE_WIDTH
    assert page.window.height == gui.IPOD_STAGE_HEIGHT
    assert page.window.center_called is True
    assert page.window.update_called is True
    assert page.padding == 0


def test_coverflow_transform_tilts_side_cards():
    center = gui._coverflow_transform(0)
    left = gui._coverflow_transform(-1)
    right = gui._coverflow_transform(1)

    assert center.matrix.ops == []
    assert left.matrix.ops[0].name == "rotate_y"
    assert right.matrix.ops[0].name == "rotate_y"
    assert left.matrix.ops[0].args[0] < 0
    assert right.matrix.ops[0].args[0] > 0


def test_short_query_uses_fast_path_without_subprocess(monkeypatch):
    called = {"run": False}

    def fake_run(*_args, **_kwargs):
        called["run"] = True
        raise RuntimeError("should not be called")

    monkeypatch.setattr(gui.subprocess, "run", fake_run)

    results = gui.search_music_results("q")

    assert results
    assert called["run"] is False


def test_search_uses_short_subprocess_timeout(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, capture_output, text, check, timeout):
        calls["timeout"] = timeout
        return type("Completed", (), {"stdout": "", "returncode": 0})()

    (tmp_path / "yt_dlp").mkdir()
    gui.SEARCH_CACHE.clear()
    monkeypatch.setattr(gui, "local_yt_dlp", tmp_path)
    monkeypatch.setattr(gui.subprocess, "run", fake_run)
    monkeypatch.setattr(gui, "yt_dlp", object())

    results = gui.search_music_results("queen")

    assert results
    assert calls["timeout"] == 6


def test_safe_search_results_returns_empty_list_on_exception(monkeypatch):
    monkeypatch.setattr(gui, "search_music_results", lambda query: (_ for _ in ()).throw(RuntimeError("boom")))

    assert gui.safe_search_results("queen") == []


def test_perform_pipeline_action_download_uses_ytdlp(monkeypatch, tmp_path):
    target = tmp_path / "download.mp4"
    calls = {}

    def fake_download(url, output, *, dry_run=False):
        calls["args"] = (url, output, dry_run)
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(gui, "download_youtube", fake_download)

    result = gui.perform_pipeline_action("download", url="https://example.com/video", target=str(target))

    assert result == f"Download completed: {target}"
    assert calls["args"] == ("https://example.com/video", target, False)


def test_perform_pipeline_action_sync_returns_target(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"demo")
    ipod_root = tmp_path / "ipod"
    expected = ipod_root / "Movies" / "demo.mp4"

    def fake_sync(source_path, ipod_path, *, title="video"):
        return expected

    monkeypatch.setattr(gui, "sync_to_ipod", fake_sync)

    result = gui.perform_pipeline_action("sync", source=str(source), ipod_root=str(ipod_root), title="demo")

    assert result == f"Sync completed: {expected}"
