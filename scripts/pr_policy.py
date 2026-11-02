"""Feature PRs target develop; main accepts only a validated develop promotion."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path


def validate(event, checks=None):
    pr = event.get('pull_request')
    if not pr or pr['base']['ref'] != 'main':
        return
    if pr['head']['ref'] != 'develop' or pr['head']['repo']['full_name'] != pr['base']['repo']['full_name']:
        raise ValueError('main accepts only develop from this repository; target develop for feature/fix PRs')
    if checks is not None and not any(
        item['name'] == 'SonarQube analysis' and item['conclusion'] == 'success'
        and item.get('app', {}).get('slug') == 'github-actions' for item in checks):
        raise ValueError('the exact develop commit needs a successful SonarQube analysis before promotion')


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    validate(event)
    pr = event.get('pull_request')
    if pr and pr['base']['ref'] == 'main':
        sha = pr['head']['sha']
        if not re.fullmatch('[0-9a-f]{40}', sha):
            raise ValueError('invalid release commit')
        repo = os.environ['GITHUB_REPOSITORY']
        request = urllib.request.Request(
            f'https://api.github.com/repos/{repo}/commits/{sha}/check-runs?per_page=100',
            headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                     'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            checks = json.load(response)['check_runs']
        validate(event, checks)
    print('PR branch policy passed')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
