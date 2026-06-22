PROJEKTPLAN: NanoSync - Dein iPod Nano Medienzentrum
--------------------------------------------------

1. ZIELSETZUNG
   Entwicklung eines PC-Tools (Windows/Linux), das YouTube-Videos (Premium) automatisch lädt, 
   für den iPod Nano 6G konvertiert und auf das Gerät synchronisiert.
   
2. TECH-STACK
   - Sprache: Python 3.11+
   - Download: yt-dlp (mit Cookie-Auth für Premium)
   - Konvertierung: FFmpeg (Subprocess-Steuerung)
   - GUI: CustomTkinter oder Flet (für modernes Design)
   - DB: SQLite (lokale Medienverwaltung)
   - iPod-Anbindung: gpod-python (Manipulation der iTunesDB)

3. PHASENPLAN
   Woche 1: Research & POC
   - Analyse: iPod_Control Ordner & iTunesDB-Struktur.
   - Test: Manuelle Video-Konvertierung via FFmpeg auf 320x240 (Baseline profile).
   - Test: Hardware-Mounting & Pfad-Identifikation (Windows/Linux).

   Woche 2: Core-Engine
   - Entwicklung: SQLite-Schema zur Verwaltung von Downloads.
   - Scripting: yt-dlp Integration mit Cookies.
   - Pipeline: Automatisierte FFmpeg-Queue.

   Woche 3: Die Brücke (Sync)
   - Implementierung: Schreiben der Dateien in den iPod_Control Ordner.
   - Logik: Integration der gpod-Bibliothek zur Datenbank-Aktualisierung.
   - Error-Handling: Was passiert bei Speicherplatzmangel oder Verbindungsabbruch?

   Woche 4: GUI & Polish
   - UI Design: Dashboard zur URL-Eingabe & Sync-Status-Anzeige.
   - Features: "One-Click-Sync"-Button, Fortschrittsanzeige, Speicher-Manager.
   - Testing: Integration aller Module.

4. ERSTE SCHRITTE (TODOs)
   - [ ] Python Umgebung einrichten.
   - [ ] yt-dlp installieren (`pip install yt-dlp`).
   - [ ] FFmpeg herunterladen & Pfad in Umgebungsvariablen setzen.
   - [ ] POC Skript schreiben: 
         URL -> Download -> Konvertierung -> Test-Ordner.

5. GUI-KONZEPT (Anforderungen)
   - Dashboard: Übersicht der verbundenen Geräte.
   - Input: Feld für YT-Links oder Playlist-URLs.
   - Status: Visualisierung des iPod-Speicherstatus.
   - Action: Sync-Button (Startet Download, Encoding & Übertragung).