"""Tests for cs2kit.watch (T-030).

No test here may touch the network: the `no_network` fixture is autouse and
replaces urllib's opener with something that fails the test if it is ever called,
so a future change that adds a real request is caught immediately rather than
turning the suite into a flaky, internet-dependent thing.
"""
import argparse
import json
import urllib.error
import urllib.request

import pytest

from cs2kit import probe, watch
from cs2kit.util import EXIT_NOT_READY, EXIT_OK, EXIT_REGRESSION, PASS, WARN

APPINFO = {"status": "success",
           "data": {"730": {"appid": 730,
                            "depots": {"branches": {"public": {"buildid": "24999999",
                                                               "timeupdated": "1756000000"},
                                                    "1v1": {"buildid": "111"}}}}}}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("a test tried to make a real HTTP request")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)


@pytest.fixture()
def fake_env(monkeypatch):
    snap = {"stable": {"macos": "26.5.2", "wine_version": "wine-11.15", "dxmt_version": "0.6",
                       "cs2_buildid": "24828357"},
            "volatile": {}, "env_id": "abc123def4567890"}
    monkeypatch.setattr(probe, "snapshot", lambda *a, **k: snap)
    return snap


def _parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    watch.register(sub)
    return parser


def _run(argv):
    args = _parser().parse_args(argv)
    return args.func(args)


# --- parsing the appinfo blob ------------------------------------------------
def test_extract_buildid_from_the_documented_path():
    assert watch._extract_buildid(APPINFO) == "24999999"


def test_extract_buildid_survives_a_reshaped_response():
    """A mirror is free to wrap its answer differently; a missed buildid is a
    missed regression drill, so the search falls back to walking the document."""
    wrapped = {"result": [{"app": {"depots": {"branches": {"public": {"buildid": 42}}}}}]}
    assert watch._extract_buildid(wrapped) == "42"


def test_extract_buildid_returns_none_when_the_branch_is_absent():
    assert watch._extract_buildid({"data": {"730": {"depots": {"branches": {}}}}}) is None
    assert watch._extract_buildid({"status": "error"}) is None
    assert watch._extract_buildid("not json at all") is None


# --- fetch -------------------------------------------------------------------
def test_fetch_buildid_reads_the_public_branch(monkeypatch):
    seen = {}

    def fake_get(url, timeout):
        seen["url"], seen["timeout"] = url, timeout
        return APPINFO

    monkeypatch.setattr(watch, "_http_get_json", fake_get)
    result = watch.fetch_buildid(timeout=5.0)
    assert result == {"buildid": "24999999", "branch": "public", "status": "ok",
                      "source": watch.APPINFO_SOURCES[0], "detail": "",
                      "elapsed_s": result["elapsed_s"]}
    assert seen["url"] == watch.APPINFO_SOURCES[0]
    assert 0 < seen["timeout"] <= 5.0


@pytest.mark.parametrize("boom", [
    urllib.error.URLError("nodename nor servname provided"),
    urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None),
    OSError("connection reset"),
    ValueError("Expecting value: line 1 column 1"),
    RuntimeError("a mirror did something exotic"),
])
def test_fetch_buildid_turns_every_failure_into_a_soft_error(monkeypatch, boom):
    def fake_get(url, timeout):
        raise boom

    monkeypatch.setattr(watch, "_http_get_json", fake_get)
    result = watch.fetch_buildid(timeout=1.0)
    assert result["buildid"] is None
    assert result["status"] == "error"
    assert result["detail"]


