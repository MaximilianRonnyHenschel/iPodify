from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import flet as ft

workspace_root = Path(__file__).resolve().parents[1]
assets_root = workspace_root / "assets"
logo_png_path = assets_root / "logo.png"
logo_ico_path = assets_root / "logo.ico"
fallback_cover_src = "IPod_nano.png"
local_yt_dlp = workspace_root / "yt-dlp-master"
if local_yt_dlp.exists():
    sys.path.insert(0, str(local_yt_dlp))

try:
    import yt_dlp
except ModuleNotFoundError:  # pragma: no cover - fallback for missing local checkout
    yt_dlp = None

from nanosync.pipeline import convert_video, download_youtube, sync_to_ipod


SAMPLE_ITEMS = [
    {"title": "Bohemian Rhapsody", "artist": "Queen", "source": "youtube", "url": "https://youtube.com/watch?v=example1"},
    {"title": "Another One Bites the Dust", "artist": "Queen", "source": "youtube", "url": "https://youtube.com/watch?v=example2"},
    {"title": "Imagine", "artist": "John Lennon", "source": "local", "url": "local://imagine"},
]
SEARCH_CACHE: dict[str, list[dict[str, str]]] = {}
MAX_CACHE_SIZE = 48
DOWNLOAD_QUEUE: list[dict[str, str]] = []

LANGUAGE_CHOICES = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
    ("pl", "Polski"),
    ("pt", "Português"),
]

CURRENT_LANGUAGE = "de"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "de": {
        "ready": "Bereit",
        "search_hint": "Bibliothek durchsuchen",
        "playlist_hint": "YouTube-Playlist-URL",
        "ipod_root_hint": "iPod- oder USB-Root",
        "menu_title": "Suche, Download & Sync",
        "menu_help": "Finde Musik, lade sie als MP3 und schiebe sie per Kabel auf den iPod.",
        "import_button": "Playlist importieren",
        "queue_button": "Einreihen",
        "download_button": "MP3 herunterladen",
        "sync_button": "Auf den iPod kopieren",
        "language_label": "Sprache",
        "screen_subtitle": "MP3 · iPod Nano · Android",
        "no_results": "Keine Treffer",
        "no_results_hint": "Suche in der Bibliothek oder füge eine Playlist-URL ein.",
        "results_found": "{count} Treffer gefunden.",
        "selected_prefix": "Ausgewählt: {title}",
        "no_item_queue": "Nichts zum Einreihen.",
        "no_item_download": "Nichts zum Herunterladen.",
        "no_item_sync": "Nichts zum Synchronisieren.",
        "invalid_url": "Ungültige URL für {title}",
        "queued_added": "Zur Warteschlange hinzugefügt: {title}",
        "playlist_url_prompt": "Bitte eine YouTube-Playlist-URL einfügen.",
        "start_playlist_import": "Importiere Playlist: {name}...",
        "playlist_imported": "Playlist importiert: {name}",
        "start_download": "Herunterladen: {title}...",
        "download_complete": "Heruntergeladen: {name}",
        "start_sync": "Synchronisiere: {title}...",
        "sync_complete": "Auf den iPod kopiert: {name}",
        "sync_playlist_complete": "{count} Titel auf den iPod kopiert.",
        "ipod_root_prompt": "Bitte den iPod- oder USB-Root auswählen.",
        "choose_folder": "Ordner wählen",
        "download_and_sync": "MP3 + Sync",
        "folder_selected": "Ordner gewählt: {name}",
        "clipboard_empty": "Zwischenablage ist leer.",
        "clipboard_pasted": "Zwischenablage eingefügt.",
        "error": "Fehler: {message}",
        "paste_tooltip": "Aus Zwischenablage einfügen",
        "menu_tooltip": "Menü",
        "previous_tooltip": "Vorheriges",
        "next_tooltip": "Nächstes",
        "download_selected_tooltip": "Auswahl herunterladen",
        "sync_selected_tooltip": "Auswahl auf den iPod kopieren",
    },
    "en": {
        "ready": "Ready",
        "search_hint": "Search the library",
        "playlist_hint": "YouTube playlist URL",
        "ipod_root_hint": "iPod or USB root",
        "menu_title": "Search, download & sync",
        "menu_help": "Find music, download it as MP3, and send it to your iPod over cable.",
        "import_button": "Import playlist",
        "queue_button": "Queue",
        "download_button": "Download MP3",
        "sync_button": "Copy to iPod",
        "language_label": "Language",
        "screen_subtitle": "MP3 · iPod Nano · Android",
        "no_results": "No results",
        "no_results_hint": "Search the library or paste a playlist URL.",
        "results_found": "{count} results found.",
        "selected_prefix": "Selected: {title}",
        "no_item_queue": "Nothing to add to the list.",
        "no_item_download": "Nothing to download.",
        "no_item_sync": "Nothing to sync.",
        "invalid_url": "Invalid URL for {title}",
        "queued_added": "Added to queue: {title}",
        "playlist_url_prompt": "Please paste a YouTube playlist URL.",
        "start_playlist_import": "Importing playlist: {name}...",
        "playlist_imported": "Playlist imported: {name}",
        "start_download": "Downloading: {title}...",
        "download_complete": "Downloaded: {name}",
        "start_sync": "Syncing: {title}...",
        "sync_complete": "Copied to iPod: {name}",
        "sync_playlist_complete": "{count} tracks copied to the iPod.",
        "ipod_root_prompt": "Please choose the iPod or USB root first.",
        "choose_folder": "Choose folder",
        "download_and_sync": "MP3 + Sync",
        "folder_selected": "Folder selected: {name}",
        "clipboard_empty": "Clipboard is empty.",
        "clipboard_pasted": "Pasted from clipboard.",
        "error": "Error: {message}",
        "paste_tooltip": "Paste from clipboard",
        "menu_tooltip": "Menu",
        "previous_tooltip": "Previous",
        "next_tooltip": "Next",
        "download_selected_tooltip": "Download selected",
        "sync_selected_tooltip": "Copy selected to iPod",
    },
}


