# iPodify

iPodify ist ein lokales Werkzeug, das Inhalte aus dem Web aufnimmt, in Audio umwandelt und für einen iPod-ähnlichen Zielordner vorbereitet. Der rote Faden ist dabei einfach: Quelle → Verarbeitung → Zielordner.

## Ziel des Projekts
Das Projekt soll aus Medienquellen wie YouTube Audio-Items erzeugen, sauber aufbereiten und in ein strukturiertes Zielsystem bringen. Der Fokus liegt aktuell auf einem einfachen, nachvollziehbaren MP3-Workflow für lokale Nutzung und spätere Synchronisation auf ein iPod-ähnliches Gerät.

## So funktioniert der Ablauf
1. Inhalte werden über die CLI oder die GUI eingebunden.
2. Audio wird heruntergeladen und in MP3 umgewandelt.
3. Die Dateien werden in einen vorbereiteten Zielordner verschoben oder synchronisiert.
4. Eine einfache Oberfläche macht den Prozess auch ohne Kommandozeile nutzbar.

## Aktueller Stand
- YouTube-Audio-Download mit `yt-dlp`
- MP3-Konvertierung mit `ffmpeg`
- Sync in den `Music/`-Ordner plus lokale `nanosync.db`
- Desktop-GUI mit Flet
- Android-APK-Build über `build_android.bat`
- Pytest-Abdeckung für Kernfunktionen
- Überarbeitung der UI mit einem iPod-inspirierten Layout und Sprachwahl

## Projektstruktur
- `main.py` – CLI für Download, Konvertierung und Sync
- `gui.py` – Einstiegspunkt für die Desktop-GUI
- `nanosync/pipeline.py` – Kernlogik der Pipeline
- `nanosync/gui.py` – Flet-Oberfläche und Suche
- `tests/` – automatische Tests
- `assets/` – UI-Assets und visuelle Elemente
- `SETUP.md` – lokale Setup-Anleitung
- `specs/` – Projektstatus und Detailplanung

## Schnellstart
1. Abhängigkeiten installieren:
   ```powershell
   pip install -r requirements.txt
   ```
2. FFmpeg installieren und im PATH einbinden.
3. Audio aus YouTube laden:
   ```powershell
   python main.py download <youtube-url> <output.mp3>
   ```
4. Eine Datei in MP3 umwandeln:
   ```powershell
   python main.py convert <source> <output.mp3>
   ```
5. Eine MP3 in einen Zielordner kopieren:
   ```powershell
   python main.py sync <source.mp3> <ipod-root>
   ```
6. Die Desktop-GUI starten:
   ```powershell
   python gui.py
   ```

## Tests
```powershell
pytest -q tests/test_pipeline.py tests/test_gui.py
```

## Android-Build
```powershell
build_android.bat
```

## Nächste Schritte
- echte iPod-Datenbank-Synchronisation auf dem Gerät
- bessere Fehlerbehandlung und Fortschrittsanzeige
- Speicherplatzprüfung vor dem Sync
- optionaler Metadaten-Editor und Album-Art
- sauberer USB-OTG-Workflow auf Android

## Hinweis
Das Projekt ist aktuell auf einen robusten MP3-Workflow ausgerichtet. Die nächsten Schritte bauen genau auf dieser Basis auf und führen die Lösung Schritt für Schritt in Richtung eines echten iPod-Transfers.
