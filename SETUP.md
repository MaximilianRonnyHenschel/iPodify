# NanoSync setup

## Local environment

```powershell
cd 'c:\Users\m.henschel\OneDrive - MEBA Metall-Bandsägemaschinen GmbH\Desktop\Berichtsheft\iPod'
.\.venv\Scripts\Activate.ps1
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_pipeline.py
```

## Run the CLI

```powershell
.\.venv\Scripts\python.exe main.py --dry-run input.mp3 output.mp3
```

## Start the GUI

```powershell
.\.venv\Scripts\python.exe gui.py
```

## Build the Android APK

```powershell
.\build_android.bat
```

## Next steps

- Install FFmpeg and ensure it is available on PATH
- Add YouTube download support with yt-dlp
- Add iPod sync and SQLite tracking
