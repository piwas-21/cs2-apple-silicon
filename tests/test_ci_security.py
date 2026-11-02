"""The compatibility exception must be mitigated, narrow and expire closed."""
import datetime
import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def audit_module():
    spec = importlib.util.spec_from_file_location('audit_dependencies', ROOT / 'scripts/audit_dependencies.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pytest_uses_a_private_parent_instead_of_the_predictable_shared_root(tmp_path):
    parent = tmp_path.parent.parent
    assert parent.name.startswith('cs2kit-tests-')
    assert stat.S_IMODE(parent.stat().st_mode) == 0o700
    assert parent.stat().st_uid == os.getuid()


@pytest.mark.parametrize('change', ['expired', 'different_package', 'different_version', 'different_python', 'new_advisory'])
def test_audit_exception_does_not_hide_unrelated_or_expired_findings(change):
    module = audit_module()
    exceptions = json.loads((ROOT / '.github/audit-exceptions.json').read_text())
    report = {'dependencies': [{'name': 'pytest', 'version': '8.4.2',
        'vulns': [{'id': 'PYSEC-2026-1845', 'aliases': []}]}]}
    version = '3.9.6'
    today = datetime.date(2026, 11, 2)
    if change == 'expired':
        today = datetime.date(2027, 1, 1)
    elif change == 'different_package':
        report['dependencies'][0]['name'] = 'other'
    elif change == 'different_version':
        report['dependencies'][0]['version'] = '8.4.1'
    elif change == 'different_python':
        version = '3.13.12'
    else:
        report['dependencies'][0]['vulns'][0]['id'] = 'NEW-ADVISORY'
    assert module.unmitigated(report, version, exceptions, today)


def test_audit_reports_only_the_exact_mitigated_compatibility_finding(capsys):
    module = audit_module()
    exceptions = json.loads((ROOT / '.github/audit-exceptions.json').read_text())
    report = {'dependencies': [{'name': 'pytest', 'version': '8.4.2',
        'vulns': [{'id': 'PYSEC-2026-1845', 'aliases': []}]}]}
    assert module.unmitigated(report, '3.9.6', exceptions, datetime.date(2026, 11, 2)) == []
    assert 'MITIGATED, time-limited' in capsys.readouterr().out
