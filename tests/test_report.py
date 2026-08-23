"""Tests for cs2kit.report (T-028).

T-028's acceptance test is "a security review of a real bundle finds ZERO personal
identifiers". So the bundle here is planted with one of every identifier class and
the assertions are made against the *serialised text* of the written files - the
same thing a reviewer would grep - not against the in-memory object.

`test_scan_finds_every_planted_identifier` is the control: it proves the scanner
is not vacuously returning an empty list, which would make every other privacy
assertion here worthless.
"""
import argparse
import json
import tarfile

import pytest

from cs2kit import probe, report
from cs2kit.util import Check, CheckSet, EXIT_FAIL, EXIT_OK, EXIT_USAGE, PASS, WARN

SECRETS = ("Mahmut's MacBook Pro", "Mahmuts-MacBook-Pro", "steamvictim")

#: captured before the autouse fixture replaces it, so one test can exercise the real thing
REAL_LOCAL_SECRETS = report.local_secrets

PLANTED = {
    "home_path": "/Users/steamvictim/Library/Application Support/Steam/steamapps",
    "linux_home": "/home/steamvictim/.wine",
    "steamid_text": "logged in as 76561198012345678 on this machine",
    "steamid_number": 76561198012345678,
    "AccountName": "steamvictim",
    "acf_fragment": '"PersonaName"\t\t"victim_2000"',
    "contact": "please mail bug@example.co.uk about this",
    "public_ip": "connected via 203.0.113.55",
    "lan_ip": "router at 192.168.1.44",
    "loopback": "steam listens on 127.0.0.1:27060",
    "ipv6": "fe80::1c2d:3e4f:5a6b:7c8d is the link-local address",
    "mac_address": "a4:83:e7:1b:2c:3d",
    "serial_line": "Serial Number (system): C02XY1234ABC",
    "IOPlatformSerialNumber": "C02XY1234ABC",
    "computer_name": "Mahmut's MacBook Pro",
    "mdns": "Mahmuts-MacBook-Pro.local",
    "nested": [{"path": "/Users/steamvictim/CS2/prefix", "timestamp": "2026-08-24T12:30:45Z"}],
    "/Users/steamvictim/key": "a username can be a dict key too",
    "keep_macos": "26.5.2",
    "keep_wine": "wine-11.15",
    "keep_fps": 112.34,
}


@pytest.fixture(autouse=True)
def fixed_identity(monkeypatch):
    """Pin the machine's own identity so the tests do not depend on whose Mac they
    run on, and so the cached lookup cannot leak between tests."""
    monkeypatch.setattr(report, "_SECRETS_CACHE", None)
    monkeypatch.setattr(report, "local_secrets",
                        lambda refresh=False: report._secret_variants(SECRETS))
    return SECRETS


@pytest.fixture()
def fake_env(monkeypatch):
    snap = {"stable": {"macos": "26.5.2", "chip": "Apple M2 Pro", "cs2_buildid": "24828357",
                       "wine_version": "wine-11.15"},
            "volatile": {"prefix": "/Users/steamvictim/CS2/prefix", "free_gib": 120},
            "env_id": "abc123def4567890"}
    monkeypatch.setattr(probe, "snapshot", lambda *a, **k: snap)
    return snap


def _parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    report.register(sub)
    return parser


def _run(argv):
    args = _parser().parse_args(argv)
    return args.func(args)


# --- the scanner is not vacuous ----------------------------------------------
def test_scan_finds_every_planted_identifier():
    kinds = {f["kind"] for f in report.scan(PLANTED)}
    assert {"steamid64", "email", "mac", "ipv4", "ipv6", "home_path",
            "local_identifier"} <= kinds


def test_scan_keeps_loopback_out_of_the_findings():
    findings = report.scan({"x": "bound to 127.0.0.1 and ::1"})
    assert findings == []


# --- redaction, class by class -----------------------------------------------
def test_redaction_leaves_no_identifier_behind():
    clean = report.redact(PLANTED)
    assert report.scan(clean) == []


def test_redacted_text_does_not_contain_any_planted_value():
    text = json.dumps(report.redact(PLANTED))
    for leaked in ("steamvictim", "76561198012345678", "victim_2000", "bug@example.co.uk",
                   "203.0.113.55", "192.168.1.44", "fe80::1c2d:3e4f:5a6b:7c8d",
                   "a4:83:e7:1b:2c:3d", "C02XY1234ABC", "Mahmut", "MacBook-Pro"):
        assert leaked not in text, "%s survived redaction" % leaked