def test_fetch_buildid_tries_the_next_source_within_one_budget(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        if len(calls) == 1:
            raise urllib.error.URLError("down")
        return APPINFO

    monkeypatch.setattr(watch, "_http_get_json", fake_get)
    result = watch.fetch_buildid(timeout=4.0, sources=("https://a/730", "https://b/730"))
    assert result["buildid"] == "24999999"
    assert result["source"] == "https://b/730"
    assert [c[0] for c in calls] == ["https://a/730", "https://b/730"]
    assert calls[1][1] <= calls[0][1]         # the second call inherits what is left


def test_fetch_buildid_with_no_budget_left_makes_no_call(monkeypatch):
    monkeypatch.setattr(watch, "_http_get_json",
                        lambda url, timeout: pytest.fail("called with no time budget"))
    assert watch.fetch_buildid(timeout=0.0)["status"] == "error"


def test_fetch_buildid_reports_a_response_without_a_buildid(monkeypatch):
    monkeypatch.setattr(watch, "_http_get_json", lambda url, timeout: {"data": {}})
    result = watch.fetch_buildid()
    assert result["buildid"] is None
    assert "no public buildid" in result["detail"]


# --- local record ------------------------------------------------------------
def test_local_buildid_reads_the_appmanifest(cs2_tree):
    assert watch.local_buildid() == "24828357"


def test_local_buildid_is_none_without_a_game(sandbox):
    assert watch.local_buildid() is None


def test_record_buildid_round_trip(sandbox, cs2_tree):
    record = watch.record_buildid()
    assert record["buildid"] == "24828357"
    assert watch.read_record()["buildid"] == "24828357"
    assert watch.record_path().is_file()


# --- check -------------------------------------------------------------------
def _remote(monkeypatch, buildid, status="ok"):
    monkeypatch.setattr(watch, "fetch_buildid", lambda *a, **k: {
        "buildid": buildid, "branch": "public", "source": "test", "status": status,
        "detail": "" if buildid else "network is down", "elapsed_s": 0.0})


def test_check_unchanged(sandbox, cs2_tree, monkeypatch):
    watch.record_buildid("24828357")
    _remote(monkeypatch, "24828357")
    result = watch.check()
    assert result["status"] == "unchanged"
    assert result["level"] == PASS
    assert result["update_pending"] is False
    assert result["action"] is None


def test_check_changed(sandbox, cs2_tree, monkeypatch):
    watch.record_buildid("24828357")
    _remote(monkeypatch, "24999999")
    result = watch.check()
    assert result["status"] == "changed"
    assert result["level"] == WARN
    assert result["action"] == "cs2kit watch drill"
    assert result["update_pending"] is True        # the install is behind the branch
    assert "24999999" in result["detail"]


def test_check_with_the_network_down_is_unknown_not_unchanged(sandbox, cs2_tree, monkeypatch):
    """Reporting "unchanged" when we simply could not ask would silently suppress
    the drill for as long as the machine is offline."""
    watch.record_buildid("24828357")
    _remote(monkeypatch, None, status="error")
    result = watch.check()
    assert result["status"] == "unknown"
    assert result["level"] == WARN
    assert "network is down" in result["remote_detail"]


def test_check_offline_makes_no_request(sandbox, cs2_tree, monkeypatch):
    monkeypatch.setattr(watch, "fetch_buildid",
                        lambda *a, **k: pytest.fail("offline check called the network"))
    result = watch.check(offline=True)
    assert result["status"] == "unknown"
    assert result["remote_status"] == "skipped"


def test_check_falls_back_to_the_appmanifest_when_nothing_is_recorded(sandbox, cs2_tree,
                                                                     monkeypatch):
    _remote(monkeypatch, "24828357")
    result = watch.check()
    assert result["stored_buildid"] == "24828357"
    assert "appmanifest" in result["stored_from"]
    assert result["status"] == "unchanged"


def test_check_without_a_game_or_a_record_is_unknown(sandbox, monkeypatch):
    _remote(monkeypatch, "24999999")
    result = watch.check()
    assert result["status"] == "unknown"
    assert result["local_buildid"] is None
    assert "watch record" in result["detail"]


# --- the compatibility matrix ------------------------------------------------
def test_matrix_row_shape(fake_env):
    row = watch.matrix_row(buildid="24828357", env=fake_env,
                           bench={"aggregate": {"avg_fps": 112.3, "low_1_pct_fps": 78.1}},
                           verdict="PASS", when=0)
    assert row == "| 1970-01-01 | 24828357 | 26.5.2 | wine-11.15 | 0.6 | 112.3 | 78.1 | PASS |"
    assert row.count("|") == watch.MATRIX_HEADER.count("|")


def test_matrix_row_marks_what_it_does_not_know():
    row = watch.matrix_row(when=0)
    assert row.count("?") == 7


def test_append_matrix_row_writes_a_header_once(tmp_path):
    matrix = tmp_path / "compatibility-matrix.md"
    matrix.write_text("# Compatibility matrix\n\nOne row per drill.\n")
    first = watch.append_matrix_row("| a | b | c | d | e | f | g | PASS |", matrix)
    second = watch.append_matrix_row("| h | i | j | k | l | m | n | BROKEN |", matrix)
    assert first["appended"] and second["appended"]
    text = matrix.read_text()
    assert text.count(watch.MATRIX_HEADER) == 1
    assert text.count(watch.MATRIX_RULE) == 1
    assert text.index("PASS") < text.index("BROKEN")     # append-only, chronological
    assert text.startswith("# Compatibility matrix")


def test_append_matrix_row_is_a_no_op_without_a_matrix(tmp_path):
    missing = tmp_path / "nope.md"
    result = watch.append_matrix_row("| a |", missing)
    assert result["appended"] is False
    assert not missing.exists()


# --- commands ----------------------------------------------------------------
def test_check_command_json(sandbox, cs2_tree, monkeypatch, capsys):
    watch.record_buildid("24828357")
    _remote(monkeypatch, "24828357")
    assert _run(["watch", "check", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unchanged"
    assert payload["command"] == "watch check"


def test_check_command_exit_on_change(sandbox, cs2_tree, monkeypatch, capsys):
    watch.record_buildid("24828357")
    _remote(monkeypatch, "24999999")
    assert _run(["watch", "check", "--json"]) == EXIT_OK
    assert _run(["watch", "check", "--exit-on-change", "--json"]) == EXIT_REGRESSION


def test_check_command_never_fails_when_offline(sandbox, cs2_tree, monkeypatch):
    _remote(monkeypatch, None, status="error")
    assert _run(["watch", "check", "--exit-on-change"]) == EXIT_OK


def test_record_command(sandbox, cs2_tree, capsys):
    assert _run(["watch", "record", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["buildid"] == "24828357"
    assert payload["source"] == "appmanifest"


def test_record_command_accepts_an_explicit_buildid(sandbox, capsys):
    assert _run(["watch", "record", "--buildid", "31337", "--json"]) == EXIT_OK
    assert watch.read_record()["buildid"] == "31337"


def test_record_command_without_a_game_is_not_ready(sandbox, capsys):
    assert _run(["watch", "record", "--json"]) == EXIT_NOT_READY
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_drill_prints_the_steps_and_files_a_row(sandbox, cs2_tree, fake_env, tmp_path, capsys):
    matrix = tmp_path / "compatibility-matrix.md"
    matrix.write_text("# Compatibility matrix\n")
    assert _run(["watch", "drill", "--matrix", str(matrix), "--verdict", "PASS",
                 "--record", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["buildid"] == "24828357"
    assert len(payload["steps"]) == len(watch.DRILL_STEPS)
    assert any("doctor" in step for step in payload["steps"])
    assert any("bench" in step for step in payload["steps"])
    assert any("smoke test" in step for step in payload["steps"])
    assert payload["matrix"]["appended"] is True
    assert "| 24828357 |" in matrix.read_text()
    assert "| PASS |" in matrix.read_text()
    assert watch.read_record()["buildid"] == "24828357"


def test_drill_uses_the_latest_bench_numbers(sandbox, cs2_tree, fake_env, tmp_path, capsys):
    from cs2kit import bench
    runs = [bench.summarize([1000.0 / 112.3] * 100) for _ in range(5)]
    bench.save_session(bench.build_session(runs, label="drill", env=fake_env, warmups=3))
    matrix = tmp_path / "m.md"
    matrix.write_text("# m\n")
    assert _run(["watch", "drill", "--matrix", str(matrix), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["bench_session"] is not None
    assert "112.3" in payload["row"]


def test_drill_can_print_without_writing(sandbox, cs2_tree, fake_env, capsys):
    assert _run(["watch", "drill", "--no-matrix"]) == EXIT_OK
    printed = capsys.readouterr().out
    assert "regression drill" in printed
    assert "| 24828357 |" in printed
    assert watch.read_record() == {}          # --record not given: nothing stored
