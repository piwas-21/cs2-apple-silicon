<!-- CS2Kit pull request. Delete sections that genuinely do not apply; do not delete the rules. -->

## What this changes

<!-- One paragraph. Name the plan task, e.g. "T-024: add the AWDL doctor check". -->

Task: T-0__

## Why

<!-- The problem, not the diff. If it is a measurement, say which machine and which protocol run. -->

## Evidence

<!-- Paste the command and its real output. Never paste a number you did not measure. -->

```
$ cs2kit doctor
```

## Checklist

- [ ] `uv run pytest` passes locally.
- [ ] `cs2kit/` still imports on the system interpreter:
      `PYTHONPATH="$PWD" /usr/bin/python3 -c "import cs2kit.cli"`
- [ ] **Standard library only** - no new runtime dependency in `cs2kit/`
      (see [CONTRIBUTING.md](../CONTRIBUTING.md)).
- [ ] No game file is written, patched, hooked or hashed-around; no Steam
      authentication is wrapped; nothing touches VAC
      (see [docs/06-legal-and-policy.md](../docs/06-legal-and-policy.md)).
- [ ] Every new factual claim in `docs/` cites a `docs/` or `research/` file,
      and is tagged CONFIRMED / LIKELY / UNKNOWN.
- [ ] Unmeasured values say **not measured** or **UNRECORDED**. No invented FPS
      numbers, no invented checksums.
- [ ] New relative markdown links resolve (`uv run pytest tests/test_docs.py`).

## Risk

<!-- What breaks if this is wrong, and how a user would notice. -->
