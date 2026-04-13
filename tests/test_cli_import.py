import os
import sqlite3
import subprocess
import sys


def _run_cli(*args, env=None, timeout=60):
    """Helper to run the poem_assoc CLI, working around Windows handle issues."""
    return subprocess.run(
        [sys.executable, "-m", "poem_assoc", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        timeout=timeout,
    )


class TestCliImport:
    def test_import_real_file(self, tmp_path):
        """Write a real CSV, invoke CLI via subprocess, assert exit 0 and summary."""
        csv_file = tmp_path / "poems.csv"
        csv_file.write_text(
            'title,text\nHello,"A short poem about hello"\nWorld,"A short poem about world"\n',
            encoding="utf-8",
        )
        db_path = str(tmp_path / "cli_test.db")
        env = {**os.environ, "POEM_DB_PATH": db_path}
        result = _run_cli("import-csv", str(csv_file), env=env)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Imported 2 poems" in result.stdout

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT lemmatized_search_text FROM poems ORDER BY id LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0]

    def test_rejects_missing_file(self, tmp_path):
        """Running CLI against a non-existent path exits non-zero."""
        db_path = str(tmp_path / "cli_test.db")
        env = {**os.environ, "POEM_DB_PATH": db_path}
        result = _run_cli("import-csv", "/no/such/file.csv", env=env)
        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_idempotent_reimport(self, tmp_path):
        """Running the same import twice results in 0 imported on second run."""
        csv_file = tmp_path / "poems.csv"
        csv_file.write_text(
            'title,text\nOnce,"Poem that should import once"\n',
            encoding="utf-8",
        )
        db_path = str(tmp_path / "cli_test.db")
        env = {**os.environ, "POEM_DB_PATH": db_path}
        _run_cli("import-csv", str(csv_file), env=env)
        result = _run_cli("import-csv", str(csv_file), env=env)
        assert result.returncode == 0
        assert "Imported 0 poems" in result.stdout
        assert "skipped 1 duplicate" in result.stdout

    def test_same_body_different_title_imports_both(self, tmp_path):
        csv_file = tmp_path / "poems.csv"
        csv_file.write_text(
            'title,text\nOne,"Shared body"\nTwo,"Shared body"\n',
            encoding="utf-8",
        )
        db_path = str(tmp_path / "cli_test.db")
        env = {**os.environ, "POEM_DB_PATH": db_path}
        result = _run_cli("import-csv", str(csv_file), env=env)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Imported 2 poems" in result.stdout
        assert "skipped 0 duplicates" in result.stdout
