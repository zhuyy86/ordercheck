from concurrent.futures import ThreadPoolExecutor
import errno

import pytest

import ordercheck_cli
import report_output


def test_sync_failure_leaves_no_partial_report_and_cli_can_retry(tmp_path, monkeypatch, capsys):
    target = tmp_path / "report.zip"
    real_sync = report_output.os.fsync

    def fail_sync(fd):
        # Staged data exists, but no incomplete file is visible at the final path.
        assert not target.exists()
        assert list(tmp_path.glob(".ordercheck-*"))
        raise OSError(errno.ENOSPC, "simulated disk full")

    monkeypatch.setattr(report_output.os, "fsync", fail_sync)
    args = ["--demo", "--output", str(target)]
    assert ordercheck_cli.main(args) == 1
    assert "disk full" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(report_output.os, "fsync", real_sync)
    assert ordercheck_cli.main(args) == 2
    assert target.read_bytes().startswith(b"PK")
    assert list(tmp_path.iterdir()) == [target]


def test_publication_failure_cleans_staging_and_preserves_an_existing_report(tmp_path, monkeypatch):
    target = tmp_path / "report.zip"
    target.write_bytes(b"previous report")
    with pytest.raises(FileExistsError):
        report_output.publish_report(target, b"replacement")
    assert target.read_bytes() == b"previous report"

    def unsupported(source, destination):
        raise OSError(errno.EPERM, "hard links unsupported")

    monkeypatch.setattr(report_output.os, "link", unsupported)
    with pytest.raises(OSError, match="unsupported"):
        report_output.publish_report(tmp_path / "fresh.zip", b"complete bytes")
    assert list(tmp_path.iterdir()) == [target]


def test_competing_writers_publish_one_whole_payload(tmp_path):
    target = tmp_path / "report.zip"
    payloads = [b"A" * 100000, b"B" * 100000]

    def attempt(payload):
        try:
            report_output.publish_report(target, payload)
            return payload
        except FileExistsError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, payloads))
    winners = [payload for payload in results if payload is not None]
    assert len(winners) == 1
    assert target.read_bytes() == winners[0]
    assert list(tmp_path.iterdir()) == [target]


def test_dangling_symlink_is_not_followed_or_replaced(tmp_path):
    target = tmp_path / "report.zip"
    destination = tmp_path / "missing.zip"
    try:
        target.symlink_to(destination)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")
    with pytest.raises(FileExistsError):
        report_output.publish_report(target, b"report")
    assert target.is_symlink()
    assert not destination.exists()
    assert set(tmp_path.iterdir()) == {target}
