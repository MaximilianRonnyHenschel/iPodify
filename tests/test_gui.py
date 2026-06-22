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
