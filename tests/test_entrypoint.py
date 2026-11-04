"""T-024: the zero-install launcher must survive a broken developer Python."""
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def launcher(sandbox):
    root = sandbox.root / "checkout with spaces"
    (root / "bin").mkdir(parents=True)
    entry = root / "bin" / "cs2kit"
    shutil.copy2(ROOT / "bin" / "cs2kit", entry)
    package = root / "cs2kit"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "__main__.py").write_text(
        "import json, os, sys\n"
        "print(json.dumps({'args': sys.argv[1:], 'repo': os.environ['CS2KIT_REPO']}))\n")
    tools = sandbox.root / "Python tools"
    tools.mkdir()
    (tools / "dirname").symlink_to(shutil.which("dirname"))
    env = dict(os.environ, PATH=str(tools), PYTHONPATH="")
    env.pop("CS2KIT_REPO", None)
    return entry, tools, env


def executable(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)
    return path


@pytest.mark.parametrize("failure", [69, 1])
def test_entrypoint_skips_broken_or_unsupported_python(launcher, failure):
    entry, tools, env = launcher
    attempted = tools / "attempted"
    executable(tools / "python3", "printf checked > " + shlex.quote(str(attempted)) +
               "\necho noisy-probe\nexit " + str(failure) + "\n")
    (tools / "python3.13").symlink_to(sys.executable)

    proc = subprocess.run(["/bin/bash", str(entry), "play", "--profile", "a b; c"],
                          env=env, cwd=str(entry.parent.parent),
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert attempted.read_text() == "checked"
    assert json.loads(proc.stdout) == {"args": ["play", "--profile", "a b; c"],
                                       "repo": str(entry.parent.parent)}


def test_interpreter_probe_requires_39_and_suppresses_its_output(launcher):
    entry, tools, env = launcher
    checked = tools / "checked"
    old_python = tools / "old_python.py"
    old_python.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"Path({str(checked)!r}).write_text('checked')\n"
        "print('probe-output')\nsys.version_info = (3, 8, 10)\n"
        "if sys.argv[1] == '-c':\n    exec(sys.argv[2])\n"
        "else:\n    sys.exit(98)\n")
    executable(tools / "python3", "exec " + shlex.quote(sys.executable) + " " +
               shlex.quote(str(old_python)) + ' "$@"\n')
    (tools / "python3.9").symlink_to(sys.executable)
    proc = subprocess.run(["/bin/bash", str(entry), "--help"], env=env,
                          cwd=str(entry.parent.parent), capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert checked.read_text() == "checked"
    assert json.loads(proc.stdout)["args"] == ["--help"]


@pytest.mark.parametrize("args, alternate, uses_first", [
    (["setup"], True, False),
    (["engine", "install"], True, False),
    (["play"], True, True),
    (["setup", "--dry-run"], False, True),
])
def test_entrypoint_prefers_xz_support_for_installs(launcher, args, alternate, uses_first):
    entry, tools, env = launcher
    used = tools / "used-first"
    missing_xz = tools / "missing xz"
    missing_xz.mkdir()
    # Some Python builds bundle _lzma as a built-in module.
    (missing_xz / "sitecustomize.py").write_text("import sys\nsys.modules['_lzma'] = None\n")
    executable(tools / "python3",
               'export PYTHONPATH=' + shlex.quote(str(missing_xz)) + ':"${PYTHONPATH:-}"\n'
               'if [[ "$1" == -m ]]; then : > ' + shlex.quote(str(used)) + '; fi\n'
               'exec ' + shlex.quote(sys.executable) + ' "$@"\n')
    command = ["/bin/bash", str(entry), *args]
    if alternate:
        (tools / "python3.13").symlink_to(sys.executable)
    else:
        # Prevent discovery of host interpreters when testing the fallback.
        script = ('source "$1"\nshift\n'
                  'python_candidates() { command -v python3; }\n'
                  'main "$@"')
        command = ["/bin/bash", "-c", script, "test", str(entry), *args]

    proc = subprocess.run(command, env=env, cwd=entry.parent.parent,
                          capture_output=True, text=True, timeout=10)

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["args"] == args
    assert used.exists() is uses_first


@pytest.mark.parametrize("options,dialog", [("", False), ("--gui", True),
                                           ("--gui --print-only", False)])
def test_missing_python_reports_failure_and_only_dialogs_for_gui(launcher, options, dialog):
    entry, tools, env = launcher
    marker = tools / "dialog"
    executable(tools / "osascript", "printf called > " + shlex.quote(str(marker)) + "\n")
    # Override discovery so this test cannot fall back to the host's Python.
    script = ('source "$1"\npython_candidates() { printf "%s\\n" /missing/python; }\n'
              'main play ' + options)
    proc = subprocess.run(["/bin/bash", "-c", script, "test", str(entry)], env=env,
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 69
    assert proc.stdout == ""
    assert "no working Python 3.9+" in proc.stderr
    assert "If Python reports an Xcode license error" in proc.stderr
    assert "unary operator expected" not in proc.stderr
    assert marker.exists() is dialog