def _set_language(language_code: str) -> None:
    global CURRENT_LANGUAGE
    CURRENT_LANGUAGE = language_code if language_code in TRANSLATIONS else "de"


def _t(key: str, **kwargs: Any) -> str:
    language = TRANSLATIONS.get(CURRENT_LANGUAGE, TRANSLATIONS["de"])
    value = language.get(key, TRANSLATIONS["de"].get(key, key))
    return value.format(**kwargs)


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name)
    return cleaned.strip("_")[:64] or "track"


def _filter_sample_items(normalized: str, *, limit: int = 8) -> list[dict[str, str]]:
    if not normalized:
        return SAMPLE_ITEMS[:limit]
    return [
        item
        for item in SAMPLE_ITEMS
        if normalized in item["title"].lower() or normalized in item["artist"].lower()
    ][:limit]


def _fallback_items(normalized: str, *, limit: int = 8) -> list[dict[str, str]]:
    matches = _filter_sample_items(normalized, limit=limit)
    return matches if matches else _filter_sample_items("", limit=limit)


def _cache_result(normalized: str, items: list[dict[str, str]]) -> list[dict[str, str]]:
    if normalized and normalized not in SEARCH_CACHE:
        if len(SEARCH_CACHE) >= MAX_CACHE_SIZE:
            SEARCH_CACHE.pop(next(iter(SEARCH_CACHE)))
        SEARCH_CACHE[normalized] = items[:8]
    return items[:8]


def _items_from_payload(payload: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    payload_entries = payload if isinstance(payload, list) else [payload]
    for entry in payload_entries:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "Untitled")
        artist = str(entry.get("uploader") or entry.get("channel") or "Unknown")
        url = str(entry.get("url") or entry.get("webpage_url") or "")
        source = str(entry.get("extractor_key") or "youtube").lower()
        source_label = "youtube" if "youtube" in source else "local"
        cover = str(entry.get("thumbnail") or "")
        if not cover:
            thumbnails = entry.get("thumbnails")
            if isinstance(thumbnails, list):
                for thumb in reversed(thumbnails):
                    if not isinstance(thumb, dict):
                        continue
                    thumb_url = thumb.get("url")
                    if thumb_url:
                        cover = str(thumb_url)
                        break
        items.append({"title": title, "artist": artist, "source": source_label, "url": url, "cover": cover})
    return items


def _looks_like_youtube_url(query: str) -> bool:
    parsed = urlparse(query)
    host = (parsed.netloc or "").lower()
    if not host:
        return False
    return "youtube" in host or "youtu.be" in host


def _playlist_summary_item(info: dict[str, Any], url: str, *, entry_count: int) -> dict[str, str]:
    title = str(info.get("title") or info.get("playlist_title") or "Untitled playlist")
    artist = str(info.get("uploader") or info.get("channel") or "YouTube playlist")
    cover = str(info.get("thumbnail") or "")
    if not cover:
        thumbnails = info.get("thumbnails")
        if isinstance(thumbnails, list):
            for thumb in reversed(thumbnails):
                if not isinstance(thumb, dict):
                    continue
                thumb_url = thumb.get("url")
                if thumb_url:
                    cover = str(thumb_url)
                    break
    return {
        "title": title,
        "artist": artist,
        "source": "youtube",
        "url": str(info.get("webpage_url") or url),
        "cover": cover,
        "kind": "playlist",
        "track_count": str(entry_count),
    }


def _convert_info_to_items(info: Any, *, url: str | None = None, playlist_mode: bool = False) -> list[dict[str, str]]:
    if not isinstance(info, dict):
        return []

    entries = info.get("entries")
    if playlist_mode and isinstance(entries, list) and entries:
        playlist_url = str(info.get("webpage_url") or url or "")
        items: list[dict[str, str]] = [_playlist_summary_item(info, playlist_url, entry_count=len(entries))]
        for entry in entries[:8]:
            items.extend(_items_from_payload(entry))
        return items

    if isinstance(entries, list) and entries:
        items: list[dict[str, str]] = []
        for entry in entries[:8]:
            items.extend(_items_from_payload(entry))
        if items:
            return items

    return _items_from_payload(info)


