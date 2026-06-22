from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

workspace_root = Path(__file__).resolve().parents[1]
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
    {"title": "Dreams", "artist": "Fleetwood Mac", "source": "youtube", "url": "https://youtube.com/watch?v=example3"},
    {"title": "Around The World", "artist": "Daft Punk", "source": "youtube", "url": "https://youtube.com/watch?v=example4"},
    {"title": "Lose Yourself", "artist": "Eminem", "source": "youtube", "url": "https://youtube.com/watch?v=example5"},
    {"title": "Under Pressure", "artist": "Queen", "source": "youtube", "url": "https://youtube.com/watch?v=example6"},
    {"title": "Viva La Vida", "artist": "Coldplay", "source": "youtube", "url": "https://youtube.com/watch?v=example7"},
]
SEARCH_CACHE: dict[str, list[dict[str, str]]] = {}
MAX_CACHE_SIZE = 48


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
        items.append({"title": title, "artist": artist, "source": source_label, "url": url})
    return items


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name)
    return cleaned.strip("_")[:64] or "track"


def _accent_from_title(title: str) -> str:
    palette = ["#22d3ee", "#34d399", "#f59e0b", "#60a5fa", "#f472b6", "#a78bfa"]
    return palette[sum(ord(ch) for ch in title) % len(palette)]


