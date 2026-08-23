"""T-021 acceptance: the guard must exit non-zero when a guarded file is touched."""
import argparse

import pytest

from cs2kit import integrity, probe
from cs2kit.util import EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, FAIL, PASS, WARN


def args(**kw):
    return argparse.Namespace(**{"root": None, "json": False, "strict": False, **kw})


def test_baseline_then_clean_verify(cs2_tree):
    baseline = integrity.create_baseline()
    assert baseline.count == 4 and baseline.buildid == "24828357"
    verdict = integrity.verify()
    assert verdict.status == PASS and verdict.clean


def test_touched_binary_fails_and_exits_non_zero(cs2_tree):
    integrity.create_baseline()
    (cs2_tree / "client.dll").write_bytes(b"MZ-client-PATCHED")
    verdict = integrity.verify()
    assert verdict.status == FAIL
    assert verdict.changed == ["client.dll"] and not verdict.clean
    assert integrity.cmd_check(args()) == EXIT_INTEGRITY
    with pytest.raises(integrity.IntegrityError):
        integrity.guard()


def test_missing_binary_fails(cs2_tree):
    integrity.create_baseline()
    (cs2_tree / "cs2.exe").unlink()
    verdict = integrity.verify()
    assert verdict.status == FAIL and verdict.missing == ["cs2.exe"]


def test_non_binary_changes_are_ignored(cs2_tree):
    integrity.create_baseline()
    (cs2_tree / "shadercache.bin").write_bytes(b"noise")
    (cs2_tree.parent / "notes.txt").write_text("hello")
    assert integrity.verify().status == PASS


def test_new_binary_is_a_warning_not_a_failure(cs2_tree):
    integrity.create_baseline()
    (cs2_tree / "newmodule.dll").write_bytes(b"MZ-new")
    verdict = integrity.verify()
    assert verdict.status == WARN and verdict.added == ["newmodule.dll"]


def test_buildid_change_is_a_stale_baseline_not_an_alarm(cs2_tree, sandbox):
    integrity.create_baseline()
    (cs2_tree / "client.dll").write_bytes(b"MZ-client-v2")
    manifest = sandbox.steam / "steamapps" / "appmanifest_730.acf"
    manifest.write_text(manifest.read_text().replace("24828357", "24900000"))
    verdict = integrity.verify()
    assert verdict.status == WARN and "24828357" in verdict.message
    integrity.guard()  # must not raise: a CS2 update is not tampering


def test_without_a_baseline_it_warns_and_tells_you_what_to_run(cs2_tree):
    verdict = integrity.verify()
    assert verdict.status == WARN and "cs2kit verify baseline" in integrity.check().fix


def test_baseline_without_a_game_is_not_ready(sandbox):
    with pytest.raises(integrity.IntegrityError):
        integrity.create_baseline()
    assert integrity.cmd_baseline(args()) == EXIT_NOT_READY
