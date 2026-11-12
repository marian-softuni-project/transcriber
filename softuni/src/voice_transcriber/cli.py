import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Tuple


FILENAME_PATTERN = re.compile(
    r"Voice (?P<date>[0-9]{6})_(?P<time>[0-9]{6})(?: (?P<tags>[^\s]+(?: [^\s]+)*))?\.m4a",
    re.IGNORECASE,
)


def parse_filename(filename: str) -> Tuple[str, list[str]]:
    match = FILENAME_PATTERN.fullmatch(filename)
    if match is None:
        raise ValueError(f"Invalid audio filename: {filename!r}")
    date = match.group("date")
    time = match.group("time")
    try:
        timestamp = datetime(
            2000 + int(date[:2]), int(date[2:4]), int(date[4:6]),
            int(time[:2]), int(time[2:4]), int(time[4:6]),
        )
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp in filename: {filename!r}") from exc
    tags = match.group("tags")
    return timestamp.isoformat(), tags.split(" ") if tags else []


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe .m4a recordings into SQLite.")
    parser.add_argument("audio", nargs="*", type=Path, help="Audio files to transcribe")
    parser.add_argument("--directory", type=Path, help="Transcribe new .m4a files in this directory")
    parser.add_argument("--database", type=Path, default=Path("transcriptions.db"))
    parser.add_argument("--model", default="base", help="Whisper model name (default: base)")
    args = parser.parse_args(argv)
    if bool(args.audio) == bool(args.directory):
        parser.error("provide audio files or --directory, but not both")
    if args.directory:
        try:
            audio_files = sorted(
                path for path in args.directory.iterdir()
                if path.is_file() and path.suffix.lower() == ".m4a"
            )
        except OSError as exc:
            print(f"Cannot read directory {args.directory}: {exc}", file=sys.stderr)
            return 1
    else:
        audio_files = args.audio

    try:
        with sqlite3.connect(args.database, timeout=30) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    text TEXT NOT NULL,
                    audio_filename TEXT NOT NULL,
                    tags TEXT NOT NULL
                )"""
            )
            model = None
            failed = False
            for audio in audio_files:
                try:
                    timestamp, tags = parse_filename(audio.name)
                    if not audio.is_file():
                        raise ValueError(f"Audio file not found: {audio}")
                    if args.directory:
                        connection.execute("BEGIN IMMEDIATE")
                        if connection.execute(
                            "SELECT 1 FROM transcriptions WHERE audio_filename = ? LIMIT 1",
                            (audio.name,),
                        ).fetchone():
                            connection.rollback()
                            continue
                    if model is None:
                        import whisper

                        model = whisper.load_model(args.model)
                    text = model.transcribe(str(audio))["text"]
                    connection.execute(
                        "INSERT INTO transcriptions (timestamp, text, audio_filename, tags) "
                        "VALUES (?, ?, ?, ?)",
                        (timestamp, text, audio.name, json.dumps(tags, ensure_ascii=False)),
                    )
                    connection.commit()
                    print(f"Transcribed: {audio}")
                except Exception as exc:
                    connection.rollback()
                    failed = True
                    print(f"Error processing {audio}: {exc}", file=sys.stderr)
            return 1 if failed else 0
    except sqlite3.Error as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())