def search_music_results(query: str) -> list[dict[str, str]]:
    normalized = (query or "").strip().lower()
    if not normalized:
        return _fallback_items(normalized, limit=9)

    if len(normalized) < 2:
        return _fallback_items(normalized, limit=9)

    cached = SEARCH_CACHE.get(normalized)
    if cached is not None:
        return cached.copy()

    fallback_items = _fallback_items(normalized, limit=9)
    if yt_dlp is None:
        return _cache_result(normalized, fallback_items)

    try:
        if hasattr(yt_dlp, "YoutubeDL"):
            ydl_opts = {
                "skip_download": True,
                "extract_flat": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 6,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch8:{normalized}", download=False)

            items: list[dict[str, str]] = []
            entries = info.get("entries") if isinstance(info, dict) else []
            if isinstance(info, dict) and info.get("_type") == "playlist" and entries:
                for entry in entries[:8]:
                    items.extend(_items_from_payload(entry))
                if items:
                    return _cache_result(normalized, items)

            if isinstance(info, dict) and info.get("title"):
                payload_items = _items_from_payload(info)
                if payload_items:
                    return _cache_result(normalized, payload_items)

            if entries:
                for entry in entries[:8]:
                    items.extend(_items_from_payload(entry))
                if items:
                    return _cache_result(normalized, items)
    except Exception:
        pass

    if not (local_yt_dlp / "yt_dlp").exists():
        return _cache_result(normalized, fallback_items)

    try:
        result = subprocess.run(
            [sys.executable, str(local_yt_dlp / "yt_dlp" / "__main__.py"), "--skip-download", "--print", "json", f"ytsearch8:{normalized}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=6,
        )
    except Exception:
        return _cache_result(normalized, fallback_items)

    if result.returncode == 0 and result.stdout.strip():
        items: list[dict[str, str]] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            items.extend(_items_from_payload(payload))
        if items:
            return _cache_result(normalized, items)

    return _cache_result(normalized, fallback_items)


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


def build_app() -> Any:
    try:
        import tkinter as tk
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("tkinter is not available in this Python installation") from exc

    root = tk.Tk()
    root.title("NanoSync - Professional Media Center")
    root.geometry("1120x760")
    root.minsize(900, 620)
    root.configure(bg="#080f22")

    colors = {
        "bg": "#080f22",
        "panel": "#101c39",
        "panel_soft": "#15264b",
        "panel_card": "#192d54",
        "text_primary": "#f7fbff",
        "text_secondary": "#9bb0d7",
        "accent": "#25d9a9",
        "accent_alt": "#3ba4ff",
    }

    shell = tk.Frame(root, bg=colors["bg"])
    shell.pack(fill="both", expand=True, padx=16, pady=14)

    header = tk.Frame(shell, bg=colors["panel"])
    header.pack(fill="x")
    tk.Label(
        header,
        text="NanoSync",
        fg=colors["text_primary"],
        bg=colors["panel"],
        font=("Bahnschrift", 30, "bold"),
    ).pack(side="left", padx=18, pady=14)

    device_card = tk.Frame(header, bg=colors["panel_soft"])
    device_card.pack(side="right", padx=18, pady=12)
    tk.Label(
        device_card,
        text="iPod Nano 6G verbunden",
        fg=colors["text_primary"],
        bg=colors["panel_soft"],
        font=("Bahnschrift", 12, "bold"),
    ).pack(anchor="w", padx=12, pady=(8, 2))
    tk.Label(
        device_card,
        text="12.8 GB / 16 GB frei",
        fg=colors["text_secondary"],
        bg=colors["panel_soft"],
        font=("Segoe UI", 10),
    ).pack(anchor="w", padx=12, pady=(0, 6))
    capacity_bar = tk.Canvas(device_card, width=260, height=10, bg=colors["panel_soft"], highlightthickness=0)
    capacity_bar.pack(padx=12, pady=(0, 10))
    capacity_bar.create_rectangle(0, 1, 258, 9, fill="#253a66", outline="")
    capacity_bar.create_rectangle(0, 1, 205, 9, fill=colors["accent"], outline="")

    search_zone = tk.Frame(shell, bg=colors["panel"])
    search_zone.pack(fill="x", pady=(10, 10))
    tk.Label(
        search_zone,
        text="Schnellsuche",
        fg=colors["text_secondary"],
        bg=colors["panel"],
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", padx=16, pady=(10, 4))
    entry = tk.Entry(
        search_zone,
        font=("Segoe UI", 14),
        relief="flat",
        bg="#1a2e58",
        fg=colors["text_primary"],
        insertbackground=colors["text_primary"],
    )
    entry.pack(fill="x", padx=16, pady=(0, 10), ipady=8)

    content = tk.Frame(shell, bg=colors["bg"])
    content.pack(fill="both", expand=True)

    board = tk.Frame(content, bg=colors["panel"])
    board.pack(fill="both", expand=True)

    canvas = tk.Canvas(board, bg=colors["panel"], highlightthickness=0)
    scrollbar = tk.Scrollbar(board, orient="vertical", command=canvas.yview)
    cards_container = tk.Frame(canvas, bg=colors["panel"])

    cards_window = canvas.create_window((0, 0), window=cards_container, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    footer = tk.Frame(shell, bg=colors["panel"])
    footer.pack(fill="x", pady=(10, 0))

    selected_text = tk.StringVar(value="Kein Track ausgewählt")
    status = tk.StringVar(value="Bereit")
    tk.Label(
        footer,
        textvariable=selected_text,
        fg=colors["text_secondary"],
        bg=colors["panel"],
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", padx=16, pady=(8, 2))
    tk.Label(
        footer,
        textvariable=status,
        fg=colors["text_primary"],
        bg=colors["panel"],
        anchor="w",
        font=("Segoe UI", 10),
    ).pack(fill="x", padx=16, pady=(0, 8))

    controls = tk.Frame(footer, bg=colors["panel"])
    controls.pack(fill="x", padx=16, pady=(0, 12))

    selected_item: dict[str, str] | None = None
    search_generation = 0
    pending_search_id: str | None = None
    current_results: list[dict[str, str]] = []

    def set_status(message: str) -> None:
        status.set(message)

    def set_selected(item: dict[str, str]) -> None:
        nonlocal selected_item
        selected_item = item
        selected_text.set(f"Ausgewählt: {item['title']} - {item['artist']}")

    def handle_download(item: dict[str, str]) -> None:
        url = item.get("url", "")
        if not url or url.startswith("local://"):
            set_status("Dieser Eintrag hat keine YouTube-URL")
            return

        target = workspace_root / "downloads" / f"{_safe_filename(item['title'])}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        set_status(f"Lade herunter: {item['title']}")

        def worker() -> None:
            try:
                message = perform_pipeline_action("download", url=url, target=str(target))
            except Exception as exc:
                message = str(exc)
            root.after(0, lambda: set_status(message))

        threading.Thread(target=worker, daemon=True).start()

    def handle_sync_selected() -> None:
        if not selected_item:
            set_status("Bitte zuerst einen Track auswählen")
            return

        source = workspace_root / "downloads" / f"{_safe_filename(selected_item['title'])}.mp4"
        if not source.exists():
            set_status("Bitte den Track zuerst herunterladen")
            return

        ipod_root = workspace_root / "tmp_ipod"
        set_status("Synchronisierung läuft...")

        def worker() -> None:
            try:
                message = perform_pipeline_action(
                    "sync",
                    source=str(source),
                    ipod_root=str(ipod_root),
                    title=_safe_filename(selected_item["title"]),
                )
            except Exception as exc:
                message = str(exc)
            root.after(0, lambda: set_status(message))

        threading.Thread(target=worker, daemon=True).start()

    def handle_download_and_sync() -> None:
        if not selected_item:
            set_status("Bitte zuerst einen Track auswählen")
            return

        item = selected_item
        target = workspace_root / "downloads" / f"{_safe_filename(item['title'])}.mp4"
        ipod_root = workspace_root / "tmp_ipod"
        target.parent.mkdir(parents=True, exist_ok=True)
        set_status("Download & Sync gestartet...")

        def worker() -> None:
            try:
                download_msg = perform_pipeline_action("download", url=item.get("url", ""), target=str(target))
                if "failed" in download_msg.lower():
                    message = download_msg
                else:
                    message = perform_pipeline_action(
                        "sync",
                        source=str(target),
                        ipod_root=str(ipod_root),
                        title=_safe_filename(item["title"]),
                    )
            except Exception as exc:
                message = str(exc)
            root.after(0, lambda: set_status(message))

        threading.Thread(target=worker, daemon=True).start()

    def render_cards(results: list[dict[str, str]]) -> None:
        for child in cards_container.winfo_children():
            child.destroy()

        if not results:
            tk.Label(
                cards_container,
                text="Keine Treffer",
                fg=colors["text_secondary"],
                bg=colors["panel"],
                font=("Segoe UI", 12),
            ).grid(row=0, column=0, padx=20, pady=20, sticky="w")
            return

        width = max(canvas.winfo_width(), 880)
        columns = 3 if width >= 1000 else 2 if width >= 660 else 1
        for col in range(columns):
            cards_container.grid_columnconfigure(col, weight=1, uniform="cards")

        for idx, item in enumerate(results):
            row = idx // columns
            col = idx % columns
            card = tk.Frame(cards_container, bg=colors["panel_card"], highlightthickness=1, highlightbackground="#243b69")
            card.grid(row=row, column=col, padx=9, pady=9, sticky="nsew")

            thumb = tk.Canvas(card, width=64, height=64, bg=colors["panel_card"], highlightthickness=0)
            thumb.grid(row=0, column=0, rowspan=3, padx=(10, 10), pady=10)
            accent = _accent_from_title(item["title"])
            thumb.create_rectangle(2, 2, 62, 62, fill=accent, outline="")
            thumb.create_text(32, 32, text=item["title"][:1].upper(), fill="#04122f", font=("Segoe UI", 18, "bold"))

            tk.Label(
                card,
                text=item["title"],
                fg=colors["text_primary"],
                bg=colors["panel_card"],
                anchor="w",
                font=("Segoe UI", 12, "bold"),
            ).grid(row=0, column=1, sticky="w", pady=(12, 0))
            tk.Label(
                card,
                text=item["artist"],
                fg=colors["text_secondary"],
                bg=colors["panel_card"],
                anchor="w",
                font=("Segoe UI", 10),
            ).grid(row=1, column=1, sticky="w")
            tk.Label(
                card,
                text=f"Quelle: {item['source']}",
                fg="#7fd4f6",
                bg=colors["panel_card"],
                anchor="w",
                font=("Segoe UI", 9),
            ).grid(row=2, column=1, sticky="w", pady=(0, 10))

            action_box = tk.Frame(card, bg=colors["panel_card"])
            action_box.grid(row=0, column=2, rowspan=3, padx=(8, 10), pady=10)
            tk.Button(
                action_box,
                text="Select",
                command=lambda it=item: set_selected(it),
                relief="flat",
                bg="#294578",
                fg=colors["text_primary"],
                padx=10,
                pady=4,
            ).pack(fill="x", pady=(0, 6))
            tk.Button(
                action_box,
                text="Download",
                command=lambda it=item: handle_download(it),
                relief="flat",
                bg=colors["accent_alt"],
                fg=colors["text_primary"],
                padx=10,
                pady=4,
            ).pack(fill="x")

    def apply_results(query: str, results: list[dict[str, str]], generation: int) -> None:
        nonlocal current_results
        if generation != search_generation:
            return
        current_results = results
        render_cards(results)
        set_status(f"{len(results)} Treffer für '{query}'" if results else f"Keine Treffer für '{query}'")

    def start_search(query: str, generation: int) -> None:
        nonlocal pending_search_id
        pending_search_id = None

        def worker() -> None:
            results = safe_search_results(query)
            root.after(0, lambda: apply_results(query, results, generation))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_results(*_args: Any) -> None:
        nonlocal search_generation, pending_search_id
        query = entry.get().strip()

        if pending_search_id is not None:
            try:
                root.after_cancel(pending_search_id)
            except Exception:
                pass
            pending_search_id = None

        search_generation += 1
        generation = search_generation

        if not query:
            suggestions = _filter_sample_items("", limit=9)
            apply_results("Empfehlungen", suggestions, generation)
            return

        if len(query) < 2:
            quick_results = _filter_sample_items(query.lower(), limit=9)
            apply_results(query, quick_results, generation)
            set_status("Tippe mindestens 2 Zeichen für Live-YouTube-Suche")
            return

        set_status("Suche läuft...")
        pending_search_id = root.after(190, lambda: start_search(query, generation))

    def _sync_canvas_width(event: Any) -> None:
        canvas.itemconfigure(cards_window, width=event.width)
        render_cards(current_results)

    cards_container.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", _sync_canvas_width)

    tk.Button(
        controls,
        text="Sync To iPod",
        command=handle_sync_selected,
        relief="flat",
        bg=colors["accent"],
        fg="#06212a",
        padx=18,
        pady=8,
        font=("Segoe UI", 10, "bold"),
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        controls,
        text="Download & Sync",
        command=handle_download_and_sync,
        relief="flat",
        bg=colors["accent_alt"],
        fg=colors["text_primary"],
        padx=18,
        pady=8,
        font=("Segoe UI", 10, "bold"),
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        controls,
        text="Manage Library",
        command=lambda: set_status("Library-Management folgt als nächster Schritt"),
        relief="flat",
        bg="#2a3c66",
        fg=colors["text_primary"],
        padx=18,
        pady=8,
        font=("Segoe UI", 10),
    ).pack(side="left")

    entry.bind("<KeyRelease>", refresh_results)
    refresh_results()
    return root


def launch_gui() -> None:
    app = build_app()
    app.mainloop()
