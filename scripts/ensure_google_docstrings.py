# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ensure public methods have Google-style Args/Returns docstrings."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _type_str(node: ast.expr | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return ""


def _arg_lines(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = func.args
    lines: list[str] = []
    defaults = list(args.defaults)
    pos = list(args.args)
    pos_defaults: list[ast.expr | None] = [None] * (len(pos) - len(defaults)) + list(
        defaults
    )
    for arg, default in zip(pos, pos_defaults):
        if arg.arg in {"self", "cls"}:
            continue
        ann = _type_str(arg.annotation)
        if default is not None:
            lines.append(f"{arg.arg}: default {_type_str(default)}")
        elif ann:
            lines.append(f"{arg.arg}: {ann}")
        else:
            lines.append(arg.arg)
    for arg in args.kwonlyargs:
        ann = _type_str(arg.annotation)
        label = f"{arg.arg}: {ann}" if ann else arg.arg
        lines.append(f"{label} (keyword-only)")
    if args.vararg is not None:
        lines.append(f"*{args.vararg.arg}")
    if args.kwarg is not None:
        lines.append(f"**{args.kwarg.arg}")
    return lines


def _needs_update(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    doc = ast.get_docstring(func) or ""
    arg_lines = _arg_lines(func)
    if arg_lines and "Args:" not in doc and "Arguments:" not in doc:
        return True
    if func.name != "__init__" and "Returns:" not in doc:
        return True
    if func.name == "__init__" and not doc:
        return True
    return False


def _format_docstring(func: ast.FunctionDef | ast.AsyncFunctionDef, body_indent: str) -> str:
    existing = ast.get_docstring(func) or ""
    summary = ""
    for line in existing.splitlines():
        if line.strip():
            summary = line.strip()
            break
    if not summary:
        summary = f"{func.name}."
    if not summary.endswith((".", "!", "?")):
        summary += "."

    item = body_indent + "    "
    parts: list[str] = [summary]
    arg_lines = _arg_lines(func)
    if arg_lines:
        parts.append("")
        parts.append("Args:")
        for line in arg_lines:
            parts.append(f"{item}{line}")
    if func.name != "__init__":
        parts.append("")
        parts.append("Returns:")
        ann = _type_str(func.returns)
        parts.append(f"{item}{ann if ann else 'None.'}")
    elif not arg_lines:
        parts.append("")
        parts.append("Args:")
        parts.append(f"{item}None.")

    out = [f'{body_indent}"""{parts[0]}']
    for part in parts[1:]:
        if not part:
            out.append("")
        elif part in {"Args:", "Returns:", "Raises:"}:
            out.append(f"{body_indent}{part}")
        else:
            out.append(f"{body_indent}{part}" if part.startswith("    ") else f"{item}{part}")
    # fix double indent: arg lines already include item prefix in parts
    # rebuild simply:
    out = [f'{body_indent}"""{parts[0]}']
    for part in parts[1:]:
        if not part:
            out.append("")
        elif part in {"Args:", "Returns:", "Raises:"}:
            out.append(f"{body_indent}{part}")
        elif part.startswith("    "):
            out.append(f"{body_indent}{part}")
        else:
            out.append(f"{item}{part}")
    out.append(f'{body_indent}"""')
    return "\n".join(out) + "\n"


def process_file(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    lines = source.splitlines(keepends=True)
    edits: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        if name.startswith("_") and name != "__init__":
            continue
        if name.startswith("__") and name.endswith("__") and name != "__init__":
            continue
        if node.col_offset not in (0, 4):
            continue
        if not _needs_update(node):
            continue

        def_line = lines[node.lineno - 1]
        def_indent = def_line[: len(def_line) - len(def_line.lstrip(" \t"))]
        body_indent = def_indent + "    "
        formatted = _format_docstring(node, body_indent)

        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            doc_expr = node.body[0]
            edits.append((doc_expr.lineno, doc_expr.end_lineno or doc_expr.lineno, formatted))
        else:
            first = node.body[0].lineno if node.body else node.lineno + 1
            edits.append((first, first - 1, formatted))

    if not edits:
        return 0

    edits.sort(key=lambda e: (e[0], e[1]), reverse=True)
    for start, end, formatted in edits:
        text = formatted if formatted.endswith("\n") else formatted + "\n"
        if end >= start:
            lines[start - 1 : end] = [text]
        else:
            lines.insert(start - 1, text)

    path.write_text("".join(lines), encoding="utf-8")
    return len(edits)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "src/drama_forge")
    total = 0
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        n = process_file(path)
        if n:
            print(f"{path}: {n}")
            total += n
    print(f"total_edits={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
