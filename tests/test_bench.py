"""Tests for cs2kit.bench (T-011 protocol, T-026 automation).

The maths tests use hand-computed vectors: if `summarize` or `aggregate` were
subtly wrong - the mean of instantaneous FPS instead of a time-weighted average,
a percentile off by one - these fail. The tolerance tests sit exactly on the
+-5 % T-026 boundary, on both sides.
"""
import argparse
import json

import pytest

from cs2kit import bench, probe
from cs2kit.util import EXIT_NOT_READY, EXIT_OK, EXIT_REGRESSION, EXIT_USAGE

# 90 frames at 8 ms and 10 frames at 40 ms: every metric below is worked out by
# hand in test_summarize_hand_computed, so the numbers are checkable on paper.
VECTOR = [8.0] * 90 + [40.0] * 10


def _parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    bench.register(sub)
    return parser


def _run(argv):
    parser = _parser()
    args = parser.parse_args(argv)
    return args.func(args)


@pytest.fixture()
def fake_env(monkeypatch):
    """A deterministic probe.snapshot(): the real one shells out to
    system_profiler, which is slow and machine-dependent."""
    snap = {"stable": {"macos": "26.5.2", "chip": "Apple M2 Pro", "cs2_buildid": "24828357",
                       "wine_version": "wine-11.15", "dxmt_version": "0.6"},
            "volatile": {"free_gib": 120},
            "env_id": "abc123def4567890"}
    monkeypatch.setattr(probe, "snapshot", lambda *a, **k: snap)
    return snap


def _write_runs(tmp_path, fps_values, frames=100):
    """One frametime log per requested average FPS, at a constant frametime."""
    paths = []
    for i, fps in enumerate(fps_values):
        path = tmp_path / ("run%d.csv" % i)
        path.write_text("\n".join(["%.6f" % (1000.0 / fps)] * frames) + "\n")
        paths.append(str(path))
    return paths


# --- summarize ---------------------------------------------------------------
def test_summarize_hand_computed():
    result = bench.summarize(VECTOR)
    # total time = 90*8 + 10*40 = 1120 ms over 100 frames
    assert result["frames"] == 100
    assert result["duration_s"] == pytest.approx(1.12)
    assert result["avg_fps"] == pytest.approx(100 * 1000.0 / 1120.0, abs=1e-4)   # 89.2857
    # sorted vector: indices 0..89 are 8 ms, 90..99 are 40 ms.
    # p99 index = (100-1)*0.99 = 98.01 -> between two 40 ms samples -> 40 ms.
    assert result["p99_frametime_ms"] == pytest.approx(40.0)
    assert result["low_1_pct_fps"] == pytest.approx(25.0)
    # median 8 ms -> hitch threshold = max(20, 24) = 24 ms -> the ten 40 ms frames
    assert result["median_frametime_ms"] == pytest.approx(8.0)
    assert result["hitch_threshold_ms"] == pytest.approx(24.0)
    assert result["hitch_count"] == 10


def test_avg_fps_is_time_weighted_not_the_mean_of_instantaneous_fps():
    """The mean of per-frame FPS flatters a stuttering run; docs/07 wants the
    honest number, so avg_fps must be frames / total time."""
    naive = sum(1000.0 / ft for ft in VECTOR) / len(VECTOR)
    assert naive == pytest.approx(115.0)                     # 0.9*125 + 0.1*25
    assert bench.summarize(VECTOR)["avg_fps"] == pytest.approx(89.2857, abs=1e-3)


def test_hitch_threshold_adapts_to_a_fast_machine():
    """3x median catches relative stutter; the fixed floor catches absolute
    stutter. A 25 ms frame on a 10 ms machine is under 3x median, so it is not a
    hitch - but the same run with the protocol's 50 ms floor keeps a 60 ms frame."""
    assert bench.summarize([10.0] * 20 + [25.0])["hitch_count"] == 0        # 25 < max(20, 30)
    assert bench.summarize([10.0] * 20 + [31.0])["hitch_count"] == 1        # 31 > 30
    assert bench.summarize([10.0] * 20 + [40.0], hitch_ms=50.0)["hitch_count"] == 0
    assert bench.summarize([10.0] * 20 + [60.0], hitch_ms=50.0)["hitch_count"] == 1


@pytest.mark.parametrize("bad", [[], [0.0], [-3.0], [8.0, "abc"], [8.0, None], [float("inf")]])
def test_summarize_rejects_impossible_frametimes(bad):
    with pytest.raises(bench.BenchError):
        bench.summarize(bad)