def _ytdlp_command_base(query: str, *, url_mode: bool) -> list[str]:
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]

    local_main = local_yt_dlp / "yt_dlp" / "__main__.py"
    if local_main.exists():
        return [sys.executable, str(local_main)]

    return [sys.executable, "-m", "yt_dlp"]


def _run_ytdlp_subprocess(query: str, *, url_mode: bool) -> subprocess.CompletedProcess[str]:
    if url_mode:
        cmd = _ytdlp_command_base(query, url_mode=True) + ["--skip-download", "--dump-single-json", query]
    else:
        cmd = _ytdlp_command_base(query, url_mode=False) + ["--skip-download", "--print", "json", f"ytsearch8:{query}"]

    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=6)


def _parse_ytdlp_stdout(stdout: str, *, url_mode: bool, url: str | None = None) -> list[dict[str, str]]:
    if not stdout.strip():
        return []

    payloads: list[Any] = []
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        payloads = parsed if isinstance(parsed, list) else [parsed]
    else:
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, list):
                payloads.extend(payload)
            else:
                payloads.append(payload)

    items: list[dict[str, str]] = []
    for payload in payloads:
        if url_mode and isinstance(payload, dict) and isinstance(payload.get("entries"), list) and payload.get("entries"):
            items.extend(_convert_info_to_items(payload, url=url, playlist_mode=True))
            continue
        items.extend(_items_from_payload(payload))
    return items


def search_music_results(query: str) -> list[dict[str, str]]:
    raw_query = (query or "").strip()
    normalized = raw_query.lower()
    if not raw_query:
        return _fallback_items(normalized, limit=9)

    if not _looks_like_youtube_url(raw_query) and len(normalized) < 2:
        return _fallback_items(normalized, limit=9)

    cache_key = normalized
    cached = SEARCH_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()

    url_mode = _looks_like_youtube_url(raw_query)

    if yt_dlp is not None and hasattr(yt_dlp, "YoutubeDL"):
        try:
            ydl_opts = {
                "skip_download": True,
                "extract_flat": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 6,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(raw_query if url_mode else f"ytsearch8:{normalized}", download=False)

            items = _convert_info_to_items(info, url=raw_query, playlist_mode=url_mode)
            if items:
                return _cache_result(cache_key, items)
        except Exception:
            pass

    try:
        result = _run_ytdlp_subprocess(raw_query if url_mode else normalized, url_mode=url_mode)
    except Exception:
        return _cache_result(cache_key, _fallback_items(normalized))

    if result.returncode == 0 and result.stdout.strip():
        items = _parse_ytdlp_stdout(result.stdout, url_mode=url_mode, url=raw_query)
        if items:
            return _cache_result(cache_key, items)

    return _cache_result(cache_key, _fallback_items(normalized))


def safe_search_results(query: str) -> list[dict[str, str]]:
    try:
        return search_music_results(query)
    except Exception:
        return []


def _resolve_ffmpeg_binary() -> str:
    configured = os.environ.get("NANOSYNC_FFMPEG", "").strip()
    if configured:
        return configured

    binary = shutil.which("ffmpeg")
    if binary:
        return binary

    bundled_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    bundled = workspace_root / "bin" / bundled_name
    if bundled.exists():
        return str(bundled)

    raise RuntimeError("ffmpeg was not found on PATH. Install FFmpeg first.")


def perform_pipeline_action(command: str, **kwargs: Any) -> str:
    if command == "convert":
        source = Path(kwargs["source"])
        target = Path(kwargs["target"])
        result = convert_video(source, target, dry_run=kwargs.get("dry_run", False))
        return f"Conversion completed: {target}" if result.returncode == 0 else f"Conversion failed: {result.returncode}"

    if command == "download":
        url = kwargs["url"]
        target = Path(kwargs["target"])
        result = download_youtube(url, target, dry_run=kwargs.get("dry_run", False))
        return f"Download completed: {target}" if result.returncode == 0 else f"Download failed: {result.returncode}"

    if command == "sync":
        source = Path(kwargs["source"])
        ipod_root = Path(kwargs["ipod_root"])
        target = sync_to_ipod(source, ipod_root, title=kwargs.get("title", "track"))
        return f"Sync completed: {target}"

    raise ValueError(f"Unsupported command: {command}")


def _download_target_for_item(item: dict[str, str]) -> Path:
    title = _safe_filename(item["title"])
    if item.get("kind") == "playlist":
        playlist_target = _playlist_download_target(item.get("url", ""))
        if playlist_target is not None:
            return playlist_target
        return workspace_root / "downloads" / "playlists" / title
    return workspace_root / "downloads" / f"{title}.mp3"


def _playlist_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "youtube" not in host and "youtu.be" not in host:
        return None

    playlist_id = parse_qs(parsed.query).get("list", [None])[0]
    if not playlist_id:
        return None
    playlist_id = playlist_id.strip()
    return playlist_id or None


def _playlist_download_target(url: str) -> Path | None:
    playlist_id = _playlist_id_from_url(url)
    if playlist_id is None:
        return None
    return workspace_root / "downloads" / "playlists" / f"playlist_{_safe_filename(playlist_id)}"


def _png_to_ico_bytes(png_bytes: bytes) -> bytes:
    image_offset = 6 + 16
    width = struct.unpack(">I", png_bytes[16:20])[0] if len(png_bytes) >= 20 else 0
    height = struct.unpack(">I", png_bytes[20:24])[0] if len(png_bytes) >= 24 else 0
    width_byte = width if width < 256 else 0
    height_byte = height if height < 256 else 0
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII",
        width_byte,
        height_byte,
        0,
        0,
        1,
        32,
        len(png_bytes),
        image_offset,
    )
    return header + entry + png_bytes


