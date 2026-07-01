import os

from evidex.core.backup import prune_backups


def _touch(path, mtime):
    path.write_text("backup\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_prune_backups_keeps_each_prefix_independently(tmp_path):
    for index in range(105):
        _touch(tmp_path / f"runs-20260616-{index:03}.csv", index)
    for index in range(5):
        _touch(tmp_path / f"series-20260616-{index:03}.csv", 1000 + index)

    prune_backups(tmp_path)

    assert len(list(tmp_path.glob("runs-*.csv"))) == 100
    assert len(list(tmp_path.glob("series-*.csv"))) == 5


def test_prune_backups_ignores_non_backup_files(tmp_path):
    for index in range(101):
        _touch(tmp_path / f"steps-20260616-{index:03}.csv", index)
    other_csv = tmp_path / "other-20260616.csv"
    runs_txt = tmp_path / "runs-20260616.txt"
    _touch(other_csv, 0)
    _touch(runs_txt, 0)

    prune_backups(tmp_path)

    assert len(list(tmp_path.glob("steps-*.csv"))) == 100
    assert other_csv.exists()
    assert runs_txt.exists()
