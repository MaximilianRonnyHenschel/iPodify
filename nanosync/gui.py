from __future__ import annotations

import asyncio
import inspect
import json
import struct
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from typing import Any

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

# --- Data Handling & Business Logic ---

SAMPLE_ITEMS = [
    {"title": "Bohemian Rhapsody", "artist": "Queen", "source": "youtube", "url": "https://youtube.com/watch?v=example1"},
    {"title": "Another One Bites the Dust", "artist": "Queen", "source": "youtube", "url": "https://youtube.com/watch?v=example2"},
    {"title": "Imagine", "artist": "John Lennon", "source": "local", "url": "local://imagine"},
]
SEARCH_CACHE: dict[str, list[dict[str, str]]] = {}
MAX_CACHE_SIZE = 48
DOWNLOAD_QUEUE = []

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
        "menu_title": "Suche & Import",
        "menu_help": "Das Menü blendet sich ein, damit die Listenfläche frei bleibt.",
        "import_button": "Playlist importieren",
        "queue_button": "Einreihen",
        "download_button": "Herunterladen",
        "language_label": "Sprache",
        "screen_subtitle": "Listenansicht · Playlists · Oldschool",
        "no_results": "Keine Treffer",
        "no_results_hint": "Suche in der Bibliothek oder füge eine Playlist-URL ein.",
        "results_found": "{count} Treffer gefunden.",
        "selected_prefix": "Ausgewählt: {title}",
        "no_item_queue": "Nichts zum Einreihen.",
        "no_item_download": "Nichts zum Herunterladen.",
        "invalid_url": "Ungültige URL für {title}",
        "queued_added": "Zur Warteschlange hinzugefügt: {title}",
        "playlist_url_prompt": "Bitte eine YouTube-Playlist-URL einfügen.",
        "start_playlist_import": "Importiere Playlist: {name}...",
        "playlist_imported": "Playlist importiert: {name}",
        "start_download": "Herunterladen: {title}...",
        "download_complete": "Heruntergeladen: {name}",
        "clipboard_empty": "Zwischenablage ist leer.",
        "clipboard_pasted": "Zwischenablage eingefügt.",
        "error": "Fehler: {message}",
        "paste_tooltip": "Aus Zwischenablage einfügen",
        "menu_tooltip": "Menü",
        "previous_tooltip": "Vorheriges",
        "next_tooltip": "Nächstes",
        "download_selected_tooltip": "Auswahl herunterladen",
    },
    "en": {
        "ready": "Ready",
        "search_hint": "Search the library",
        "playlist_hint": "YouTube playlist URL",
        "menu_title": "Search & Import",
        "menu_help": "The menu hides so the list area stays clear.",
        "import_button": "Import playlist",
        "queue_button": "Queue",
        "download_button": "Download",
        "language_label": "Language",
        "screen_subtitle": "List view · Playlists · Old school",
        "no_results": "No results",
        "no_results_hint": "Search the library or paste a playlist URL.",
        "results_found": "{count} results found.",
        "selected_prefix": "Selected: {title}",
        "no_item_queue": "Nothing to add to the list.",
        "no_item_download": "Nothing to download.",
        "invalid_url": "Invalid URL for {title}",
        "queued_added": "Added to queue: {title}",
        "playlist_url_prompt": "Please paste a YouTube playlist URL.",
        "start_playlist_import": "Importing playlist: {name}...",
        "playlist_imported": "Playlist imported: {name}",
        "start_download": "Downloading: {title}...",
        "download_complete": "Downloaded: {name}",
        "clipboard_empty": "Clipboard is empty.",
        "clipboard_pasted": "Pasted from clipboard.",
        "error": "Error: {message}",
        "paste_tooltip": "Paste from clipboard",
        "menu_tooltip": "Menu",
        "previous_tooltip": "Previous",
        "next_tooltip": "Next",
        "download_selected_tooltip": "Download selected",
    },
    "fr": {
        "ready": "Prêt",
        "search_hint": "Rechercher la bibliothèque",
        "playlist_hint": "URL de playlist YouTube",
        "menu_title": "Recherche et import",
        "menu_help": "Le menu se masque pour libérer la zone de liste.",
        "import_button": "Importer la playlist",
        "queue_button": "Ajouter à la liste",
        "download_button": "Télécharger",
        "language_label": "Langue",
        "screen_subtitle": "Vue liste · Playlists · Old school",
        "no_results": "Aucun résultat",
        "no_results_hint": "Recherchez dans la bibliothèque ou collez une URL de playlist.",
        "results_found": "{count} résultats trouvés.",
        "selected_prefix": "Sélectionné : {title}",
        "no_item_queue": "Rien à ajouter à la liste.",
        "no_item_download": "Rien à télécharger.",
        "invalid_url": "URL invalide pour {title}",
        "queued_added": "Ajouté à la file : {title}",
        "playlist_url_prompt": "Collez une URL de playlist YouTube.",
        "start_playlist_import": "Import de la playlist : {name}...",
        "playlist_imported": "Playlist importée : {name}",
        "start_download": "Téléchargement : {title}...",
        "download_complete": "Téléchargé : {name}",
        "clipboard_empty": "Le presse-papiers est vide.",
        "clipboard_pasted": "Collé depuis le presse-papiers.",
        "error": "Erreur : {message}",
        "paste_tooltip": "Coller depuis le presse-papiers",
        "menu_tooltip": "Menu",
        "previous_tooltip": "Précédent",
        "next_tooltip": "Suivant",
        "download_selected_tooltip": "Télécharger la sélection",
    },
    "es": {
        "ready": "Listo",
        "search_hint": "Buscar en la biblioteca",
        "playlist_hint": "URL de playlist de YouTube",
        "menu_title": "Búsqueda e importación",
        "menu_help": "El menú se oculta para dejar libre la vista de lista.",
        "import_button": "Importar playlist",
        "queue_button": "Añadir a la lista",
        "download_button": "Descargar",
        "language_label": "Idioma",
        "screen_subtitle": "Vista de lista · Playlists · Old school",
        "no_results": "Sin resultados",
        "no_results_hint": "Busca en la biblioteca o pega una URL de playlist.",
        "results_found": "{count} resultados encontrados.",
        "selected_prefix": "Seleccionado: {title}",
        "no_item_queue": "Nada para añadir a la lista.",
        "no_item_download": "Nada que descargar.",
        "invalid_url": "URL no válida para {title}",
        "queued_added": "Añadido a la cola: {title}",
        "playlist_url_prompt": "Pega una URL de playlist de YouTube.",
        "start_playlist_import": "Importando playlist: {name}...",
        "playlist_imported": "Playlist importada: {name}",
        "start_download": "Descargando: {title}...",
        "download_complete": "Descargado: {name}",
        "clipboard_empty": "El portapapeles está vacío.",
        "clipboard_pasted": "Pegado desde el portapapeles.",
        "error": "Error: {message}",
        "paste_tooltip": "Pegar desde el portapapeles",
        "menu_tooltip": "Menú",
        "previous_tooltip": "Anterior",
        "next_tooltip": "Siguiente",
        "download_selected_tooltip": "Descargar selección",
    },
    "it": {
        "ready": "Pronto",
        "search_hint": "Cerca nella libreria",
        "playlist_hint": "URL playlist YouTube",
        "menu_title": "Ricerca e importazione",
        "menu_help": "Il menu si nasconde per lasciare libera la vista elenco.",
        "import_button": "Importa playlist",
        "queue_button": "Aggiungi alla lista",
        "download_button": "Scarica",
        "language_label": "Lingua",
        "screen_subtitle": "Vista elenco · Playlist · Old school",
        "no_results": "Nessun risultato",
        "no_results_hint": "Cerca nella libreria o incolla un URL di playlist.",
        "results_found": "{count} risultati trovati.",
        "selected_prefix": "Selezionato: {title}",
        "no_item_queue": "Niente da aggiungere alla lista.",
        "no_item_download": "Niente da scaricare.",
        "invalid_url": "URL non valida per {title}",
        "queued_added": "Aggiunto alla coda: {title}",
        "playlist_url_prompt": "Incolla un URL di playlist YouTube.",
        "start_playlist_import": "Importazione playlist: {name}...",
        "playlist_imported": "Playlist importata: {name}",
        "start_download": "Scaricamento: {title}...",
        "download_complete": "Scaricato: {name}",
        "clipboard_empty": "Gli appunti sono vuoti.",
        "clipboard_pasted": "Incollato dagli appunti.",
        "error": "Errore: {message}",
        "paste_tooltip": "Incolla dagli appunti",
        "menu_tooltip": "Menu",
        "previous_tooltip": "Precedente",
        "next_tooltip": "Successivo",
        "download_selected_tooltip": "Scarica selezione",
    },
    "nl": {
        "ready": "Klaar",
        "search_hint": "Bibliotheek doorzoeken",
        "playlist_hint": "YouTube-afspeellijst-URL",
        "menu_title": "Zoeken en importeren",
        "menu_help": "Het menu verbergt zich zodat de lijst vrij blijft.",
        "import_button": "Afspeellijst importeren",
        "queue_button": "Toevoegen aan lijst",
        "download_button": "Download",
        "language_label": "Taal",
        "screen_subtitle": "Lijstweergave · Afspeellijsten · Oldschool",
        "no_results": "Geen resultaten",
        "no_results_hint": "Zoek in de bibliotheek of plak een afspeellijst-URL.",
        "results_found": "{count} resultaten gevonden.",
        "selected_prefix": "Geselecteerd: {title}",
        "no_item_queue": "Niets om aan de lijst toe te voegen.",
        "no_item_download": "Niets om te downloaden.",
        "invalid_url": "Ongeldige URL voor {title}",
        "queued_added": "Toegevoegd aan wachtrij: {title}",
        "playlist_url_prompt": "Plak een YouTube-afspeellijst-URL.",
        "start_playlist_import": "Afspeellijst wordt geïmporteerd: {name}...",
        "playlist_imported": "Afspeellijst geïmporteerd: {name}",
        "start_download": "Bezig met downloaden: {title}...",
        "download_complete": "Gedownload: {name}",
        "clipboard_empty": "Het klembord is leeg.",
        "clipboard_pasted": "Geplakt vanuit klembord.",
        "error": "Fout: {message}",
        "paste_tooltip": "Plakken vanuit klembord",
        "menu_tooltip": "Menu",
        "previous_tooltip": "Vorige",
        "next_tooltip": "Volgende",
        "download_selected_tooltip": "Geselecteerde downloaden",
    },
    "pl": {
        "ready": "Gotowe",
        "search_hint": "Przeszukaj bibliotekę",
        "playlist_hint": "Adres listy odtwarzania YouTube",
        "menu_title": "Wyszukiwanie i import",
        "menu_help": "Menu ukrywa się, aby lista pozostała czytelna.",
        "import_button": "Importuj playlistę",
        "queue_button": "Dodaj do listy",
        "download_button": "Pobierz",
        "language_label": "Język",
        "screen_subtitle": "Widok listy · Playlisty · Oldschool",
        "no_results": "Brak wyników",
        "no_results_hint": "Szukaj w bibliotece lub wklej adres playlisty.",
        "results_found": "Znaleziono {count} wyników.",
        "selected_prefix": "Zaznaczono: {title}",
        "no_item_queue": "Nic do dodania do listy.",
        "no_item_download": "Nic do pobrania.",
        "invalid_url": "Nieprawidłowy adres URL dla {title}",
        "queued_added": "Dodano do kolejki: {title}",
        "playlist_url_prompt": "Wklej adres playlisty YouTube.",
        "start_playlist_import": "Import playlisty: {name}...",
        "playlist_imported": "Playlista zaimportowana: {name}",
        "start_download": "Pobieranie: {title}...",
        "download_complete": "Pobrano: {name}",
        "clipboard_empty": "Schowek jest pusty.",
        "clipboard_pasted": "Wklejono ze schowka.",
        "error": "Błąd: {message}",
        "paste_tooltip": "Wklej ze schowka",
        "menu_tooltip": "Menu",
        "previous_tooltip": "Poprzedni",
        "next_tooltip": "Następny",
        "download_selected_tooltip": "Pobierz zaznaczone",
    },
    "pt": {
        "ready": "Pronto",
        "search_hint": "Procurar na biblioteca",
        "playlist_hint": "URL da playlist do YouTube",
        "menu_title": "Pesquisa e importação",
        "menu_help": "O menu oculta-se para deixar a lista livre.",
        "import_button": "Importar playlist",
        "queue_button": "Adicionar à lista",
        "download_button": "Transferir",
        "language_label": "Idioma",
        "screen_subtitle": "Vista de lista · Playlists · Old school",
        "no_results": "Sem resultados",
        "no_results_hint": "Procura na biblioteca ou cola um URL de playlist.",
        "results_found": "{count} resultados encontrados.",
        "selected_prefix": "Selecionado: {title}",
        "no_item_queue": "Nada para adicionar à lista.",
        "no_item_download": "Nada para transferir.",
        "invalid_url": "URL inválido para {title}",
        "queued_added": "Adicionado à fila: {title}",
        "playlist_url_prompt": "Cola um URL de playlist do YouTube.",
        "start_playlist_import": "A importar playlist: {name}...",
        "playlist_imported": "Playlist importada: {name}",
        "start_download": "A transferir: {title}...",
        "download_complete": "Transferido: {name}",
        "clipboard_empty": "A área de transferência está vazia.",
        "clipboard_pasted": "Colado da área de transferência.",
        "error": "Erro: {message}",
        "paste_tooltip": "Colar da área de transferência",
        "menu_tooltip": "Menu",
        "previous_tooltip": "Anterior",
        "next_tooltip": "Seguinte",
        "download_selected_tooltip": "Transferir seleção",
    },
}