def _ensure_logo_ico() -> Path | None:
    if not logo_png_path.exists():
        return None

    png_bytes = logo_png_path.read_bytes()
    ico_bytes = _png_to_ico_bytes(png_bytes)
    if logo_ico_path.exists() and logo_ico_path.read_bytes() == ico_bytes:
        return logo_ico_path
    logo_ico_path.write_bytes(ico_bytes)
    return logo_ico_path


def _apply_window_icon(page: ft.Page) -> None:
    ico_path = _ensure_logo_ico()
    if ico_path is not None and hasattr(page.window, "icon"):
        page.window.icon = str(ico_path)


IPOD_BODY_WIDTH = 520
IPOD_BODY_ASPECT_RATIO = 1.55
IPOD_BODY_HEIGHT = int(round(IPOD_BODY_WIDTH * IPOD_BODY_ASPECT_RATIO))
IPOD_STAGE_WIDTH = IPOD_BODY_WIDTH
IPOD_STAGE_HEIGHT = IPOD_BODY_HEIGHT
IPOD_SCREEN_WIDTH = 488
IPOD_SCREEN_HEIGHT = 600
IPOD_WHEEL_SIZE = 192


def _configure_window(page: ft.Page, colors: dict[str, str]) -> None:
    window = getattr(page, "window", None)
    if window is None:
        return

    for attr, value in (
        ("width", IPOD_STAGE_WIDTH),
        ("height", IPOD_STAGE_HEIGHT),
        ("min_width", IPOD_STAGE_WIDTH),
        ("min_height", IPOD_STAGE_HEIGHT),
        ("max_width", IPOD_STAGE_WIDTH),
        ("max_height", IPOD_STAGE_HEIGHT),
        ("resizable", False),
        ("frameless", True),
        ("title_bar_hidden", True),
    ):
        try:
            setattr(window, attr, value)
        except Exception:
            pass

    try:
        window.center()
    except Exception:
        pass

    try:
        window.update()
    except Exception:
        pass

    page.padding = 0
    page.spacing = 0
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.bgcolor = colors["background"]


def _cover_source(item: dict[str, str]) -> str:
    cover = item.get("cover")
    return cover if isinstance(cover, str) and cover else fallback_cover_src


def _source_display_label(source: str) -> str:
    normalized = (source or "").strip().lower()
    if "youtube" in normalized:
        return "YouTube"
    if normalized in {"local", "file"}:
        return "Lokal"
    return normalized.title() if normalized else "Unbekannt"


def _border(color: str, width: int = 1) -> ft.Border:
    return ft.border.all(width, color)


async def _read_clipboard_text(clipboard: Any) -> str:
    if clipboard is None:
        return ""

    getter = getattr(clipboard, "get", None)
    if getter is None:
        return ""

    result = getter()
    if inspect.isawaitable(result):
        result = await result

    if result is None:
        return ""
    return str(result).strip()


def _coverflow_transform(relative_index: int) -> ft.Transform:
    if relative_index == 0:
        return ft.Transform(matrix=ft.Matrix4.identity())

    tilt = -0.25 if relative_index < 0 else 0.25
    shift = -18 if relative_index < 0 else 18
    scale = 0.92
    drop = abs(relative_index) * 4
    matrix = (
        ft.Matrix4.identity()
        .rotate_y(tilt)
        .translate(shift, drop, 0)
        .scale(scale, scale, scale)
    )
    return ft.Transform(matrix=matrix)


def _run_async(page: ft.Page, coro: Any) -> None:
    runner = getattr(page, "run_task", None)
    if callable(runner):
        try:
            async def _wrapper() -> Any:
                return await coro

            runner(_wrapper)
            return
        except Exception:
            pass
    asyncio.run(coro)


def _start_download_job(
    url: str,
    target: Path,
    status_bar: ft.Text,
    page: ft.Page,
    *,
    start_message: str,
    success_message: str,
) -> None:
    status_bar.value = start_message
    page.update()

    def do_download() -> None:
        try:
            message = perform_pipeline_action("download", url=url, target=str(target))
            status_bar.value = success_message if message.startswith("Download completed") else message
        except Exception as exc:
            status_bar.value = _t("error", message=exc)

        page.update()

    threading.Thread(target=do_download, daemon=True).start()


def _sync_playlist_folder(source_dir: Path, ipod_root: Path) -> list[Path]:
    synced: list[Path] = []
    for mp3_path in sorted(source_dir.glob("*.mp3")):
        synced.append(sync_to_ipod(mp3_path, ipod_root, title=mp3_path.stem))
    return synced


