import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from voice_transcriber.cli import main, parse_filename


class FilenameTests(unittest.TestCase):
    def test_without_tags(self):
        self.assertEqual(parse_filename("Voice 260320_043020.m4a"), ("2026-03-20T04:30:20", []))

    def test_with_multiple_tags(self):
        self.assertEqual(
            parse_filename("Voice 260320_043020 important work.m4a"),
            ("2026-03-20T04:30:20", ["important", "work"]),
        )

    def test_year_is_in_2000s(self):
        self.assertEqual(parse_filename("Voice 991231_235959.m4a")[0], "2099-12-31T23:59:59")

    def test_invalid_filenames_and_dates(self):
        for filename in ("other.m4a", "Voice 260230_043020.m4a", "Voice 260320_250000.m4a", "Voice 260320_043020 .m4a"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                parse_filename(filename)


class TranscriptionTests(unittest.TestCase):
    def test_directory_only_processes_new_audio_and_retries_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio_dir = root / "audio"
            audio_dir.mkdir()
            first = audio_dir / "Voice 260320_043020.m4a"
            second = audio_dir / "Voice 260321_043020 important.M4A"
            first.touch()
            second.touch()
            (audio_dir / "notes.txt").touch()
            database = root / "output.db"
            model = Mock()
            model.transcribe.side_effect = [{"text": "First"}, RuntimeError("decode failed"), {"text": "Second"}]
            whisper = SimpleNamespace(load_model=Mock(return_value=model))
            arguments = ["--database", str(database), "--directory", str(audio_dir)]
            with patch.dict("sys.modules", {"whisper": whisper}):
                self.assertEqual(main(arguments), 1)
                self.assertEqual(main(arguments), 0)
                self.assertEqual(main(arguments), 0)
            self.assertEqual(model.transcribe.call_count, 3)
            self.assertEqual(whisper.load_model.call_count, 2)
            with sqlite3.connect(database) as connection:
                rows = connection.execute("SELECT text, audio_filename FROM transcriptions ORDER BY id").fetchall()
            self.assertEqual(rows, [("First", first.name), ("Second", second.name)])

    def test_empty_directory_does_not_load_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            whisper = SimpleNamespace(load_model=Mock())
            with patch.dict("sys.modules", {"whisper": whisper}):
                self.assertEqual(main(["--database", str(root / "output.db"), "--directory", str(root)]), 0)
            whisper.load_model.assert_not_called()

    def test_inserts_results_and_loads_model_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / "Voice 260320_043020.m4a", root / "Voice 260321_120000 important work.m4a"]
            for file in files:
                file.touch()
            database = root / "output.db"
            model = Mock()
            model.transcribe.side_effect = [{"text": "First"}, {"text": "Second"}]
            whisper = SimpleNamespace(load_model=Mock(return_value=model))
            with patch.dict("sys.modules", {"whisper": whisper}):
                result = main(["--database", str(database), *map(str, files)])
            self.assertEqual(result, 0)
            whisper.load_model.assert_called_once_with("base")
            with sqlite3.connect(database) as connection:
                rows = connection.execute(
                    "SELECT id, timestamp, text, audio_filename, tags FROM transcriptions ORDER BY id"
                ).fetchall()
            self.assertEqual(rows[0][:4], (1, "2026-03-20T04:30:20", "First", files[0].name))
            self.assertEqual(json.loads(rows[0][4]), [])
            self.assertEqual(rows[1][:4], (2, "2026-03-21T12:00:00", "Second", files[1].name))
            self.assertEqual(json.loads(rows[1][4]), ["important", "work"])

    def test_failed_files_are_not_inserted_and_processing_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "Voice 260320_043020.m4a"
            good = root / "Voice 260321_043020.m4a"
            bad.touch()
            good.touch()
            database = root / "output.db"
            model = Mock()
            model.transcribe.side_effect = [RuntimeError("cannot decode audio"), {"text": "Success"}]
            whisper = SimpleNamespace(load_model=Mock(return_value=model))
            with patch.dict("sys.modules", {"whisper": whisper}):
                result = main(["--database", str(database), str(bad), str(good)])
            self.assertEqual(result, 1)
            with sqlite3.connect(database) as connection:
                rows = connection.execute("SELECT text, audio_filename FROM transcriptions").fetchall()
            self.assertEqual(rows, [("Success", good.name)])


if __name__ == "__main__":
    unittest.main()