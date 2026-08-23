"""A deliberately small YAML subset - load and dump - with no dependencies.

Why not PyYAML: CS2Kit must run on a stock Mac with `/usr/bin/python3` and no
`pip install` step. The recipe and profile files are ours, so we control the
dialect. Supported: nested block mappings, block sequences of scalars or
mappings, `#` comments, quoted and bare scalars, ints, floats, booleans, null,
and multi-line-free values only. Anything else raises `YamlError` loudly rather
than guessing - a silently mis-parsed bottle recipe is worse than a crash.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


class YamlError(ValueError):
    """The document used a construct outside the supported subset."""


_TRUE = {"true", "yes", "on"}
_FALSE = {"false", "no", "off"}
_NULL = {"", "null", "~"}


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    low = s.lower()
    if low in _NULL:
        return None
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if s == "{}":
        return {}
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [parse_scalar(x) for x in inner.split(",")] if inner else []
    return s


def _lines(text: str) -> List[Tuple[int, int, str]]:
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        body = _strip_comment(raw)
        if not body.strip():
            continue
        if "\t" in body[: len(body) - len(body.lstrip())]:
            raise YamlError(f"line {n}: tabs are not valid YAML indentation")
        out.append((n, len(body) - len(body.lstrip()), body.strip()))
    return out


def loads(text: str) -> Any:
    items = _lines(text)
    if not items:
        return {}
    value, idx = _parse_block(items, 0, items[0][1])
    if idx != len(items):
        raise YamlError(f"line {items[idx][0]}: unexpected indentation")
    return value


def _parse_block(items, idx: int, indent: int):
    if items[idx][2].startswith("- "):
        return _parse_seq(items, idx, indent)
    return _parse_map(items, idx, indent)


def _parse_map(items, idx: int, indent: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    while idx < len(items):
        line_no, ind, body = items[idx]
        if ind < indent:
            break
        if ind > indent:
            raise YamlError(f"line {line_no}: unexpected indentation")
        if ":" not in body:
            raise YamlError(f"line {line_no}: expected 'key: value', got {body!r}")
        key, _, rest = body.partition(":")
        key, rest = key.strip(), rest.strip()
        idx += 1
        if rest:
            out[key] = parse_scalar(rest)
            continue
        if idx < len(items) and items[idx][1] > ind:
            out[key], idx = _parse_block(items, idx, items[idx][1])
        else:
            out[key] = None
    return out, idx  # type: ignore[return-value]


def _parse_seq(items, idx: int, indent: int) -> List[Any]:
    out: List[Any] = []
    while idx < len(items):
        line_no, ind, body = items[idx]
        if ind < indent:
            break
        if ind > indent or not body.startswith("- "):
            raise YamlError(f"line {line_no}: malformed list item {body!r}")
        item = body[2:].strip()
        idx += 1
        if ":" in item and not (item[0] in "\"'"):
            # inline first key of a mapping item: "- name: x" plus deeper lines
            sub = [(line_no, 0, item)]
            while idx < len(items) and items[idx][1] > ind:
                sub.append((items[idx][0], items[idx][1] - (ind + 2), items[idx][2]))
                idx += 1
            val, _ = _parse_map(sub, 0, 0)
            out.append(val)
        else:
            out.append(parse_scalar(item))
    return out, idx  # type: ignore[return-value]


# --- dumping -----------------------------------------------------------------
def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if s == "" or s.strip() != s or s.lower() in _TRUE | _FALSE | _NULL or any(
        ch in s for ch in ":#[]{}&*!|>%@`,"
    ):
        return '"' + s.replace('"', '\\"') + '"'
    try:
        float(s)
        return f'"{s}"'
    except ValueError:
        return s


def dumps(data: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(data, dict):
        if not data:
            return pad + "{}\n"
        out = []
        for key, value in data.items():
            if isinstance(value, (dict, list)) and value:
                out.append(f"{pad}{key}:\n{dumps(value, indent + 2)}")
            elif isinstance(value, (dict, list)):
                out.append(f"{pad}{key}: {'{}' if isinstance(value, dict) else '[]'}\n")
            else:
                out.append(f"{pad}{key}: {_fmt(value)}\n")
        return "".join(out)
    if isinstance(data, list):
        out = []
        for item in data:
            if isinstance(item, dict):
                body = dumps(item, indent + 2)
                out.append(f"{pad}-" + body[indent + 1:])
            else:
                out.append(f"{pad}- {_fmt(item)}\n")
        return "".join(out)
    return pad + _fmt(data) + "\n"


def load_file(path) -> Any:
    from pathlib import Path

    return loads(Path(path).read_text())