def _start_sync_job(
    item: dict[str, str],
    ipod_root: Path,
    status_bar: ft.Text,
    page: ft.Page,
) -> None:
    if not str(ipod_root).strip():
        status_bar.value = _t("ipod_root_prompt")
        page.update()
        return

    status_bar.value = _t("start_sync", title=item["title"])
    page.update()

    def do_sync() -> None:
        try:
            source = _download_target_for_item(item)
            if item.get("kind") == "playlist":
                if not source.exists():
                    download_message = perform_pipeline_action("download", url=item["url"], target=str(source))
                    if not download_message.startswith("Download completed"):
                        raise RuntimeError(download_message)
                synced = _sync_playlist_folder(source, ipod_root)
                if not synced:
                    raise RuntimeError("No MP3 files were found in the playlist folder.")
                status_bar.value = _t("sync_playlist_complete", count=len(synced))
            else:
                if not source.exists():
                    download_message = perform_pipeline_action("download", url=item["url"], target=str(source))
                    if not download_message.startswith("Download completed"):
                        raise RuntimeError(download_message)
                target = sync_to_ipod(source, ipod_root, title=item["title"])
                status_bar.value = _t("sync_complete", name=target.name)
        except Exception as exc:
            status_bar.value = _t("error", message=exc)

        page.update()

    threading.Thread(target=do_sync, daemon=True).start()


def _queue_item(item: dict[str, str], status_bar: ft.Text, page: ft.Page, queue_count_text: ft.Text | None = None) -> None:
    DOWNLOAD_QUEUE.append(item)
    status_bar.value = _t("queued_added", title=item["title"])
    if queue_count_text is not None:
        queue_count_text.value = f"Queue: {len(DOWNLOAD_QUEUE)}"
    page.update()


def _download_item(
    item: dict[str, str],
    status_bar: ft.Text,
    page: ft.Page,
    *,
    start_message: str | None = None,
    success_message: str | None = None,
) -> None:
    url = item.get("url", "")
    if not url or not url.startswith("http"):
        status_bar.value = _t("invalid_url", title=item["title"])
        page.update()
        return

    target = _download_target_for_item(item)
    target.parent.mkdir(parents=True, exist_ok=True)
    is_playlist = item.get("kind") == "playlist"

    _start_download_job(
        url,
        target,
        status_bar,
        page,
        start_message=start_message
        or (_t("start_playlist_import", name=item["title"]) if is_playlist else _t("start_download", title=item["title"])),
        success_message=success_message
        or (_t("playlist_imported", name=item["title"]) if is_playlist else _t("download_complete", name=target.name)),
    )


