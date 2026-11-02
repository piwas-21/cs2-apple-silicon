"""Fail on third-party imports anywhere in the installed runtime package."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import pkgutil
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cs2kit


def main():
    stdlib = Path(sysconfig.get_path('stdlib')).resolve()
    for source in (ROOT / 'cs2kit').glob('*.py'):
        tree = ast.parse(source.read_text(), filename=str(source))
        for node in ast.walk(tree):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names.append(node.module)
            for name in names:
                root = name.split('.')[0]
                if root == 'cs2kit':
                    continue
                spec = importlib.util.find_spec(root)
                if spec is None:
                    raise ValueError(f'{source.name}: non-stdlib import {root}')
                if spec.origin not in ('built-in', 'frozen'):
                    origin = Path(spec.origin or '').resolve()
                    if stdlib not in origin.parents or 'site-packages' in origin.parts:
                        raise ValueError(f'{source.name}: non-stdlib import {root}: {origin}')
    for module in pkgutil.iter_modules(cs2kit.__path__, 'cs2kit.'):
        if module.name != 'cs2kit.__main__':
            importlib.import_module(module.name)
    print('All runtime modules import using only the Python standard library')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