# --- aggregate ---------------------------------------------------------------
def test_aggregate_takes_medians_and_reports_spread():
    runs = [bench.summarize([1000.0 / fps] * 100) for fps in (100, 102, 104, 106, 120)]
    agg = bench.aggregate(runs)
    assert agg["run_count"] == 5
    assert agg["avg_fps"] == pytest.approx(104.0, abs=1e-3)          # median, not mean (106.4)
    assert agg["spread_pct"] == pytest.approx((120 - 100) / 104.0 * 100, abs=1e-2)
    assert agg["low_1_pct_fps"] == pytest.approx(104.0, abs=1e-3)
    assert agg["protocol_runs"] == bench.MEASURED_RUNS


def test_aggregate_median_of_an_even_number_of_runs():
    runs = [bench.summarize([1000.0 / fps] * 50) for fps in (100, 110)]
    assert bench.aggregate(runs)["avg_fps"] == pytest.approx(105.0, abs=1e-3)


def test_aggregate_rejects_empty_and_incomplete_runs():
    with pytest.raises(bench.BenchError):
        bench.aggregate([])
    with pytest.raises(bench.BenchError):
        bench.aggregate([{"avg_fps": 100.0}])


# --- compare (the T-026 acceptance boundary) ---------------------------------
BASE = {"avg_fps": 100.0, "low_1_pct_fps": 60.0, "p99_frametime_ms": 16.6, "hitch_count": 2}


@pytest.mark.parametrize("avg,expected", [
    (95.0, "PASS"),          # exactly -5 %: inside an inclusive tolerance
    (94.99, "REGRESSION"),   # a hair outside
    (105.0, "PASS"),         # exactly +5 %
    (105.01, "IMPROVED"),
    (100.0, "PASS"),
])
def test_compare_tolerance_boundary_is_inclusive(avg, expected):
    new = dict(BASE, avg_fps=avg)
    assert bench.compare(new, BASE, tol_pct=5.0)["verdict"] == expected


def test_compare_reports_every_metric_delta():
    result = bench.compare(dict(BASE, avg_fps=90.0), BASE)
    assert result["metrics"]["avg_fps"]["delta_pct"] == pytest.approx(-10.0)
    assert result["metrics"]["avg_fps"]["verdict"] == "REGRESSION"
    assert result["regressed"] == ["avg_fps"]
    assert result["decided_by"] == ["avg_fps", "low_1_pct_fps"]


def test_compare_one_percent_low_can_regress_alone():
    """A stack change that keeps average FPS but destroys the 1 % low is exactly
    the regression docs/07 says the average would hide."""
    result = bench.compare(dict(BASE, low_1_pct_fps=50.0), BASE)
    assert result["verdict"] == "REGRESSION"
    assert result["regressed"] == ["low_1_pct_fps"]


def test_compare_frametime_metrics_do_not_decide_the_verdict():
    """p99 frametime restates the 1 % low and hitch counts are tiny integers, so
    they are reported but never flip the headline verdict on their own."""
    result = bench.compare(dict(BASE, p99_frametime_ms=25.0, hitch_count=9), BASE)
    assert result["metrics"]["p99_frametime_ms"]["verdict"] == "REGRESSION"
    assert result["metrics"]["hitch_count"]["verdict"] == "REGRESSION"
    assert result["verdict"] == "PASS"


def test_compare_survives_a_zero_baseline():
    result = bench.compare(dict(BASE, hitch_count=3), dict(BASE, hitch_count=0))
    assert result["metrics"]["hitch_count"]["delta_pct"] is None
    assert result["metrics"]["hitch_count"]["verdict"] == "REGRESSION"
    assert json.loads(json.dumps(result))["verdict"] == "PASS"   # still valid JSON


def test_compare_needs_a_shared_headline_metric():
    with pytest.raises(bench.BenchError):
        bench.compare({"p99_frametime_ms": 10.0}, {"p99_frametime_ms": 10.0})


# --- parsers -----------------------------------------------------------------
def test_parse_one_column_list():
    assert bench.parse_frametime_log("8.0\n8.5\n9.25\n") == [8.0, 8.5, 9.25]


def test_parse_ignores_comments_and_blank_lines():
    assert bench.parse_frametime_log("# frametimes\n8.0\n\n// noise\n9.0\n") == [8.0, 9.0]


def test_parse_csv_picks_the_frametime_column_by_header():
    text = "Application,TimeInSeconds,MsBetweenPresents\ncs2.exe,0.10,8.0\ncs2.exe,0.11,9.0\n"
    assert bench.parse_csv(text) == [8.0, 9.0]


def test_parse_csv_converts_an_fps_only_column():
    assert bench.parse_csv("time,FPS\n0.1,125\n0.2,100\n") == [8.0, 10.0]


def test_parse_csv_handles_tabs_and_semicolons():
    assert bench.parse_csv("frame\tframetime_ms\n1\t8.0\n2\t12.0\n") == [8.0, 12.0]
    assert bench.parse_csv("frame;frametime;other\n1;8.0;x\n2;12.0;y\n") == [8.0, 12.0]