def test_redaction_keeps_the_diagnostic_content():
    clean = report.redact(PLANTED)
    assert clean["keep_macos"] == "26.5.2"
    assert clean["keep_wine"] == "wine-11.15"
    assert clean["keep_fps"] == 112.34
    assert "127.0.0.1" in clean["loopback"]
    assert "2026-08-24T12:30:45Z" in clean["nested"][0]["timestamp"]


def test_home_paths_keep_their_shape():
    clean = report.redact(PLANTED)
    assert clean["home_path"].startswith("/Users/<redacted>/Library/Application Support/Steam")
    assert clean["linux_home"] == "/home/<redacted>/.wine"


def test_a_username_used_as_a_dict_key_is_redacted():
    clean = report.redact(PLANTED)
    assert "/Users/<redacted>/key" in clean
    assert not any("steamvictim" in key for key in clean)


def test_a_steamid_stored_as_an_integer_is_redacted():
    assert report.redact({"steam_id_64": 76561198012345678})["steam_id_64"] == report.REDACTED
    assert report.redact({"unlabelled": 76561198012345678})["unlabelled"] == report.REDACTED
    assert report.redact({"buildid": 24828357})["buildid"] == 24828357


def test_secret_keys_scrub_whatever_shape_the_value_has():
    clean = report.redact({"AccountName": {"nested": "anything"}, "hostname": ["a", "b"],
                           "map_name": "Ancient"})
    assert clean["AccountName"] == report.REDACTED
    assert clean["hostname"] == report.REDACTED
    assert clean["map_name"] == "Ancient"          # an innocent *_name key survives


def test_extra_secrets_are_scrubbed():
    clean = report.redact({"note": "the profile is called dave-competitive"},
                          extra_secrets=("dave",))
    assert "dave" not in json.dumps(clean)


def test_redaction_is_idempotent():
    once = report.redact(PLANTED)
    assert report.redact(once) == once


def test_local_secrets_picks_up_the_unix_user(monkeypatch):
    monkeypatch.setattr(report, "local_secrets", REAL_LOCAL_SECRETS)
    monkeypatch.setattr(report, "_SECRETS_CACHE", None)
    monkeypatch.setenv("USER", "unlikelyusername")
    assert "unlikelyusername" in report.local_secrets(refresh=True)
    assert "unlikelyusername.local" in report.local_secrets()


# --- collectors are defensive ------------------------------------------------
def test_doctor_collector_survives_a_broken_doctor(monkeypatch):
    import types
    import cs2kit
    fake = types.ModuleType("cs2kit.doctor")

    def run_checks():
        raise TypeError("run_checks() takes 1 positional argument but 0 were given")

    fake.run_checks = run_checks
    monkeypatch.setitem(__import__("sys").modules, "cs2kit.doctor", fake)
    monkeypatch.setattr(cs2kit, "doctor", fake, raising=False)
    section = report._doctor_section()
    assert section["available"] is True
    assert "TypeError" in section["result"]["error"]


def test_doctor_collector_normalises_a_checkset(monkeypatch):
    import types
    import cs2kit
    fake = types.ModuleType("cs2kit.doctor")
    checks = CheckSet([Check(id="os", label="macOS version", status=PASS, detail="26.5.2"),
                       Check(id="awdl", label="AWDL", status=WARN, detail="up", fix="turn it off")])
    fake.run_checks = lambda: checks
    monkeypatch.setitem(__import__("sys").modules, "cs2kit.doctor", fake)
    monkeypatch.setattr(cs2kit, "doctor", fake, raising=False)
    section = report._doctor_section()
    assert section["result"]["summary"][PASS] == 1
    assert section["result"]["checks"][1]["fix"] == "turn it off"


def test_missing_doctor_is_reported_not_raised():
    section = report._doctor_section()
    assert section["available"] in (True, False)      # either way, it returned


def test_integrity_collector_uses_the_first_entry_point(monkeypatch):
    import types
    import cs2kit
    fake = types.ModuleType("cs2kit.integrity")
    fake.summary = lambda: {"files": 4, "changed": 0}
    monkeypatch.setitem(__import__("sys").modules, "cs2kit.integrity", fake)
    monkeypatch.setattr(cs2kit, "integrity", fake, raising=False)
    section = report._integrity_section()
    assert section["entry_point"] == "summary"
    assert section["result"] == {"files": 4, "changed": 0}


def test_collect_has_every_advertised_section(sandbox, fake_env):
    bundle = report.collect()
    for name, _ in report.SECTION_DESCRIPTIONS:
        assert name in bundle


