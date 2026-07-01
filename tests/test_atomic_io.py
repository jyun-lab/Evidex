from pathlib import Path

from evidex.core.fsio import atomic_write


def test_atomic_write_replaces_content_and_removes_temp_file(tmp_path):
    path = tmp_path / "runs.csv"

    with atomic_write(path, newline="", encoding="utf-8-sig") as handle:
        handle.write("run_id,date\nR001,2026-06-16\n")

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert path.read_text(encoding="utf-8-sig") == "run_id,date\nR001,2026-06-16\n"
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_keeps_original_content_when_write_fails(tmp_path):
    path = tmp_path / "evidex_settings.json"
    path.write_text('{"language": "en"}', encoding="utf-8")

    class ExpectedFailure(Exception):
        pass

    try:
        with atomic_write(path, encoding="utf-8") as handle:
            handle.write('{"language": "ja"}')
            raise ExpectedFailure
    except ExpectedFailure:
        pass

    assert path.read_text(encoding="utf-8") == '{"language": "en"}'
    assert list(tmp_path.glob("*.tmp")) == []