def _set_language(language_code: str) -> None:
    global CURRENT_LANGUAGE
    if language_code in TRANSLATIONS:
        CURRENT_LANGUAGE = language_code
    else:
        CURRENT_LANGUAGE = "de"


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
    if local_yt_dlp.exists() and (local_yt_dlp / "yt_dlp").exists():
        main_py = local_yt_dlp / "yt_dlp" / "__main__.py"
        if main_py.exists():
            return [sys.executable, str(main_py)]
    return [sys.executable, "-m", "yt_dlp"] if url_mode else [sys.executable, "-m", "yt_dlp"]


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
        target = sync_to_ipod(source, ipod_root, title=kwargs.get("title", "video"))
        return f"Sync completed: {target}"

    raise ValueError(f"Unsupported command: {command}")


def _download_target_for_item(item: dict[str, str]) -> Path:
    title = _safe_filename(item["title"])
    if item.get("kind") == "playlist":
        return workspace_root / "downloads" / title
    return workspace_root / "downloads" / f"{title}.mp4"


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
    # Windows ICO files can embed a PNG image directly.
    image_offset = 6 + 16
    width = struct.unpack(">I", png_bytes[16:20])[0] if len(png_bytes) >= 20 else 0
    height = struct.unpack(">I", png_bytes[20:24])[0] if len(png_bytes) >= 24 else 0
    width_byte = width if width < 256 else 0
    height_byte = height if height < 256 else 0
    header = struct.pack(
        "<HHHBBBBHHII",
        0,
        1,
        1,
        width_byte,
        height_byte,
        0,
        0,
        1,
        32,
        len(png_bytes),
        image_offset,
    )
    return header + png_bytes


