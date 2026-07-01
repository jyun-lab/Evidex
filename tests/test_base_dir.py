from pathlib import Path

from evidex.core import config, csvio, pack_ops, settings
from evidex import packs


def test_resolve_base_dir_prefers_explicit_data_path(tmp_path, monkeypatch):
    monkeypatch.delenv("EVIDEX_HOME", raising=False)
    monkeypatch.setattr(config, "LAST_DIR_FILE", tmp_path / "missing_last_dir.txt")
    data_dir = tmp_path / "explicit"

    assert config.resolve_base_dir(data_dir) == data_dir


def test_resolve_base_dir_prefers_environment(tmp_path, monkeypatch):
    env_dir = tmp_path / "env-ledger"
    monkeypatch.setenv("EVIDEX_HOME", str(env_dir))
    monkeypatch.setattr(config, "LAST_DIR_FILE", tmp_path / "missing_last_dir.txt")

    assert config.resolve_base_dir() == env_dir


def test_resolve_base_dir_uses_checkout_or_home_default(tmp_path, monkeypatch):
    monkeypatch.delenv("EVIDEX_HOME", raising=False)
    monkeypatch.setattr(config, "LAST_DIR_FILE", tmp_path / "missing_last_dir.txt")

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setattr(
        config,
        "__file__",
        str(checkout / "evidex" / "core" / "config.py"),
    )
    assert config.resolve_base_dir() == checkout

    installed = tmp_path / "installed"
    monkeypatch.setattr(
        config,
        "__file__",
        str(installed / "evidex" / "core" / "config.py"),
    )
    assert config.resolve_base_dir() == Path.home() / "Evidex"


def test_set_base_dir_updates_settings_and_user_pack_paths(tmp_path):
    original_records_csv = config.RECORDS_CSV
    try:
        config.set_base_dir(tmp_path)
        pack_dir = tmp_path / "packs" / "private_pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "schema.json").write_text("{}", encoding="utf-8")

        assert config.RECORDS_CSV == tmp_path / "runs.csv"
        assert settings._settings_path() == tmp_path / "evidex_settings.json"
        assert pack_ops.user_pack_root() == tmp_path / "packs"
        assert packs._discover_user_packs() == {"private_pack": str(pack_dir)}
    finally:
        config.RECORDS_CSV = original_records_csv


def test_data_arg_resolution_generates_initial_csv_files(tmp_path):
    from evidex.__main__ import _consume_data_arg

    original_records_csv = config.RECORDS_CSV
    try:
        argv = ["evidex", "--data", str(tmp_path), "--tk"]
        data_dir = _consume_data_arg(argv)
        config.set_base_dir(config.resolve_base_dir(data_dir))

        assert argv == ["evidex", "--tk"]
        assert csvio.ensure_initial_csv_files() == [
            "runs.csv",
            "steps.csv",
            "series.csv",
        ]
        assert (tmp_path / "runs.csv").exists()
        assert (tmp_path / "steps.csv").exists()
        assert (tmp_path / "series.csv").exists()
    finally:
        config.RECORDS_CSV = original_records_csv
