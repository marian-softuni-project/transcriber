# Voice Transcriber

Transcribe `.m4a` recordings locally with OpenAI Whisper and store the results in SQLite.

## Requirements

The Ubuntu machine must have Python 3.9 or later, the `whisper` Python module, FFmpeg on the standard executable path, and a running cron service. The runner uses `.venv/bin/python` if present, otherwise `python3`; the chosen interpreter must have Whisper available.

Whisper may download the selected model the first time it is used unless the model is already cached. Transcription can require substantial disk space and processing time.

## Usage

```sh
PYTHONPATH=src python3 -m voice_transcriber.cli "Voice 260320_043020.m4a" "Voice 260320_043020 important work.m4a"
PYTHONPATH=src python3 -m voice_transcriber.cli --database recordings.db --model small /path/to/recordings/*.m4a
```

The default database is `transcriptions.db` in the current directory and the default Whisper model is `base`. Each successful transcription creates a new row; running the command again for the same file creates another row. Processing continues after a file fails, and the command exits with a nonzero status if any file failed.

Filenames must have the form `Voice YYMMDD_HHMMSS` followed by zero or more space-separated tags and the `.m4a` extension. Two-digit years are interpreted as 2000 through 2099. The timestamp is stored as ISO 8601 text without a timezone, because the filename contains no timezone information.

The `transcriptions` table contains `id`, `timestamp`, `text`, `audio_filename`, and `tags`. The filename column contains only the basename, and `tags` is a JSON array of strings, such as `["important", "work"]` or `[]`.

## Daily Import

Place recordings in `data/`. The daily runner scans that folder (not subfolders) and skips filenames already in the database, including recordings imported manually. Failed files remain in the folder and are retried on the next run. A different recording with the same filename is also skipped; rename it to a valid, unique filename to import it. Audio files are not deleted after processing.

Run the scheduled import manually from the project directory with:

```sh
/bin/sh daily_transcribe.sh
```

The runner uses `transcriptions.db` and `transcriptions.log` in the project directory, regardless of cron's working directory. To install the job for the current user at 02:00 local time, run once on the Ubuntu machine:

```sh
bash install_cron.sh
```

The installer preserves existing cron entries and can be run again without adding a duplicate. Run it again if you move the project, and remove the old entry with `crontab -e`. Cron does not run missed jobs while the computer is asleep or switched off. Inspect `transcriptions.log` for transcription errors.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

The tests mock Whisper and do not require a model download or FFmpeg.