def test_parse_showfps_console_lines():
    text = "120 fps  8.33 ms\n118 fps  8.47 ms\n"
    assert bench.parse_frametime_log(text) == pytest.approx([8.33, 8.47])


def test_parse_showfps_fps_only_lines():
    assert bench.parse_frametime_log("fps: 125\nfps: 100\n") == pytest.approx([8.0, 10.0])


def test_parse_refuses_an_ambiguous_headerless_table():
    with pytest.raises(bench.BenchError):
        bench.parse_csv("1,8.0\n2,9.0\n")


def test_parse_refuses_a_header_with_no_usable_column():
    with pytest.raises(bench.BenchError) as excinfo:
        bench.parse_csv("frame,temperature\n1,55\n2,56\n")
    assert "frametime" in str(excinfo.value)


@pytest.mark.parametrize("garbage", [
    "",
    "   \n\n",
    "hello world\nthis is not a benchmark\n",
    "8.0\nnot-a-number\nalso-not\nnope\n",     # majority junk
])
def test_parse_rejects_garbage(garbage):
    with pytest.raises(bench.BenchError):
        bench.parse_frametime_log(garbage)


def test_parse_tolerates_a_minority_of_bad_rows():
    assert bench.parse_frametime_log("8.0\n8.0\n8.0\nbroken\n") == [8.0, 8.0, 8.0]


def test_load_run_reports_a_missing_file(tmp_path):
    with pytest.raises(bench.BenchError):
        bench.load_run(tmp_path / "nope.csv")


# --- storage -----------------------------------------------------------------
def _session(monkeypatch, sandbox, fps, label, env_id="env0000000000000", buildid="24828357"):
    env = {"stable": {"cs2_buildid": buildid}, "volatile": {}, "env_id": env_id}
    runs = [bench.summarize([1000.0 / fps] * 100) for _ in range(5)]
    session = bench.build_session(runs, label=label, env=env, warmups=3)
    bench.save_session(session)
    return session


def test_save_and_load_round_trip(sandbox, monkeypatch):
    first = _session(monkeypatch, sandbox, 100.0, "first")
    stored = bench.load_sessions()
    assert [s["id"] for s in stored] == [first["id"]]
    assert stored[0]["aggregate"]["avg_fps"] == pytest.approx(100.0, abs=1e-3)
    assert bench.latest_session()["id"] == first["id"]


def test_save_session_never_overwrites_a_same_second_session(sandbox, monkeypatch):
    a = _session(monkeypatch, sandbox, 100.0, "same")
    b = _session(monkeypatch, sandbox, 110.0, "same")
    assert a["id"] != b["id"]
    assert len(bench.load_sessions()) == 2


def test_find_session_by_prefix(sandbox, monkeypatch):
    session = _session(monkeypatch, sandbox, 100.0, "prefixed")
    assert bench.find_session(session["id"][:12])["id"] == session["id"]
    assert bench.find_session("nope") is None


def test_baseline_never_crosses_environments_or_buildids(sandbox, monkeypatch):
    mine = _session(monkeypatch, sandbox, 100.0, "mine", env_id="env0000000000000")
    _session(monkeypatch, sandbox, 200.0, "other", env_id="ffff000000000000")
    _session(monkeypatch, sandbox, 300.0, "newbuild", env_id="env0000000000000",
             buildid="99999999")
    baseline = bench.baseline_for("env0000000000000", "24828357")
    assert baseline["id"] == mine["id"]
    assert bench.baseline_for("env0000000000000", "24828357", exclude_id=mine["id"]) is None
    assert bench.baseline_for("nosuchenv", "24828357") is None


def test_load_sessions_skips_a_corrupt_file(sandbox, monkeypatch):
    good = _session(monkeypatch, sandbox, 100.0, "good")
    (bench.session_dir(good["env_id"]) / "broken.json").write_text("{not json")
    assert [s["id"] for s in bench.load_sessions()] == [good["id"]]


def test_slug_is_filename_safe():
    assert bench.slug("Balanced 1080p / DXMT") == "balanced-1080p-dxmt"
    assert bench.slug("///") == "session"


# --- commands ----------------------------------------------------------------
def test_run_without_the_game_is_not_ready(sandbox, fake_env, capsys):
    assert _run(["bench", "run", "--json"]) == EXIT_NOT_READY
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "cs2-missing"
    assert not (sandbox.home / "bench").exists()


