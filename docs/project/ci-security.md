# CI, security and contribution flow

## Purpose and evidence

**CONFIRMED from the workflow definitions:** CS2Kit is a Python CLI that configures and diagnoses
Wine; it is not a renderer or network service. CI therefore tests filesystem boundaries, generated
scripts, configuration, CLI contracts and measurements on synthetic inputs. It must not install or
launch Wine, Steam or CS2, access a developer's real bottle, submit credentials, or automate game input.

This design adapts the pinned tools, least-privilege jobs, periodic rescans and explicit quality gates
used in the existing Piwas projects. Service deployment, database, browser-E2E and staging load-test
jobs do not apply here. The implementation is in [CI](../../.github/workflows/ci.yml),
[CodeQL](../../.github/workflows/codeql.yml), [scheduled audits](../../.github/workflows/security-audit.yml),
and [Sonar](../../.github/workflows/sonar.yml).

## Branch and PR flow

- `develop` is the integration/default branch. Feature, fix and dependency PRs target it.
- `main` is the release branch. Only this repository's `develop` may open a passing promotion PR.
- Both branches require PRs, resolved conversations, current CI and both CodeQL checks. Force pushes
  and deletion are blocked. There is no routine administrator bypass.
- A separate code-scanning rule blocks CodeQL security findings rated high or critical and other
  error-level findings. Successful scanner execution alone does not mean its findings are clean.
- There is currently one writer. Required approval count is zero so the maintainer can merge their
  own PRs; outside contributions still require a maintainer to review and merge. CODEOWNERS requests
  visibility. Add a second required reviewer when the project has another trusted writer.
- Squash feature PRs when appropriate. Use a merge commit for `develop -> main` promotions to retain
  ancestry between the long-lived branches. Do not delete `develop` after a release. Sync `main`
  back into `develop` through a PR after release so subsequent strict checks remain up to date.
- [PR policy](../../scripts/pr_policy.py) rejects direct feature/fork PRs to `main`. Promotion also
  requires a successful GitHub Actions Sonar analysis on the exact `develop` commit being promoted.

Protection settings are repository configuration, not something a YAML file alone can enforce.
Verify them in GitHub Settings after changing check names; never remove a required check from a
workflow without updating the protections.

## Required checks and cadence

| Check | Purpose | Cadence |
|---|---|---|
| Python 3.9, 3.13, 3.14 on Linux and macOS | Full hermetic suite; runtime compatibility and archive policy on the oldest interpreter | PR and protected-branch push |
| Branch coverage >= 80% | Maintain the measured runtime baseline; report uncovered branches | Each test matrix leg |
| System Python with `-S` | Import/parser/CLI without installed site packages | Linux and macOS |
| Ruff | Correctness, undefined names and unused imports | PR/push |
| ShellCheck, `bash -n`, actionlint | Shell and workflow correctness | PR/push |
| Documentation and CLI-contract tests | Working links and real commands | PR/push |
| Bandit | Python security patterns; specific reviewed exceptions only | PR/push and weekly |
| pip-audit | Locked test and quality dependencies for each supported Python target | PR/push and weekly |
| Gitleaks | Redacted secret detection across full Git history | PR/push and weekly |
| CodeQL Python and Actions | Dataflow and workflow security analysis | PR/push and weekly |
| Offline performance smoke | Detect gross regressions in startup, parsing and hashing | PR/push |
| SonarQube Cloud | Security/reliability/maintainability, runtime coverage and quality gate | Trusted integration pushes/PRs |
| `CI required checks` | Fail if any constituent job failed, was cancelled or was unexpectedly skipped | PR/push |

The coverage floor applies to the installed `cs2kit` package, including branches. It does not claim
hardware coverage for the optional research scripts. Sonar coverage excludes hardware research and
CI tooling; those receive static checks, and policy/audit helpers have separate behavioral tests.
Do not hide runtime code from coverage to make a check pass.

## Threat boundaries and scanner limitations

Actions are pinned to full commit SHAs verified against their upstream repositories. Downloaded CI
binaries are version/checksum-pinned in [ci-tools.json](../../.github/ci-tools.json). The
[installer](../../scripts/install_ci_tools.py) verifies bytes and copies only the named regular-file
member; it does not extract archive paths. Dependencies and their hashes are committed in `uv.lock`.
CI uses `uv sync --locked --no-build --no-install-project`; normal CLI users still need no packages.

Workflow permissions default to read-only. Checkout does not persist credentials, shared dependency
caches are disabled, and timeouts/concurrency limits bound wasted runs. CodeQL alone receives the
security-events write permission needed for reports. No workflow uses `pull_request_target` or
executes artifacts from an untrusted privileged follow-up run.
Repository secret scanning and push protection, Dependabot security updates, and private vulnerability
reporting are enabled. Feature PR branch-policy code is checked out from `develop`; release PRs
evaluate the integration code being promoted, so bootstrapping CI onto an older `main` also works.
Maintainers must still review workflow and policy changes: a required check name cannot prove that a
proposed workflow continues to perform the same validation.

Fork PRs receive ordinary tests and security checks without Sonar credentials. Sonar's token is
available only to its scanner step on trusted integration events; it is not passed to test commands.
**This is not sandboxing:** trusted PR code runs earlier in that job, so same-repository contributors
must already be trusted with that credential. Never broaden the condition to include fork code.

Sonar's integration baseline is `develop`. Under a plan limited to one long-lived analysis branch,
`main` receives the previously analyzed integration commit through the promotion policy. We do not
pay for another plan or pretend a skipped fork scan is a completed analysis. The scanner waits for
its quality gate and fails if analysis or the gate fails. Automatic analysis must be switched off
when CI-based analysis is enabled, so there are not two competing analysis methods.