def _ensure_logo_ico() -> Path | None:
    if not logo_png_path.exists():
        return None

    try:
        png_mtime = logo_png_path.stat().st_mtime
        if not logo_ico_path.exists() or logo_ico_path.stat().st_mtime < png_mtime:
            logo_ico_path.write_bytes(_png_to_ico_bytes(logo_png_path.read_bytes()))
    except Exception:
        return None

    return logo_ico_path


def _apply_window_icon(page: ft.Page) -> None:
    icon_path = _ensure_logo_ico()
    window = getattr(page, "window", None)
    if icon_path is None or window is None:
        return

    try:
        window.icon = str(icon_path)
    except Exception:
        pass


def _configure_window(page: ft.Page, colors: dict[str, str]) -> None:
    window = getattr(page, "window", None)
    if window is None:
        return

    try:
        page.padding = 0
    except Exception:
        pass

    try:
        page.spacing = 0
    except Exception:
        pass

    for attr, value in (
        ("width", IPOD_STAGE_WIDTH),
        ("height", IPOD_STAGE_HEIGHT),
        ("min_width", IPOD_STAGE_WIDTH),
        ("min_height", IPOD_STAGE_HEIGHT),
        ("max_width", IPOD_STAGE_WIDTH),
        ("max_height", IPOD_STAGE_HEIGHT),
        ("frameless", True),
        ("title_bar_hidden", True),
        ("title_bar_buttons_hidden", True),
        ("resizable", False),
        ("minimizable", False),
        ("maximizable", False),
        ("movable", True),
        ("full_screen", False),
        ("bgcolor", colors["background"]),
        ("shadow", False),
    ):
        try:
            setattr(window, attr, value)
        except Exception:
            pass

    try:
        center_result = window.center()
        if inspect.isawaitable(center_result):
            async def _center_window() -> None:
                try:
                    await center_result
                except Exception:
                    pass

            runner = getattr(page, "run_task", None)
            if callable(runner):
                try:
                    runner(_center_window)
                    return
                except Exception:
                    pass

            try:
                asyncio.run(_center_window())
            except RuntimeError:
                try:
                    center_result.close()
                except Exception:
                    pass
    except Exception:
        pass

    try:
        window.update()
    except Exception:
        pass

    for attr, value in (
        ("window_width", IPOD_STAGE_WIDTH),
        ("window_height", IPOD_STAGE_HEIGHT),
        ("window_min_width", IPOD_STAGE_WIDTH),
        ("window_min_height", IPOD_STAGE_HEIGHT),
    ):
        try:
            setattr(page, attr, value)
        except Exception:
            pass


