# iPodify - Projektstatus

## Leitlinie
Die Idee von iPodify ist klar: Aus einer Quelle wird ein passendes Audio-Produkt erstellt und in ein iPod-taugliches Zielsystem gebracht. Der rote Faden lautet deshalb: Inhalt finden → verarbeiten → organisieren → abspielen.

## Aktueller Stand
- Audio-Downloads werden über `yt-dlp` realisiert.
- Downloads werden in MP3 umgewandelt und für den späteren Sync vorbereitet.
- Die Pipeline ist in `nanosync/pipeline.py` organisiert.
- Eine Desktop-GUI steht zur Verfügung und wird weiter vereinfacht.
- Ein Android-Build ist bereits als Skript angelegt.
- Die Testabdeckung wächst für Pipeline und GUI weiter.

## Was bereits umgesetzt ist
- YouTube-Audio-Download mit `yt-dlp`
- MP3-Konvertierung mit `ffmpeg`
- Sync in den `Music/`-Ordner plus lokale `nanosync.db`
- Desktop-GUI mit Flet
- Android APK-Build mit `build_android.bat`
- Tests im `tests/`-Ordner
- UI-Überarbeitung mit iPod-inspiriertem Layout und Sprachwahl

## Nächste Entwicklungsstufen
1. Aufbau einer stabilen Basis für Download, Konvertierung und Sync.
2. Vereinfachung der Bedienung über GUI und CLI.
3. Erweiterung um echte iPod-Transfer- und Organisierungslogik.
4. Ausbau auf mobile Nutzung und Android-Workflow.

## Wichtige Befehle
- `pip install -r requirements.txt`
- `python main.py convert <source> <output.mp3>`
- `python main.py download <youtube-url> <output.mp3>`
- `python main.py sync <source.mp3> <ipod-root>`
- `python gui.py`
- `pytest -q tests/test_pipeline.py tests/test_gui.py`
- `build_android.bat`

## Projektstruktur
- `main.py` – CLI
- `gui.py` – GUI-Startpunkt
- `nanosync/` – Kernlogik
- `tests/` – automatische Tests
- `assets/` – UI-Elemente
- `android_dist/` – APK-Ausgabe

## Aktueller Fokus
Der nächste Schritt ist die Verfestigung des lokalen Workflows und danach die echte iPod-Nano-Synchronisation mit einem sauberen Transfer- und Fehlerhandling.