A scanner does not prove archive containment, shell argument preservation or process ownership.
The executable regressions in [test_archive.py](../../tests/test_archive.py) and
[test_security.py](../../tests/test_security.py) cover these boundaries with temporary sentinels,
including symlink chains, hard links, destination swaps, shell payloads and checksum refusal.
Archive symbolic links are checked against the staged graph and the corresponding destination
targets. Legitimate dangling wrapper links remain supported; links that would bind to retained
destination symlinks outside the extraction root are rejected before publication.
Shutdown uses the selected prefix's wineserver and waits for termination; it no longer kills global
PID/name matches. Native Wine behavior and physical game acceptance still require manual validation.
The unmerged external security PR is not imported wholesale; its runtime-copy feature remains a
separate proposal and must address its review before adoption.

The Wine installation selected in local bottle configuration is a trusted executable dependency.
Canonicalization and rejection of PATH separators/control characters prevent extra search entries;
they do not authenticate a user-supplied engine or sandbox hostile local configuration. Do not import
an untrusted bottle's engine configuration or run CS2Kit as a privileged service.

Two Sonar findings were individually reviewed as false positives, with rationale recorded on each
issue, without disabling their rules:

- `AaGZ1PFSLh6Xm1Y7HCBA` (`S6549`): checking the selected Wine directory is local engine discovery.
  There is no HTTP requester or less-privileged recipient to receive a filesystem-existence oracle.
- `AaGZ1PHLLh6Xm1Y7HCBC` (`S7044`): CI tool URLs come from the checked-in manifest, under the same
  review authority as the executing script. Official repository/HTTPS/redirect checks and SHA-256
  verification apply before installation in a new private directory. No external URL input is accepted.

Reassess these decisions if configuration is served remotely or tool manifests become external inputs.

## Python 3.9 test-tool exception

**CONFIRMED by the upstream pytest advisory:** pytest 8.4.2, the last compatible version for Python
3.9, is affected by CVE-2025-71176 / PYSEC-2026-1845. The listed fix is pytest 9.0.3, which requires a
newer Python. This affects pytest's predictable shared temporary root; pytest is not a runtime
CS2Kit dependency.

[conftest.py](../../tests/conftest.py) sets `basetemp` under a newly created private mode-0700
`TemporaryDirectory` before pytest initializes its temporary factory. This applies to direct local
pytest runs as well as CI and avoids the vulnerable shared-root path. A behavioral test checks the
actual temporary parent and permissions. Do not remove that hook while supporting pytest 8.

[audit-exceptions.json](../../.github/audit-exceptions.json) records the exact package, version,
Python target, identifiers, mitigation and expiry **2026-12-31**. The auditor still prints the
finding as mitigated; it does not use a global advisory-ignore switch. Different versions, packages,
Python targets, new advisories and expired entries fail closed. Before expiry, re-evaluate whether a
compatible fix is available or whether to revise the system-Python compatibility strategy.

## Performance evidence

[perf_smoke.py](../../scripts/perf_smoke.py) uses one discarded warm-up and five retained samples,
then reports medians and every sample to an artifact. Initial generous budgets are 2 seconds for
CLI help, 0.5 seconds for 100 profile parses, and 0.5 seconds for hashing 16 MiB. These are coarse
smoke budgets, not a promise to catch small changes on variable shared runners. Tighten them only
with runner-specific evidence, retaining old samples and explaining the change.

These tests produce **no FPS, frame-time, latency or VAC-acceptance evidence**. Hosted runners cannot
establish CS2 performance on an Apple Silicon Mac with a real Wine/Metal stack. Continue to use
[the game benchmark protocol](../benchmarking.md) and physical acceptance separately. Optional OCR
research scripts require local macOS dependencies and user-driven hardware validation; CI never runs
their capture/input routines.

## Local verification

```bash
uv sync --locked --all-groups --no-build --no-install-project --python 3.13
uv run --locked --no-build --no-sync pytest --cov --cov-fail-under=80
uv run --locked --no-build --no-sync ruff check cs2kit scripts tests
uv run --locked --no-build --no-sync bandit -c pyproject.toml -r cs2kit -q
uv run --locked --no-build --no-sync python scripts/audit_dependencies.py
shellcheck bin/cs2kit scripts/preflight.sh
actionlint
python3 scripts/perf_smoke.py
```

## Primary references

- [GitHub Actions secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use)
  supports immutable action pins and avoiding privileged execution of fork code.
- [GitHub ruleset rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
  describe required PRs, checks, conversations, and expected check sources.
- [Sonar GitHub Actions integration](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/ci-based-analysis/github-actions-for-sonarcloud)
  and [Python coverage](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/test-coverage/python-test-coverage)
  explain CI-based scanning, token use and imported coverage.
- [Sonar subscription capabilities](https://docs.sonarsource.com/sonarqube-cloud/administering-sonarcloud/managing-subscription/subscription-plans)
  distinguish main-only and multi-branch analysis plans.
- [uv locking](https://docs.astral.sh/uv/concepts/projects/sync/) explains locked versus frozen installs.
- [pip-audit](https://github.com/pypa/pip-audit) explains audits of fully pinned requirements without installation.
- [pytest security fix](https://github.com/pytest-dev/pytest/pull/14343) and
  [temporary-directory configuration](https://docs.pytest.org/en/stable/how-to/tmp_path.html) explain
  the compatibility exception's underlying issue and `basetemp` behavior.
- [Python tarfile security guidance](https://docs.python.org/3/library/tarfile.html#extraction-filters)
  explains link/path hazards and extraction resource limits.
- [Wine's wineserver manual](https://github.com/wine-mirror/wine/blob/master/server/wineserver.man.in)
  defines prefix-selected shutdown, signal options and waiting.
