import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


INSTALLER = Path(__file__).resolve().parents[1] / "install_cron.sh"


class CronInstallerTests(unittest.TestCase):
    def test_preserves_existing_entries_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project with 'quote' and %"
            project.mkdir()
            installer = project / "install_cron.sh"
            shutil.copyfile(INSTALLER, installer)
            marker = root / "runner-executed"
            (project / "daily_transcribe.sh").write_text('#!/bin/sh\ntouch "$MARKER"\n')
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_crontab = bin_dir / "crontab"
            fake_crontab.write_text(
                '#!/bin/sh\n'
                'if [ "$1" = "-l" ]; then cat "$FAKE_CRONTAB"; '
                'else cp "$1" "$FAKE_CRONTAB"; fi\n'
            )
            fake_crontab.chmod(0o755)
            existing = root / "crontab"
            existing.write_text("15 3 * * * /bin/true\n")
            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", FAKE_CRONTAB=str(existing), MARKER=str(marker))
            for _ in range(2):
                subprocess.run(["bash", str(installer)], env=env, check=True, capture_output=True, text=True)
            lines = existing.read_text().splitlines()
            self.assertEqual(lines[0], "15 3 * * * /bin/true")
            self.assertEqual(len(lines), 2)
            self.assertIn("\\%", lines[1])
            self.assertIn("'\\''", lines[1])
            self.assertTrue(lines[1].startswith("0 2 * * * "))
            command = lines[1].removeprefix("0 2 * * * ").replace("\\%", "%")
            subprocess.run(["/bin/sh", "-c", command], env=env, check=True)
            self.assertTrue(marker.exists())

    def test_installs_when_no_crontab_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_crontab = root / "crontab"
            fake_crontab.write_text(
                '#!/bin/sh\n'
                'if [ "$1" = "-l" ]; then printf "no crontab for user\\n" >&2; exit 1; '
                'else cp "$1" "$FAKE_CRONTAB"; fi\n'
            )
            fake_crontab.chmod(0o755)
            output = root / "installed"
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", FAKE_CRONTAB=str(output))
            subprocess.run(["bash", str(INSTALLER)], env=env, check=True, capture_output=True, text=True)
            self.assertTrue(output.read_text().startswith("0 2 * * * "))

    def test_crontab_read_failure_does_not_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_crontab = root / "crontab"
            fake_crontab.write_text('#!/bin/sh\nprintf "permission denied\\n" >&2\nexit 1\n')
            fake_crontab.chmod(0o755)
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}")
            result = subprocess.run(["bash", str(INSTALLER)], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("permission denied", result.stderr)


if __name__ == "__main__":
    unittest.main()