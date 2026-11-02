"""The compatibility exception must be mitigated, narrow and expire closed."""
import datetime
import importlib.util
import json
import io
import os
import stat
import hashlib
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def installer_module():
    spec = importlib.util.spec_from_file_location('install_ci_tools', ROOT / 'scripts/install_ci_tools.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('url', ['http://github.com/a', 'https://github.com.evil.invalid/a',
                                'https://127.0.0.1/a', 'file:///etc/passwd',
                                'https://user@github.com/a', 'https://github.com:8443/a'])
def test_ci_tool_redirects_refuse_unapproved_destinations_before_following(url):
    module = installer_module()
    with pytest.raises(ValueError, match='URL'):
        module.ReleaseRedirect().redirect_request(None, None, 302, '', {}, url)


@pytest.mark.parametrize('corrupt,link', [(False, False), (True, False), (False, True)])
def test_ci_tool_install_checks_bytes_and_member_and_publishes_only_in_private_temp(tmp_path, monkeypatch, corrupt, link):
    module = installer_module()
    archive = io.BytesIO()
    payload = b'harmless test binary'
    with tarfile.open(fileobj=archive, mode='w:gz') as tar:
        member = tarfile.TarInfo('actionlint')
        if link:
            member.type = tarfile.SYMTYPE
            member.linkname = '/outside'
        else:
            member.size = len(payload)
        tar.addfile(member, None if link else io.BytesIO(payload))
    data = archive.getvalue()
    pin = {'url': 'https://github.com/rhysd/actionlint/releases/download/v1/tool.tar.gz',
           'sha256': '0' * 64 if corrupt else hashlib.sha256(data).hexdigest()}
    monkeypatch.setattr(module.json, 'loads', lambda text: {'actionlint': pin})
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))

    class Response(io.BytesIO):
        def geturl(self):
            return pin['url']

    class Opener:
        def open(self, url, timeout):
            return Response(data)

    monkeypatch.setattr(module.urllib.request, 'build_opener', lambda *a: Opener())
    if corrupt or link:
        with pytest.raises(ValueError):
            module.install('actionlint')
        assert not list(tmp_path.rglob('actionlint'))
    else:
        target = module.install('actionlint')
        assert target.read_bytes() == payload
        assert target.parent.parent == tmp_path
        assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(target.stat().st_mode) == 0o755


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
