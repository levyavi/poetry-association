import os

import pytest

from poem_assoc.__main__ import main
from poem_assoc.config import Config


def test_config_derives_import_temp_dir_and_normalizes_warn_alias(tmp_path):
    db_path = tmp_path / "nested" / "poem_assoc.db"
    cfg = Config(
        db_path=str(db_path),
        secret_key="secret",
        admin_password="admin",
        model_name="all-MiniLM-L6-v2",
        model_path=None,
        log_level="warn",
    )

    assert cfg.import_temp_dir == os.path.join(str(tmp_path / "nested"), "_import_tmp")
    assert cfg.log_level == "WARNING"
    assert os.path.isabs(cfg.nltk_data_path)


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", "   "])
def test_config_from_environment_recognizes_falsey_synonym_flags(monkeypatch, value):
    monkeypatch.setenv("ENABLE_SYNONYM_EXPANSION", value)
    monkeypatch.setenv("POEM_ADMIN_PASSWORD", "admin")

    cfg = Config.from_environment()

    assert cfg.enable_synonym_expansion is False


def test_config_from_environment_falls_back_for_invalid_log_level(monkeypatch):
    monkeypatch.setenv("POEM_ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("POEM_LOG_LEVEL", "loud")

    cfg = Config.from_environment()

    assert cfg.log_level == "WARNING"


def test_main_import_csv_exits_with_cli_status(monkeypatch):
    import poem_assoc.cli as cli

    def fake_import_csv(argv):
        assert argv == ["fixture.csv"]
        return 7

    monkeypatch.setattr(cli, "import_csv", fake_import_csv)
    monkeypatch.setattr("sys.argv", ["poem_assoc", "import-csv", "fixture.csv"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 7


def test_main_starts_web_app_and_prints_url(monkeypatch, capsys):
    import poem_assoc.__main__ as main_module

    calls = {}

    class FakeApp:
        def run(self, host, port):
            calls["host"] = host
            calls["port"] = port

    monkeypatch.setattr(main_module, "create_app", lambda: FakeApp())
    monkeypatch.setattr("sys.argv", ["poem_assoc"])

    main()

    captured = capsys.readouterr()
    assert "http://127.0.0.1:5000" in captured.out
    assert calls == {"host": "127.0.0.1", "port": 5000}