def _cover_source(item: dict[str, str]) -> str:
    return item.get("cover") or fallback_cover_src


def _source_display_label(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized in {"youtube", "yt"}:
        return "YouTube"
    if normalized == "local":
        return "Lokal"
    return normalized.capitalize() if normalized else "Unbekannt"


def _border(color: str, width: int = 1) -> ft.Border:
    side = ft.BorderSide(width=width, color=color)
    return ft.Border(left=side, top=side, right=side, bottom=side)


async def _read_clipboard_text(clipboard: Any) -> str:
    try:
        value = await clipboard.get()
    except Exception:
        return ""
    return str(value or "").strip()


IPOD_BODY_ASPECT_RATIO = 1.7641489844858633
IPOD_BODY_WIDTH = 520
IPOD_BODY_HEIGHT = int(round(IPOD_BODY_WIDTH * IPOD_BODY_ASPECT_RATIO))
IPOD_STAGE_WIDTH = IPOD_BODY_WIDTH
IPOD_STAGE_HEIGHT = IPOD_BODY_HEIGHT
IPOD_SCREEN_WIDTH = 488
IPOD_SCREEN_HEIGHT = 600
COVERFLOW_TILT = 0.46
COVERFLOW_SHIFT = 26
COVERFLOW_DROP = 9
COVERFLOW_SCALE = 0.20
IPOD_WHEEL_SIZE = 192
COVER_CARD_WIDTH = 252
COVER_CARD_HEIGHT = 206


def _coverflow_transform(relative_index: int) -> ft.Transform:
    if relative_index == 0:
        return ft.Transform(matrix=ft.Matrix4.identity())

    direction = -1 if relative_index < 0 else 1
    distance = min(abs(relative_index), 2)
    depth_multiplier = 1.0 if distance == 1 else 1.55
    tilt = COVERFLOW_TILT * direction * depth_multiplier
    shift = COVERFLOW_SHIFT * direction * depth_multiplier
    drop = COVERFLOW_DROP * depth_multiplier
    scale = max(0.62, 1.0 - (COVERFLOW_SCALE * depth_multiplier))
    matrix = (
        ft.Matrix4.identity()
        .rotate_y(tilt)
        .translate(shift, drop, 0)
        .scale(scale, scale, scale)
    )
    return ft.Transform(matrix=matrix)


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

    def do_download():
        try:
            message = perform_pipeline_action("download", url=url, target=str(target))
            status_bar.value = success_message if message.startswith("Download completed") else message
        except Exception as exc:
            status_bar.value = _t("error", message=exc)

        page.update()

    threading.Thread(target=do_download, daemon=True).start()


def _queue_item(item: dict[str, str], status_bar: ft.Text, page: ft.Page) -> None:
    DOWNLOAD_QUEUE.append(item)
    status_bar.value = _t("queued_added", title=item["title"])
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


# --- Flet UI ---

class MediaCard(ft.Container):
    def __init__(
        self,
        item: dict[str, str],
        colors: dict[str, str],
        status_bar: ft.Text,
        *,
        selected: bool = False,
        hovered: bool = False,
        key: str | None = None,
        on_select: Any | None = None,
        on_hover_change: Any | None = None,
    ):
        self.item = item
        self.colors = colors
        self.status_bar = status_bar
        self.selected = selected
        self.hovered = hovered
        self._hover_change = on_hover_change
        cover_source = _cover_source(item)
        source_label = _source_display_label(item.get("source", ""))
        subtitle_label = f"{item['artist']} · {source_label}"
        self._base_bgcolor = "#17181C"
        self._hover_bgcolor = "#1B1D22"
        self._selected_bgcolor = "#1A1F1D"
        self._base_border = "#24262B"
        self._hover_border = "#2E3238"
        self._selected_border = colors["primary"]
        self._base_shadow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=10,
            color="#00000028",
            offset=ft.Offset(0, 4),
        )
        self._hover_shadow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=12,
            color="#0000003A",
            offset=ft.Offset(0, 5),
        )
        self._selected_shadow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=14,
            color="#1DB95426" if selected else "#0000003A",
            offset=ft.Offset(0, 5),
        )
        self._thumbnail = ft.Container(
            width=76,
            height=76,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=11,
            bgcolor="#0D0D10",
            content=ft.Image(
                src=cover_source,
                fit=ft.BoxFit.COVER,
                expand=True,
                error_content=ft.Container(
                    alignment=ft.Alignment(0, 0),
                    bgcolor="#0D0D10",
                    content=ft.Icon(
                        ft.Icons.ALBUM,
                        color=colors["primary"],
                        size=30,
                    ),
                ),
            ),
        )
        self._title_text = ft.Text(
            item["title"],
            weight=ft.FontWeight.W_700,
            color=ft.Colors.WHITE,
            size=15,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self._subtitle_text = ft.Text(
            subtitle_label,
            color=ft.Colors.WHITE60,
            size=11,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self._text_column = ft.Column(
            controls=[
                self._title_text,
                self._subtitle_text,
            ],
            spacing=4,
            tight=True,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )
        self._queue_button = ft.IconButton(
            icon=ft.Icons.PLAYLIST_ADD,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            tooltip=_t("queue_button"),
            on_click=self.add_to_queue,
            bgcolor="#22252A",
            hover_color="#2B2F36",
            width=34,
            height=34,
            padding=0,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )
        self._download_button = ft.IconButton(
            icon=ft.Icons.DOWNLOAD,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            tooltip=_t("download_button"),
            on_click=self.download,
            bgcolor=colors["primary"],
            hover_color="#36C95B",
            width=34,
            height=34,
            padding=0,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )
        self._action_column = ft.Column(
            controls=[
                self._queue_button,
                self._download_button,
            ],
            spacing=6,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._row = ft.Row(
            controls=[
                self._thumbnail,
                ft.Container(
                    expand=True,
                    padding=ft.Padding(12, 4, 12, 4),
                    content=self._text_column,
                ),
                self._action_column,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            key=key,
            expand=True,
            height=96,
            padding=10,
            bgcolor=self._selected_bgcolor if selected else self._base_bgcolor,
            border=_border(self._selected_border if selected else self._base_border, 1),
            border_radius=12,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=self._selected_shadow if selected else self._base_shadow,
            on_hover=self._handle_hover,
            on_click=on_select,
            content=self._row,
        )
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        if self.hovered:
            self.bgcolor = self._hover_bgcolor
            self.border = _border(self._selected_border if self.selected else self._hover_border, 1)
            self.shadow = self._selected_shadow if self.selected else self._hover_shadow
            self._action_column.opacity = 1.0
        else:
            self.bgcolor = self._selected_bgcolor if self.selected else self._base_bgcolor
            self.border = _border(self._selected_border if self.selected else self._base_border, 1)
            self.shadow = self._selected_shadow if self.selected else self._base_shadow
            self._action_column.opacity = 0.96 if self.selected else 0.82

    def _handle_hover(self, e):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        if callable(self._hover_change):
            self._hover_change(hovered)

    def add_to_queue(self, e):
        _queue_item(self.item, self.status_bar, self.page)

    def download(self, e):
        _download_item(self.item, self.status_bar, self.page)


def main(page: ft.Page):
    _apply_window_icon(page)
    page.title = "iPodify"
    page.theme_mode = ft.ThemeMode.DARK

    colors = {
        "background": "#0B0B0D",
        "surface": "#121214",
        "primary": "#1DB954",
        "text": "#FFFFFF",
        "panel": "#202025",
    }
    _configure_window(page, colors)
    page.bgcolor = colors["background"]

    status_bar = ft.Text(_t("ready"), color=ft.Colors.WHITE54, size=11)
    result_count_text = ft.Text(_t("no_results"), color=ft.Colors.WHITE54, size=10)
    result_list = ft.ListView(
        expand=True,
        spacing=6,
        padding=0,
        build_controls_on_demand=True,
        item_extent=96,
    )
    current_results: list[dict[str, str]] = []
    selected_index = 0
    hovered_index = -1
    menu_open = False
    updating_results = False
    status_state: dict[str, Any] = {"key": "ready", "kwargs": {}}

    def selected_item() -> dict[str, str] | None:
        if not current_results:
            return None
        index = max(0, min(selected_index, len(current_results) - 1))
        return current_results[index]

    def build_placeholder_card() -> ft.Container:
        return ft.Container(
            height=96,
            expand=True,
            border_radius=12,
            padding=12,
            bgcolor="#111114",
            border=_border("#24262B"),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CIRCLE_OUTLINED, color=ft.Colors.WHITE54, size=26),
                    ft.Column(
                        controls=[
                            ft.Text(_t("no_results"), color=ft.Colors.WHITE, size=14, weight=ft.FontWeight.W_600),
                            ft.Text(_t("no_results_hint"), color=ft.Colors.WHITE54, size=10, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                        ],
                        spacing=2,
                        tight=True,
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def select_result(index: int, *, announce: bool = True) -> None:
        nonlocal selected_index

        if not current_results:
            return

        selected_index = max(0, min(index, len(current_results) - 1))
        if announce:
            set_status("selected_prefix", title=current_results[selected_index]["title"])
        render_results()

    def set_hovered_result(index: int, hovered: bool) -> None:
        nonlocal hovered_index

        if hovered:
            if hovered_index == index:
                return
            hovered_index = index
        elif hovered_index == index:
            hovered_index = -1
        else:
            return

        async def _refresh_hover() -> None:
            try:
                await asyncio.sleep(0)
            except Exception:
                pass
            render_results(scroll=False)

        runner = getattr(page, "run_task", None)
        if callable(runner):
            try:
                runner(_refresh_hover)
                return
            except Exception:
                pass

        render_results(scroll=False)

    def build_result_card(item: dict[str, str], index: int) -> MediaCard:
        return MediaCard(
            item,
            colors,
            status_bar,
            selected=index == selected_index,
            hovered=index == hovered_index,
            key=f"result-{index}",
            on_select=lambda _e, idx=index: select_result(idx),
            on_hover_change=lambda is_hovered, idx=index: set_hovered_result(idx, is_hovered),
        )

    def render_results(*, scroll: bool = True) -> None:
        nonlocal selected_index, hovered_index, updating_results

        if updating_results:
            return

        updating_results = True
        try:
            result_list.controls.clear()
            if current_results:
                selected_index = max(0, min(selected_index, len(current_results) - 1))
                hovered_index = hovered_index if 0 <= hovered_index < len(current_results) else -1
                result_count_text.value = _t("results_found", count=len(current_results))
                result_list.controls.extend(build_result_card(item, idx) for idx, item in enumerate(current_results))
            else:
                selected_index = 0
                hovered_index = -1
                result_count_text.value = _t("no_results")
                result_list.controls.append(build_placeholder_card())
            page.update()
        finally:
            updating_results = False

        if not current_results or not scroll:
            return

        async def _scroll_to_selected() -> None:
            try:
                await result_list.scroll_to(scroll_key=f"result-{selected_index}", duration=220)
            except Exception:
                pass

        runner = getattr(page, "run_task", None)
        if callable(runner):
            runner(_scroll_to_selected)

    def set_status(key: str, **kwargs: Any) -> None:
        status_state["key"] = key
        status_state["kwargs"] = kwargs
        status_bar.value = _t(key, **kwargs)
        page.update()

    def toggle_menu(_=None):
        nonlocal menu_open
        menu_open = not menu_open
        menu_panel.visible = menu_open
        page.update()

    def perform_search(e):
        nonlocal current_results, selected_index, hovered_index
        query = e.control.value or ""
        current_results = safe_search_results(query)
        selected_index = 0
        hovered_index = -1
        render_results()
        set_status("results_found", count=len(current_results))

    def move_cover(step: int):
        if not current_results:
            set_status("no_results")
            return

        select_result(selected_index + step)

    def queue_selected(_=None):
        item = selected_item()
        if item is None:
            set_status("no_item_queue")
            return

        _queue_item(item, status_bar, page)

    def download_selected(_=None):
        item = selected_item()
        if item is None:
            set_status("no_item_download")
            return

        _download_item(item, status_bar, page)

    def import_playlist(e):
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

    async def paste_playlist_from_clipboard(e):
        clipboard_text = await _read_clipboard_text(page.clipboard)
        if not clipboard_text:
            set_status("clipboard_empty")
            return

        playlist_url_field.value = clipboard_text
        set_status("clipboard_pasted")


    search_bar = ft.TextField(
        hint_text=_t('search_hint'),
        prefix_icon=ft.Icons.SEARCH,
        border_color='#2A2A30',
        bgcolor='#151519',
        border_radius=10,
        color=ft.Colors.WHITE,
        on_submit=perform_search,
        on_change=perform_search,
    )
    playlist_url_field = ft.TextField(
        hint_text=_t('playlist_hint'),
        border_color='#2A2A30',
        bgcolor='#151519',
        border_radius=10,
        color=ft.Colors.WHITE,
        expand=True,
    )

    screen_brand = ft.Row(
        controls=[
            ft.Image(src='logo.png', width=20, height=20, fit=ft.BoxFit.CONTAIN),
            ft.Text('iPodify', weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=14),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    menu_title_text = ft.Text(_t('menu_title'), size=11, color=ft.Colors.WHITE54)
    menu_help_text = ft.Text(_t('menu_help'), color=ft.Colors.WHITE54, size=10)
    screen_subtitle_text = ft.Text(_t('screen_subtitle'), color=ft.Colors.WHITE54, size=10)

    def set_language(e=None):
        selected_value = getattr(getattr(e, "control", None), "value", None) if e is not None else None
        _set_language((selected_value or language_dropdown.value or "de").strip())
        apply_language()
        render_results(scroll=False)

    language_dropdown = ft.Dropdown(
        value=CURRENT_LANGUAGE,
        label=_t('language_label'),
        options=[ft.dropdown.Option(code, label) for code, label in LANGUAGE_CHOICES],
        border_color='#2A2A30',
        bgcolor='#151519',
        border_radius=10,
        color=ft.Colors.WHITE,
        width=180,
        dense=True,
        on_select=set_language,
    )

    menu_paste_button = ft.IconButton(
        ft.Icons.PASTE,
        tooltip=_t('paste_tooltip'),
        on_click=paste_playlist_from_clipboard,
        icon_color=ft.Colors.WHITE70,
    )
    menu_import_button = ft.FilledButton(
        _t('import_button'),
        icon=ft.Icons.DOWNLOAD,
        on_click=import_playlist,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            bgcolor=colors['primary'],
            color=ft.Colors.WHITE,
        ),
    )
    menu_queue_button = ft.OutlinedButton(
        _t('queue_button'),
        icon=ft.Icons.PLAYLIST_ADD,
        on_click=queue_selected,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            color=ft.Colors.WHITE,
        ),
    )
    menu_toggle_button = ft.IconButton(
        ft.Icons.MENU,
        on_click=toggle_menu,
        icon_color=ft.Colors.WHITE,
        tooltip=_t('menu_tooltip'),
    )

    def apply_language():
        search_bar.hint_text = _t('search_hint')
        playlist_url_field.hint_text = _t('playlist_hint')
        menu_title_text.value = _t('menu_title')
        menu_help_text.value = _t('menu_help')
        screen_subtitle_text.value = _t('screen_subtitle')
        language_dropdown.label = _t('language_label')
        language_dropdown.value = CURRENT_LANGUAGE
        menu_paste_button.tooltip = _t('paste_tooltip')
        menu_import_button.text = _t('import_button')
        menu_queue_button.text = _t('queue_button')
        menu_toggle_button.tooltip = _t('menu_tooltip')
        wheel_menu_button.tooltip = _t('menu_tooltip')
        wheel_prev_button.tooltip = _t('previous_tooltip')
        wheel_next_button.tooltip = _t('next_tooltip')
        wheel_download_button.tooltip = _t('download_selected_tooltip')
        status_bar.value = _t(status_state['key'], **status_state['kwargs'])

    menu_panel = ft.Container(
        visible=False,
        animate_opacity=180,
        border_radius=14,
        bgcolor='#111114',
        border=_border('#303038'),
        padding=10,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[menu_title_text, language_dropdown],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                search_bar,
                ft.Row(
                    controls=[
                        playlist_url_field,
                        menu_paste_button,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[menu_import_button, menu_queue_button],
                    spacing=8,
                    wrap=True,
                ),
                menu_help_text,
            ],
            spacing=8,
        ),
        key='menu-panel',
    )

    screen_panel = ft.Container(
        width=IPOD_SCREEN_WIDTH,
        height=IPOD_SCREEN_HEIGHT,
        bgcolor='#050505',
        border_radius=30,
        border=_border('#37373D'),
        padding=4,
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=18, color='#00000077', offset=ft.Offset(0, 6)),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        menu_toggle_button,
                        ft.Column(
                            controls=[
                                screen_brand,
                                screen_subtitle_text,
                            ],
                            spacing=0,
                            expand=True,
                        ),
                        result_count_text,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                menu_panel,
                ft.Container(expand=True, content=result_list),
                status_bar,
            ],
            spacing=8,
            expand=True,
        ),
    )

    wheel_menu_button = ft.IconButton(
        ft.Icons.MENU,
        icon_color=ft.Colors.WHITE,
        icon_size=18,
        tooltip=_t('menu_tooltip'),
        on_click=toggle_menu,
    )
    wheel_prev_button = ft.IconButton(
        ft.Icons.KEYBOARD_ARROW_LEFT,
        icon_color=ft.Colors.WHITE,
        icon_size=20,
        tooltip=_t('previous_tooltip'),
        on_click=lambda _e: move_cover(-1),
    )
    wheel_next_button = ft.IconButton(
        ft.Icons.KEYBOARD_ARROW_RIGHT,
        icon_color=ft.Colors.WHITE,
        icon_size=20,
        tooltip=_t('next_tooltip'),
        on_click=lambda _e: move_cover(1),
    )
    wheel_download_button = ft.IconButton(
        ft.Icons.PLAY_ARROW,
        icon_color=ft.Colors.WHITE,
        icon_size=20,
        tooltip=_t('download_selected_tooltip'),
        on_click=download_selected,
    )

    apply_language()

    wheel_panel = ft.Container(
        width=IPOD_WHEEL_SIZE,
        height=IPOD_WHEEL_SIZE,
        shape=ft.BoxShape.CIRCLE,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        bgcolor='#0E0E10',
        border=_border('#736A61', 2),
        alignment=ft.Alignment(0, 0),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=24, color='#00000088', offset=ft.Offset(0, 8)),
        content=ft.Stack(
            controls=[
                ft.Container(
                    left=6,
                    top=6,
                    right=6,
                    bottom=6,
                    shape=ft.BoxShape.CIRCLE,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=['#1B1B1F', '#0A0A0B'],
                    ),
                ),
                ft.Container(
                    left=66,
                    top=10,
                    width=60,
                    height=32,
                    alignment=ft.Alignment(0, 0),
                    content=wheel_menu_button,
                ),
                ft.Container(
                    left=10,
                    top=72,
                    width=40,
                    height=44,
                    alignment=ft.Alignment(0, 0),
                    content=wheel_prev_button,
                ),
                ft.Container(
                    right=10,
                    top=72,
                    width=40,
                    height=44,
                    alignment=ft.Alignment(0, 0),
                    content=wheel_next_button,
                ),
                ft.Container(
                    left=60,
                    top=60,
                    width=72,
                    height=72,
                    shape=ft.BoxShape.CIRCLE,
                    bgcolor='#18181A',
                    border=_border('#7B7269', 1),
                    alignment=ft.Alignment(0, 0),
                    ink=True,
                    on_click=queue_selected,
                    content=ft.Icon(ft.Icons.PLAYLIST_ADD, color=ft.Colors.WHITE54, size=20),
                ),
                ft.Container(
                    left=67,
                    bottom=12,
                    width=58,
                    height=32,
                    alignment=ft.Alignment(0, 0),
                    content=wheel_download_button,
                ),
            ]
        ),
    )
    front_shell = ft.Container(
        width=IPOD_BODY_WIDTH,
        height=IPOD_BODY_HEIGHT,
        border_radius=56,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=["#F6F1E8", "#E0D5C7", "#B7AB9C"],
        ),
        padding=12,
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=34, color="#00000077", offset=ft.Offset(0, 16)),
        content=ft.Column(
            controls=[
                ft.WindowDragArea(
                    maximizable=False,
                    content=ft.Container(
                        height=14,
                        width=IPOD_BODY_WIDTH - 24,
                        bgcolor=ft.Colors.TRANSPARENT,
                    ),
                ),
                screen_panel,
                wheel_panel,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    back_cover = ft.Container(
        left=0,
        top=0,
        width=IPOD_BODY_WIDTH,
        height=IPOD_BODY_HEIGHT,
        opacity=0.11,
        content=ft.Image(src="3d/ipodminicover.png", fit=ft.BoxFit.CONTAIN),
    )

    device_stage = ft.Stack(
        width=IPOD_STAGE_WIDTH,
        height=IPOD_STAGE_HEIGHT,
        controls=[
            back_cover,
            ft.Container(
                left=0,
                top=0,
                width=IPOD_BODY_WIDTH,
                height=IPOD_BODY_HEIGHT,
                content=front_shell,
            ),
        ],
    )

    page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            padding=0,
            margin=0,
            bgcolor=colors["background"],
            content=device_stage,
        )
    )
    if search_bar.value is None:
        search_bar.value = ""
    perform_search(SimpleNamespace(control=search_bar))
    page.update()


def launch_gui():
    _ensure_logo_ico()
    ft.app(target=main, assets_dir=str(assets_root))