def _is_mobile_platform(page: ft.Page) -> bool:
    platform = getattr(page, "platform", None)
    if platform is None:
        return False

    value = getattr(platform, "value", None)
    if isinstance(value, str):
        return value in {"android", "ios", "android_tv"}

    checker = getattr(platform, "is_mobile", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            return False

    return False


def _icon_button(icon: str, *, tooltip: str, on_click: Any, background: str | None = None) -> ft.IconButton:
    kwargs: dict[str, Any] = {
        "icon": icon,
        "icon_color": ft.Colors.WHITE,
        "icon_size": 18,
        "tooltip": tooltip,
        "on_click": on_click,
    }
    if background is not None:
        kwargs["bgcolor"] = background
    return ft.IconButton(**kwargs)


def build_media_card(
    item: dict[str, str],
    colors: dict[str, str],
    *,
    key: str | None = None,
    selected: bool = False,
    on_select: Any | None = None,
    on_queue: Any | None = None,
    on_download: Any | None = None,
    on_sync: Any | None = None,
) -> ft.Container:
    cover_source = _cover_source(item)
    source_label = _source_display_label(item.get("source", ""))
    kind_label = "Playlist" if item.get("kind") == "playlist" else source_label
    track_count = item.get("track_count")
    if track_count and item.get("kind") == "playlist":
        subtitle_label = f"{item['artist']} · {kind_label} · {track_count} tracks"
    else:
        subtitle_label = f"{item['artist']} · {kind_label}"

    title_text = ft.Text(
        item["title"],
        weight=ft.FontWeight.W_700,
        color=ft.Colors.WHITE,
        size=15,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    subtitle_text = ft.Text(
        subtitle_label,
        color=ft.Colors.WHITE60,
        size=11,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    action_row = ft.Row(
        controls=[
            _icon_button(ft.Icons.PLAYLIST_ADD, tooltip=_t("queue_button"), on_click=on_queue, background="#1a1f25"),
            _icon_button(ft.Icons.DOWNLOAD, tooltip=_t("download_selected_tooltip"), on_click=on_download, background=colors["primary"]),
            _icon_button(ft.Icons.SYNC, tooltip=_t("sync_selected_tooltip"), on_click=on_sync, background="#143224"),
        ],
        spacing=6,
        tight=True,
    )

    body = ft.Row(
        controls=[
            ft.Container(
                width=64,
                height=64,
                border_radius=14,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor="#091017",
                content=ft.Image(
                    src=cover_source,
                    fit=ft.BoxFit.COVER,
                    width=64,
                    height=64,
                    error_content=ft.Container(
                        alignment=ft.Alignment(0, 0),
                        bgcolor="#091017",
                        content=ft.Icon(ft.Icons.ALBUM, color=colors["primary"], size=28),
                    ),
                ),
            ),
            ft.Container(
                expand=True,
                padding=ft.Padding(10, 2, 10, 2),
                content=ft.Column(
                    controls=[title_text, subtitle_text],
                    spacing=4,
                    tight=True,
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                ),
            ),
            ft.Container(
                content=action_row,
                alignment=ft.Alignment(0, 0),
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return ft.Container(
        key=key,
        expand=True,
        padding=12,
        margin=ft.Margin(0, 0, 0, 0),
        bgcolor=colors["surface_selected"] if selected else colors["surface"],
        border_radius=18,
        border=_border(colors["primary"] if selected else colors["border"], 1),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16 if selected else 10,
            color="#00000044" if selected else "#0000002c",
            offset=ft.Offset(0, 6),
        ),
        ink=True,
        on_click=on_select,
        content=body,
    )


def main(page: ft.Page) -> None:
    colors = {
        "background": "#071018",
        "background_alt": "#0A1520",
        "surface": "#111A24",
        "surface_selected": "#13251A",
        "border": "#223243",
        "primary": "#1DB954",
        "primary_soft": "#30d36b",
        "text": "#F8FAFC",
        "muted": "#9AA4B2",
    }

    _apply_window_icon(page)
    page.title = "NanoSync"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO

    if _is_mobile_platform(page):
        page.padding = 0
        page.spacing = 0
    else:
        _configure_window(page, colors)

    page.bgcolor = colors["background"]

    status_bar = ft.Text(_t("ready"), color=colors["muted"], size=11)
    result_count_text = ft.Text(_t("no_results"), color=colors["muted"], size=11)
    queue_count_text = ft.Text("Queue: 0", color=colors["muted"], size=11)
    result_list = ft.ListView(
        expand=True,
        spacing=10,
        padding=0,
        build_controls_on_demand=True,
    )
    current_results = safe_search_results("")
    selected_index = 0
    status_state: dict[str, Any] = {"key": "ready", "kwargs": {}}

    folder_picker = ft.FilePicker()
    page.overlay.append(folder_picker)

    def set_status(key: str, **kwargs: Any) -> None:
        status_state["key"] = key
        status_state["kwargs"] = kwargs
        status_bar.value = _t(key, **kwargs)
        page.update()

    def selected_item() -> dict[str, str] | None:
        if not current_results:
            return None
        index = max(0, min(selected_index, len(current_results) - 1))
        return current_results[index]

    def build_placeholder_card() -> ft.Container:
        return ft.Container(
            expand=True,
            padding=16,
            border_radius=18,
            bgcolor=colors["surface"],
            border=_border(colors["border"], 1),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.MUSIC_NOTE_OUTLINED, color=colors["primary"], size=28),
                    ft.Column(
                        controls=[
                            ft.Text(_t("no_results"), color=ft.Colors.WHITE, size=14, weight=ft.FontWeight.W_700),
                            ft.Text(_t("no_results_hint"), color=colors["muted"], size=11),
                        ],
                        spacing=2,
                        tight=True,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def render_results(*, scroll: bool = True) -> None:
        nonlocal selected_index

        result_list.controls.clear()
        if current_results:
            selected_index = max(0, min(selected_index, len(current_results) - 1))
            result_count_text.value = _t("results_found", count=len(current_results))
            result_list.controls.extend(
                build_media_card(
                    item,
                    colors,
                    key=f"result-{index}",
                    selected=index == selected_index,
                    on_select=lambda _e, idx=index: select_result(idx),
                    on_queue=lambda _e, idx=index: queue_selected(idx),
                    on_download=lambda _e, idx=index: download_selected(idx),
                    on_sync=lambda _e, idx=index: sync_selected(idx),
                )
                for index, item in enumerate(current_results)
            )
        else:
            selected_index = 0
            result_count_text.value = _t("no_results")
            result_list.controls.append(build_placeholder_card())

        page.update()

        if not scroll or not current_results:
            return

        async def _scroll_to_selected() -> None:
            try:
                await result_list.scroll_to(scroll_key=f"result-{selected_index}", duration=220)
            except Exception:
                pass

        _run_async(page, _scroll_to_selected())

    def select_result(index: int, *, announce: bool = True) -> None:
        nonlocal selected_index
        if not current_results:
            return
        selected_index = max(0, min(index, len(current_results) - 1))
        if announce:
            set_status("selected_prefix", title=current_results[selected_index]["title"])
        render_results(scroll=False)

    def perform_search(e: Any | None = None) -> None:
        nonlocal current_results, selected_index
        query = ""
        if e is not None:
            query = str(getattr(getattr(e, "control", None), "value", "") or "")
        elif search_bar.value:
            query = search_bar.value
        current_results = safe_search_results(query)
        selected_index = 0
        render_results(scroll=False)
        if current_results:
            set_status("results_found", count=len(current_results))
        else:
            set_status("no_results")

    def queue_selected(index: int | None = None) -> None:
        item = current_results[index] if index is not None and 0 <= index < len(current_results) else selected_item()
        if item is None:
            set_status("no_item_queue")
            return
        _queue_item(item, status_bar, page, queue_count_text=queue_count_text)

    def download_selected(index: int | None = None) -> None:
        item = current_results[index] if index is not None and 0 <= index < len(current_results) else selected_item()
        if item is None:
            set_status("no_item_download")
            return
        _download_item(item, status_bar, page)

    def sync_selected(index: int | None = None) -> None:
        item = current_results[index] if index is not None and 0 <= index < len(current_results) else selected_item()
        if item is None:
            set_status("no_item_sync")
            return
        root_value = (ipod_root_field.value or "").strip()
        if not root_value:
            set_status("ipod_root_prompt")
            return
        _start_sync_job(item, Path(root_value), status_bar, page)

    def import_playlist(e: Any | None = None) -> None:
        url = (playlist_url_field.value or "").strip()
        target = _playlist_download_target(url)
        if target is None:
            set_status("playlist_url_prompt")
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        _start_download_job(
            url,
            target,
            status_bar,
            page,
            start_message=_t("start_playlist_import", name=target.name),
            success_message=_t("playlist_imported", name=target.name),
        )

    async def pick_ipod_root() -> None:
        chosen = await folder_picker.get_directory_path(dialog_title=_t("choose_folder"))
        if chosen:
            ipod_root_field.value = chosen
            set_status("folder_selected", name=Path(chosen).name)
            page.update()

    def choose_ipod_root(_e: Any | None = None) -> None:
        _run_async(page, pick_ipod_root())

    async def paste_playlist_from_clipboard(_e: Any | None = None) -> None:
        clipboard_text = await _read_clipboard_text(page.clipboard)
        if not clipboard_text:
            set_status("clipboard_empty")
            return
        playlist_url_field.value = clipboard_text
        set_status("clipboard_pasted")
        page.update()

    def set_language(_e: Any | None = None) -> None:
        selected_value = getattr(language_dropdown, "value", None) or "de"
        _set_language(str(selected_value).strip())
        apply_language()
        render_results(scroll=False)

    search_bar = ft.TextField(
        hint_text=_t("search_hint"),
        prefix_icon=ft.Icons.SEARCH,
        border_color=colors["border"],
        bgcolor=colors["background_alt"],
        border_radius=14,
        color=ft.Colors.WHITE,
        on_submit=perform_search,
        on_change=perform_search,
    )
    playlist_url_field = ft.TextField(
        hint_text=_t("playlist_hint"),
        prefix_icon=ft.Icons.LINK,
        border_color=colors["border"],
        bgcolor=colors["background_alt"],
        border_radius=14,
        color=ft.Colors.WHITE,
        expand=True,
    )
    ipod_root_field = ft.TextField(
        hint_text=_t("ipod_root_hint"),
        prefix_icon=ft.Icons.DRIVE_FILE_MOVE,
        border_color=colors["border"],
        bgcolor=colors["background_alt"],
        border_radius=14,
        color=ft.Colors.WHITE,
        expand=True,
    )

    language_dropdown = ft.Dropdown(
        value=CURRENT_LANGUAGE,
        label=_t("language_label"),
        options=[ft.dropdown.Option(code, label) for code, label in LANGUAGE_CHOICES],
        border_color=colors["border"],
        bgcolor=colors["background_alt"],
        border_radius=14,
        color=ft.Colors.WHITE,
        width=180,
        dense=True,
        on_change=set_language,
    )

    menu_paste_button = ft.IconButton(
        ft.Icons.PASTE,
        tooltip=_t("paste_tooltip"),
        on_click=paste_playlist_from_clipboard,
        icon_color=ft.Colors.WHITE70,
    )
    menu_import_button = ft.FilledButton(
        _t("import_button"),
        icon=ft.Icons.DOWNLOAD,
        on_click=import_playlist,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            bgcolor=colors["primary"],
            color=ft.Colors.WHITE,
        ),
    )
    menu_queue_button = ft.OutlinedButton(
        _t("queue_button"),
        icon=ft.Icons.PLAYLIST_ADD,
        on_click=lambda _e: queue_selected(),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            color=ft.Colors.WHITE,
        ),
    )
    choose_folder_button = ft.OutlinedButton(
        _t("choose_folder"),
        icon=ft.Icons.FOLDER_OPEN,
        on_click=choose_ipod_root,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            color=ft.Colors.WHITE,
        ),
    )
    download_button = ft.FilledButton(
        _t("download_button"),
        icon=ft.Icons.DOWNLOAD,
        on_click=lambda _e: download_selected(),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            bgcolor=colors["primary"],
            color=ft.Colors.WHITE,
        ),
    )
    sync_button = ft.FilledButton(
        _t("download_and_sync"),
        icon=ft.Icons.SYNC,
        on_click=lambda _e: sync_selected(),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            bgcolor=colors["primary_soft"],
            color=ft.Colors.WHITE,
        ),
    )

    menu_title_text = ft.Text(_t("menu_title"), size=15, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE)
    menu_help_text = ft.Text(_t("menu_help"), color=colors["muted"], size=11)
    screen_subtitle_text = ft.Text(_t("screen_subtitle"), color=colors["muted"], size=11)

    def apply_language() -> None:
        search_bar.hint_text = _t("search_hint")
        playlist_url_field.hint_text = _t("playlist_hint")
        ipod_root_field.hint_text = _t("ipod_root_hint")
        language_dropdown.label = _t("language_label")
        menu_title_text.value = _t("menu_title")
        menu_help_text.value = _t("menu_help")
        screen_subtitle_text.value = _t("screen_subtitle")
        menu_paste_button.tooltip = _t("paste_tooltip")
        menu_import_button.text = _t("import_button")
        menu_queue_button.text = _t("queue_button")
        choose_folder_button.text = _t("choose_folder")
        download_button.text = _t("download_button")
        sync_button.text = _t("download_and_sync")
        status_bar.value = _t(status_state["key"], **status_state["kwargs"])

    control_card = ft.Container(
        expand=True,
        padding=16,
        border_radius=22,
        bgcolor=colors["surface"],
        border=_border(colors["border"], 1),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=18, color="#00000033", offset=ft.Offset(0, 8)),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            width=46,
                            height=46,
                            border_radius=14,
                            bgcolor="#0c1520",
                            alignment=ft.Alignment(0, 0),
                            content=ft.Image(src="logo.png", width=24, height=24, fit=ft.BoxFit.CONTAIN),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text("NanoSync", size=20, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                                screen_subtitle_text,
                            ],
                            spacing=0,
                            tight=True,
                            expand=True,
                        ),
                        queue_count_text,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                menu_title_text,
                menu_help_text,
                ft.Container(
                    padding=12,
                    border_radius=18,
                    bgcolor=colors["background_alt"],
                    content=ft.Column(
                        controls=[
                            search_bar,
                            ft.Row(
                                controls=[playlist_url_field, menu_paste_button],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Row(
                                controls=[ipod_root_field, choose_folder_button],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Row(
                                controls=[download_button, sync_button, menu_import_button, menu_queue_button],
                                spacing=8,
                                wrap=True,
                            ),
                            language_dropdown,
                        ],
                        spacing=10,
                    ),
                ),
            ],
            spacing=12,
        ),
    )

    results_header = ft.Row(
        controls=[
            ft.Text("Library", size=18, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
            result_count_text,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    results_card = ft.Container(
        expand=True,
        padding=16,
        border_radius=22,
        bgcolor=colors["surface"],
        border=_border(colors["border"], 1),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=18, color="#00000033", offset=ft.Offset(0, 8)),
        content=ft.Column(
            controls=[results_header, ft.Container(expand=True, content=result_list)],
            spacing=12,
            expand=True,
        ),
    )

    def build_body() -> ft.Control:
        if _is_mobile_platform(page):
            return ft.Column(
                controls=[control_card, results_card, status_bar],
                spacing=16,
                expand=True,
            )

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(width=400, content=control_card),
                        ft.Container(expand=True, content=results_card),
                    ],
                    spacing=16,
                    expand=True,
                ),
                status_bar,
            ],
            spacing=12,
            expand=True,
        )

    def refresh_results() -> None:
        result_list.controls.clear()
        if current_results:
            result_count_text.value = _t("results_found", count=len(current_results))
            result_list.controls.extend(
                build_media_card(
                    item,
                    colors,
                    selected=index == selected_index,
                    on_select=lambda _e, idx=index: select_result(idx),
                    on_queue=lambda _e, idx=index: queue_selected(idx),
                    on_download=lambda _e, idx=index: download_selected(idx),
                    on_sync=lambda _e, idx=index: sync_selected(idx),
                )
                for index, item in enumerate(current_results)
            )
        else:
            result_count_text.value = _t("no_results")
            result_list.controls.append(build_placeholder_card())
        page.update()

    apply_language()

    header_glow = ft.Container(
        right=-120,
        top=-120,
        width=260,
        height=260,
        border_radius=130,
        bgcolor="#1db95422",
    )
    footer_glow = ft.Container(
        left=-60,
        bottom=-120,
        width=180,
        height=180,
        border_radius=90,
        bgcolor="#5b9cff18",
    )

    root = ft.SafeArea(
        content=ft.Container(
            expand=True,
            padding=16,
            alignment=ft.Alignment(0, 0),
            content=ft.Stack(
                expand=True,
                controls=[
                    ft.Container(
                        expand=True,
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, -1),
                            end=ft.Alignment(1, 1),
                            colors=[colors["background"], colors["background_alt"], "#050a12"],
                        ),
                    ),
                    header_glow,
                    footer_glow,
                    ft.Container(
                        expand=True,
                        padding=0,
                        content=ft.Container(
                            constraints=ft.BoxConstraints(max_width=1200),
                            alignment=ft.Alignment(0, 0),
                            content=build_body(),
                        ),
                    ),
                ],
            ),
        )
    )

    page.add(root)
    refresh_results()
    page.update()


def launch_gui() -> None:
    _ensure_logo_ico()
    ft.app(target=main, assets_dir=str(assets_root))


if __name__ == "__main__":
    launch_gui()
