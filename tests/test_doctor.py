"""T-024 acceptance: doctor finds seeded faults and names the fix for each."""
import argparse

from cs2kit import bottle, config, doctor, integrity, probe, recipe as recipe_mod
from cs2kit.util import EXIT_FAIL, EXIT_OK, FAIL, PASS, WARN


def healthy_snapshot(sandbox, **overrides):
    stable = {"macos": "26.5.2", "macos_build": "26F1234", "macos_major": 26,
              "chip": "Apple M2 Pro", "arch": "arm64", "p_cores": "8", "e_cores": "4",
              "gpu_cores": "16", "metal": "Metal 4", "ram_gb": 32,
              "resolution": "3024 x 1964", "wine_version": "wine-11.15",
              "dxmt_version": "v0.6", "cs2_buildid": "24828357",
              "recipe_name": "cs2-default", "recipe_hash": "abc"}
    volatile = {"captured_at": "now", "free_gib": 120, "rosetta": True, "low_power_mode": False,
                "awdl_up": False, "wine_path": "/usr/local/bin/wine", "prefix": str(sandbox.prefix),
                "prefix_exists": True, "dxmt_installed": True,
                "cs2_exe": str(sandbox.steam / "steamapps/common/Counter-Strike Global Offensive"
                                             / "game/bin/win64/cs2.exe"),
                "installed_depots": ["2347770", "2347771"], "steam_root": str(sandbox.steam)}
    stable.update(overrides.pop("stable", {}))
    volatile.update(overrides.pop("volatile", {}))
    return {"stable": stable, "volatile": volatile, "env_id": "deadbeefdeadbeef"}


def by_id(checks):
    return {c.id: c for c in checks}


def test_a_healthy_machine_has_no_failures(sandbox, cs2_tree, monkeypatch):
    monkeypatch.setenv("WINEMSYNC", "1")
    monkeypatch.delenv("WINEESYNC", raising=False)
    (sandbox.prefix / "system.reg").write_text("WINE REGISTRY")
    class R(bottle.WineRunner):
        pass
    bottle.create(recipe_mod.load_default(), prefix=sandbox.prefix, dry_run=True)
    from cs2kit.util import write_json
    write_json(bottle.state_file(sandbox.prefix),
               {"recipe_name": "cs2-default", "recipe_hash": recipe_mod.load_default().hash()})
    integrity.create_baseline()
    config.apply(recipe_mod.resolve("balanced-1080p"))
    checks = doctor.run_checks(healthy_snapshot(sandbox))
    failures = [c for c in checks if c.status == FAIL]
    assert failures == [], [ (c.id, c.detail) for c in failures ]


def test_seeded_faults_are_all_found_with_a_fix_line(sandbox, monkeypatch):
    """Five deliberate faults: no Rosetta, tiny disk, no wine, no bottle, no DXMT."""
    monkeypatch.setenv("WINEESYNC", "1")
    monkeypatch.setenv("WINEMSYNC", "1")
    snap = healthy_snapshot(sandbox, stable={"wine_version": None, "dxmt_version": None},
                            volatile={"rosetta": False, "free_gib": 12, "prefix_exists": False,
                                      "dxmt_installed": False, "cs2_exe": "",
                                      "low_power_mode": True, "awdl_up": True,
                                      "installed_depots": ["2347770"]})
    checks = by_id(doctor.run_checks(snap))
    for check_id in ("rosetta", "disk", "wine", "bottle", "cs2", "sync"):
        assert checks[check_id].status == FAIL, (check_id, checks[check_id])
        assert checks[check_id].fix, f"{check_id} FAILed without telling the user what to do"
    # With no bottle at all, a missing DXMT is a consequence, not an extra fault.
    assert checks["dxmt"].status == WARN
    with_bottle = by_id(doctor.run_checks(healthy_snapshot(
        sandbox, volatile={"dxmt_installed": False})))
    assert with_bottle["dxmt"].status == FAIL and with_bottle["dxmt"].fix
    assert checks["low-power"].status == WARN
    assert checks["awdl"].status == WARN
    assert "2347771" in checks["cs2"].detail
    assert doctor.cmd_doctor(argparse.Namespace(json=False, strict=False, verbose=False)) in (EXIT_OK, EXIT_FAIL)


def test_rosetta_horizon_grades_macos_27_and_28(sandbox):
    warn = by_id(doctor.run_checks(healthy_snapshot(sandbox, stable={"macos_major": 27})))
    assert warn["rosetta-horizon"].status == WARN
    fail = by_id(doctor.run_checks(healthy_snapshot(sandbox, stable={"macos_major": 28})))
    assert fail["rosetta-horizon"].status == FAIL


def test_intel_mac_fails_the_arch_check(sandbox):
    checks = by_id(doctor.run_checks(healthy_snapshot(sandbox, stable={"arch": "x86_64"})))
    assert checks["arch"].status == FAIL


def test_json_output_is_machine_readable(sandbox, capsys, monkeypatch):
    monkeypatch.setattr(probe, "snapshot", lambda *a, **k: healthy_snapshot(sandbox))
    doctor.cmd_doctor(argparse.Namespace(json=True, strict=False, verbose=False))
    payload = __import__("json").loads(capsys.readouterr().out)
    assert payload["env"]["env_id"] and payload["summary"]["PASS"] >= 1
    assert all({"id", "status", "fix", "task"} <= set(c) for c in payload["checks"])


def test_strict_turns_warnings_into_failure(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(probe, "snapshot", lambda *a, **k: healthy_snapshot(sandbox))
    assert doctor.cmd_doctor(argparse.Namespace(json=False, strict=True, verbose=False)) == EXIT_FAIL


def test_wine_that_cannot_run_dxmt_is_a_hard_failure(sandbox):
    """2026-08-24: a Wine without the winemac.drv exports installs DXMT fine and
    then CS2 dies with "Failed to create metal view". Doctor must say so first."""
    checks = by_id(doctor.run_checks(healthy_snapshot(
        sandbox, volatile={"wine_exports_macdrv": False})))
    assert checks["wine-dxmt-abi"].status == FAIL
    assert "CrossOver 24+" in checks["wine-dxmt-abi"].fix

    ok = by_id(doctor.run_checks(healthy_snapshot(sandbox, volatile={"wine_exports_macdrv": True})))
    assert ok["wine-dxmt-abi"].status == PASS

    unknown = by_id(doctor.run_checks(healthy_snapshot(sandbox, volatile={"wine_exports_macdrv": None})))
    assert "wine-dxmt-abi" not in unknown          # never guess


def test_a_crossover_build_is_not_graded_as_stale_wine(sandbox):
    """CX 24.0.7 reports `wine-9.0 (SikarugirCX 24.0.7)`. The 9.0 is its Wine
    base, not an out-of-date install - and it is the build DXMT requires."""
    cx = by_id(doctor.run_checks(healthy_snapshot(
        sandbox, stable={"wine_version": "wine-9.0 (SikarugirCX 24.0.7)"})))
    assert cx["wine"].status == PASS and "CrossOver 24" in cx["wine"].detail

    old = by_id(doctor.run_checks(healthy_snapshot(
        sandbox, stable={"wine_version": "wine-8.0.1 (CrossOver 23.7.1)"})))
    assert old["wine"].status == WARN
