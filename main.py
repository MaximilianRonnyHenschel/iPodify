from __future__ import annotations

import argparse
from pathlib import Path

from nanosync.pipeline import convert_video, download_youtube, sync_to_ipod


def main() -> None:
    parser = argparse.ArgumentParser(description="NanoSync prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert_parser = subparsers.add_parser("convert", help="Convert a video to the Nano profile")
    convert_parser.add_argument("source", help="Input video file")
    convert_parser.add_argument("target", help="Output video file")
    convert_parser.add_argument("--dry-run", action="store_true", help="Show the ffmpeg command without running it")

    download_parser = subparsers.add_parser("download", help="Download a YouTube video")
    download_parser.add_argument("url", help="YouTube URL")
    download_parser.add_argument("target", help="Output video file")
    download_parser.add_argument("--dry-run", action="store_true", help="Show the yt-dlp command without running it")

    sync_parser = subparsers.add_parser("sync", help="Copy a video into an iPod-style folder")
    sync_parser.add_argument("source", help="Input video file")
    sync_parser.add_argument("ipod_root", help="Target iPod root directory")
    sync_parser.add_argument("--title", default="video", help="Title for the synced file")

    args = parser.parse_args()

    if args.command == "convert":
        result = convert_video(Path(args.source), Path(args.target), dry_run=args.dry_run)
        print(result.args)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    elif args.command == "download":
        result = download_youtube(args.url, Path(args.target), dry_run=args.dry_run)
        print(result.args)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    elif args.command == "sync":
        target = sync_to_ipod(Path(args.source), Path(args.ipod_root), title=args.title)
        print(target)


if __name__ == "__main__":
    main()
