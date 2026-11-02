"""Audit every supported Python's locked tool dependencies, without installing them."""
from __future__ import annotations

import os
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ('3.9.6', '3.13.12', '3.14.3')


def unmitigated(report, version, exceptions, today):
    remaining = []
    for dependency in report['dependencies']:
        for finding in dependency.get('vulns', []):
            identifiers = {finding['id'], *finding.get('aliases', [])}
            matched = any(
                entry['package'] == dependency['name'] and entry['version'] == dependency['version']
                and entry['python'] == '.'.join(version.split('.')[:2])
                and today <= datetime.date.fromisoformat(entry['expires'])
                and identifiers.intersection(entry['ids'])
                for entry in exceptions)
            label = f"{dependency['name']} {dependency['version']}: {finding['id']}"
            if matched:
                print(f"MITIGATED, time-limited exception: {label}; see .github/audit-exceptions.json")
            else:
                remaining.append(label)
    return remaining


def main():
    exported = subprocess.run(
        ['uv', 'export', '--locked', '--all-groups', '--no-emit-project', '--no-hashes'],
        check=True, capture_output=True, text=True, cwd=ROOT).stdout
    lines = [line.strip() for line in exported.splitlines()]
    requirements = [Requirement(line) for line in lines if line and not line.startswith('#')]
    failed = False
    exceptions = json.loads((ROOT / '.github/audit-exceptions.json').read_text())
    with tempfile.TemporaryDirectory(prefix='cs2kit-audit-') as temporary:
        for version in TARGETS:
            environment = default_environment()
            environment.update(python_version='.'.join(version.split('.')[:2]), python_full_version=version)
            selected = set()
            for requirement in requirements:
                if requirement.marker is None or requirement.marker.evaluate(environment):
                    selected.add(requirement.name + str(requirement.specifier))
            path = Path(temporary) / f'{version}.txt'
            path.write_text('\n'.join(sorted(selected)) + '\n')
            print(f'Auditing Python {version}: {len(selected)} locked dependencies', flush=True)
            result = subprocess.run(
                [sys.executable, '-m', 'pip_audit', '--no-deps', '--disable-pip',
                 '--progress-spinner', 'off', '--format', 'json', '-r', str(path)],
                cwd=ROOT, env=dict(os.environ), capture_output=True, text=True, check=False)
            if result.returncode not in (0, 1):
                print(result.stderr, file=sys.stderr)
                return 1
            report = json.loads(result.stdout)
            remaining = unmitigated(report, version, exceptions, datetime.date.today())
            for finding in remaining:
                print(f"UNMITIGATED: {finding}")
            print(f"Python {version}: {len(remaining)} unmitigated advisories", flush=True)
            failed = failed or bool(remaining)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