def test_bench_section_reports_an_empty_history(sandbox, fake_env):
    section = report._bench_section()
    assert section["session"] is None
    assert "no stored benchmark session" in section["note"]


# --- bundle ------------------------------------------------------------------
def test_build_bundle_writes_json_md_and_tarball(tmp_path):
    result = report.build_bundle(tmp_path, bundle=dict(PLANTED, generated="now"))
    assert result["clean"] is True
    written = json.loads(open(result["json"]).read())
    assert report.scan(written) == []
    assert open(result["md"]).read().startswith("# CS2Kit report")
    with tarfile.open(result["archive"]) as tar:
        names = sorted(member.name.split("/")[-1] for member in tar.getmembers()
                       if member.isfile())
        assert names == ["report.json", "report.md"]
        for member in tar.getmembers():
            if member.isfile():
                body = tar.extractfile(member).read().decode()
                assert report.scan(body) == []
                assert "steamvictim" not in body


def test_build_bundle_refuses_to_write_an_unredacted_bundle(tmp_path, monkeypatch):
    """If redaction ever regresses, the writer must fail loudly rather than ship."""
    monkeypatch.setattr(report, "redact", lambda obj, extra_secrets=(): obj)
    with pytest.raises(report.RedactionError):
        report.build_bundle(tmp_path, bundle=PLANTED)
    assert list(tmp_path.glob("*.tar.gz")) == []


def test_build_bundle_can_skip_the_archive(tmp_path):
    result = report.build_bundle(tmp_path, bundle={"generated": "now"}, archive=False)
    assert result["archive"] is None
    assert list(tmp_path.glob("*.tar.gz")) == []


def test_render_markdown_carries_the_headline_numbers():
    bundle = {"generated": "now", "tool": {"version": "0.1.0"},
              "env": {"stable": {"macos": "26.5.2", "wine_version": "wine-11.15"},
                      "env_id": "abc"},
              "bench": {"session": {"buildid": "24828357",
                                    "map": {"name": "Ancient", "workshop_id": "3472126051"},
                                    "aggregate": {"avg_fps": 112.3, "low_1_pct_fps": 78.1}}},
              "doctor": {"result": {"checks": [{"status": "FAIL", "label": "disk",
                                                "detail": "12 GB free"}]}}}
    text = report.render_markdown(bundle)
    assert "112.3" in text and "78.1" in text
    assert "| FAIL | disk | 12 GB free |" in text
    assert "3472126051" in text


# --- command -----------------------------------------------------------------
def test_report_refuses_to_write_without_confirmation(sandbox, fake_env, tmp_path, capsys):
    out = tmp_path / "out"
    assert _run(["report", "--out", str(out), "--json"]) == EXIT_USAGE
    payload = json.loads(capsys.readouterr().out)
    assert payload["written"] is False
    assert payload["reason"] == "confirmation-required"
    assert not out.exists()


def test_report_prints_exactly_what_will_be_shared(sandbox, fake_env, tmp_path, capsys):
    _run(["report", "--out", str(tmp_path / "out")])
    printed = capsys.readouterr().out
    for name, _ in report.SECTION_DESCRIPTIONS:
        assert name in printed
    for item in report.REDACTION_CLASSES:
        assert item in printed


def test_report_writes_after_yes(sandbox, fake_env, tmp_path, capsys):
    out = tmp_path / "out"
    assert _run(["report", "--out", str(out), "--yes", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["written"] is True
    assert report.scan(payload["report"]) == []
    body = open(payload["json"]).read()
    assert "steamvictim" not in body
    assert list(out.glob("*.tar.gz"))


def test_report_honours_an_interactive_no(sandbox, fake_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(report, "_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    out = tmp_path / "out"
    assert _run(["report", "--out", str(out), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["written"] is False
    assert not out.exists()


def test_report_honours_an_interactive_yes(sandbox, fake_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(report, "_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    out = tmp_path / "out"
    assert _run(["report", "--out", str(out), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["written"] is True


def test_report_fails_loudly_if_redaction_is_incomplete(sandbox, fake_env, tmp_path,
                                                        monkeypatch, capsys):
    monkeypatch.setattr(report, "redact", lambda obj, extra_secrets=(): obj)
    monkeypatch.setattr(report, "collect", lambda: dict(PLANTED))
    out = tmp_path / "out"
    assert _run(["report", "--out", str(out), "--yes", "--json"]) == EXIT_FAIL
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "redaction-incomplete"
    assert "steamid64" in payload["findings"]
    assert not out.exists()
