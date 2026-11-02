"""T-005/T-024: diagnose the installed Wine without launching it in tests."""
from cs2kit import bottle, probe
from cs2kit.util import Proc, write_json


def test_wine_info_finds_the_recorded_engine_without_path(sandbox, monkeypatch):
    root = sandbox.root / "Wine engine"
    (root / "lib" / "wine").mkdir(parents=True)
    write_json(bottle.state_file(sandbox.prefix), {"wine_root": str(root)})
    monkeypatch.setattr(probe, "which", lambda name: None)
    monkeypatch.setattr(bottle, "which", lambda name: None)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return Proc(0, "wine-10.0 (Sikarugir)\nextra output", "")

    monkeypatch.setattr(probe, "run", fake_run)
    assert probe.wine_info() == {"path": str(root / "bin" / "wine"),
                                 "version": "wine-10.0 (Sikarugir)", "major": 10}
    assert calls == [[str(root / "bin" / "wine"), "--version"]]


def test_wine_info_without_an_engine_is_unavailable(sandbox, monkeypatch):
    monkeypatch.setattr(probe, "which", lambda name: None)
    monkeypatch.setattr(bottle, "which", lambda name: None)
    monkeypatch.setattr(probe, "run", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("no Wine binary should have been executed")))
    assert probe.wine_info() == {"path": None, "version": None, "major": None}


def test_wine_info_tolerates_empty_output_on_failure(sandbox, monkeypatch):
    binary = str(sandbox.root / "broken-wine")
    monkeypatch.setattr(probe, "which", lambda name: binary)
    monkeypatch.setattr(probe, "run", lambda *a, **kw: Proc(1, "", "loader failure"))
    assert probe.wine_info() == {"path": binary, "version": None, "major": None}


def test_wine_info_keeps_path_discovery_when_available(sandbox, monkeypatch):
    binary = str(sandbox.root / "wine")
    monkeypatch.setattr(probe, "which", lambda name: binary)
    monkeypatch.setattr(probe, "wine_root", lambda: (_ for _ in ()).throw(
        AssertionError("the fallback is unnecessary")))
    monkeypatch.setattr(probe, "run", lambda *a, **kw: Proc(0, "wine-9.0", ""))
    assert probe.wine_info()["major"] == 9