def test_dry_run_works_without_a_game_and_stores_nothing(sandbox, fake_env, capsys):
    assert _run(["bench", "run", "--dry-run", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["stored"] is False
    assert payload["game_present"] is False
    assert any("3472126051" in step for step in payload["protocol"])
    assert bench.load_sessions() == []


def test_run_with_the_game_present_but_no_logs_is_a_usage_error(cs2_tree, fake_env):
    assert _run(["bench", "run", "--json"]) == EXIT_USAGE


def test_run_stores_a_session_keyed_by_env_and_buildid(tmp_path, cs2_tree, fake_env, capsys):
    files = _write_runs(tmp_path, [100.0, 101.0, 102.0, 103.0, 104.0])
    argv = ["bench", "run", "--label", "balanced", "--json"]
    for path in files:
        argv += ["--frametimes", path]
    assert _run(argv) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    session = payload["session"]
    assert session["env_id"] == fake_env["env_id"]
    assert session["buildid"] == "24828357"
    assert session["map"]["workshop_id"] == bench.MAP_PRIMARY["workshop_id"]
    assert session["aggregate"]["run_count"] == 5
    assert session["protocol_ok"] is True
    assert session["powermetrics"]["sampled"] is False        # never runs sudo
    assert bench.latest_session()["id"] == session["id"]


def test_run_notes_a_short_protocol(tmp_path, cs2_tree, fake_env, capsys):
    files = _write_runs(tmp_path, [100.0, 101.0])
    argv = ["bench", "run", "--warmups", "0", "--json"]
    for path in files:
        argv += ["--frametimes", path]
    assert _run(argv) == EXIT_OK
    session = json.loads(capsys.readouterr().out)["session"]
    assert session["protocol_ok"] is False
    assert any("warm-up" in note for note in session["notes"])
    assert any("measured runs" in note for note in session["notes"])


def test_import_builds_a_session_from_existing_logs(tmp_path, sandbox, fake_env, capsys):
    files = _write_runs(tmp_path, [120.0] * 5)
    assert _run(["bench", "import"] + files + ["--label", "old-logs", "--json"]) == EXIT_OK
    session = json.loads(capsys.readouterr().out)["session"]
    assert session["label"] == "old-logs"
    assert session["aggregate"]["avg_fps"] == pytest.approx(120.0, abs=1e-2)
    assert len(bench.load_sessions()) == 1


def test_import_of_only_garbage_is_a_usage_error(tmp_path, sandbox, fake_env):
    bad = tmp_path / "bad.csv"
    bad.write_text("nothing here\nnor here\n")
    assert _run(["bench", "import", str(bad), "--json"]) == EXIT_USAGE


def test_list_and_show(sandbox, monkeypatch, capsys):
    session = _session(monkeypatch, sandbox, 111.0, "listed")
    assert _run(["bench", "list", "--json"]) == EXIT_OK
    listing = json.loads(capsys.readouterr().out)
    assert listing["count"] == 1
    assert listing["sessions"][0]["id"] == session["id"]

    assert _run(["bench", "show", "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["session"]["id"] == session["id"]

    assert _run(["bench", "show", "nope", "--json"]) == EXIT_NOT_READY


def test_compare_passes_within_tolerance(sandbox, monkeypatch, capsys):
    _session(monkeypatch, sandbox, 100.0, "baseline")
    _session(monkeypatch, sandbox, 104.0, "rerun")
    assert _run(["bench", "compare", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "PASS"
    assert payload["metrics"]["avg_fps"]["delta_pct"] == pytest.approx(4.0, abs=0.05)


def test_compare_exits_with_the_regression_code(sandbox, monkeypatch, capsys):
    _session(monkeypatch, sandbox, 100.0, "baseline")
    _session(monkeypatch, sandbox, 90.0, "slow")
    assert _run(["bench", "compare", "--json"]) == EXIT_REGRESSION
    assert json.loads(capsys.readouterr().out)["verdict"] == "REGRESSION"


def test_compare_honours_a_wider_tolerance(sandbox, monkeypatch):
    _session(monkeypatch, sandbox, 100.0, "baseline")
    _session(monkeypatch, sandbox, 90.0, "slow")
    assert _run(["bench", "compare", "--tolerance", "15", "--json"]) == EXIT_OK


def test_compare_warns_when_the_buildid_moved(sandbox, monkeypatch, capsys):
    old = _session(monkeypatch, sandbox, 100.0, "old", buildid="1111")
    new = _session(monkeypatch, sandbox, 100.0, "new", buildid="2222")
    assert _run(["bench", "compare", new["id"], "--against", old["id"], "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert "buildid" in payload["warning"]


def test_compare_without_a_baseline_is_not_ready(sandbox, monkeypatch, capsys):
    _session(monkeypatch, sandbox, 100.0, "only")
    assert _run(["bench", "compare", "--json"]) == EXIT_NOT_READY
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_bare_bench_is_a_usage_error(sandbox):
    assert _run(["bench"]) == EXIT_USAGE
