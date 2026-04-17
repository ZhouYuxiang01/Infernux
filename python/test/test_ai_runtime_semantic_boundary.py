"""Semantic boundary guard (REFACTOR §10).

Scans ``python/Infernux/ai_runtime/`` for occurrences of tokens that belong
to the Adapter layer's vocabulary ("player", "jump", "attack", "enemy",
"platform"). Tokens are matched at word boundaries on the AST-level
identifier surface so comments and docstrings do not trigger false
positives.

A grandfather list exempts modules known to still carry legacy v1.1
vocabulary for the duration of the v1.3 / v1.4 transition. The exempted
set is enumerated in
``Infernux.ai_runtime._semantic_boundary.GRANDFATHERED_MODULES`` and shrinks
to empty at Phase 4 (v2.0).

An opt-out marker ``# noqa: semantic-boundary`` on a line silences the
guard for that line, for the rare deliberate exception.
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

import pytest


def _load_boundary_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "Infernux"
        / "ai_runtime"
        / "_semantic_boundary.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_semantic_boundary_module", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BOUNDARY = _load_boundary_module()
_AI_RUNTIME_DIR = (
    Path(__file__).resolve().parents[1] / "Infernux" / "ai_runtime"
)


def _collect_docstring_nodes(tree: ast.AST) -> set[int]:
    """Return ``id()`` values for every ast.Constant string that is a
    docstring (module / class / function / async function).

    REFACTOR §10 explicitly excludes docstrings from the guard; this is how
    we recognise them. Comments are already invisible to ``ast``.
    """
    doc_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                doc_ids.add(id(first.value))
    return doc_ids


def _collect_identifier_surface(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, text)`` pairs for every identifier / string literal
    in ``tree``. Comments are excluded because ``ast`` discards them;
    docstrings are excluded explicitly per REFACTOR §10."""
    doc_ids = _collect_docstring_nodes(tree)
    surface: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            surface.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            surface.append((node.lineno, node.attr))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            surface.append((node.lineno, node.name))
        elif isinstance(node, ast.arg):
            surface.append((node.lineno, node.arg))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in doc_ids:
                continue
            surface.append((node.lineno, node.value))
    return surface


def _build_pattern(tokens: frozenset[str]) -> re.Pattern[str]:
    alternation = "|".join(re.escape(tok) for tok in sorted(tokens))
    return re.compile(rf"\b({alternation})\b", re.IGNORECASE)


def _collect_exempt_lines(source: str, marker: str) -> set[int]:
    exempt: set[int] = set()
    for idx, line in enumerate(source.splitlines(), start=1):
        if marker in line:
            exempt.add(idx)
    return exempt


def _scan_file(path: Path, pattern: re.Pattern[str]) -> list[str]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover — should not happen
        return [f"{path.name}:{exc.lineno}: SyntaxError {exc.msg}"]

    exempt_lines = _collect_exempt_lines(source, _BOUNDARY.ESCAPE_HATCH_MARKER)
    offenses: list[str] = []
    for lineno, text in _collect_identifier_surface(tree):
        if lineno in exempt_lines:
            continue
        match = pattern.search(text)
        if match:
            offenses.append(f"{path.name}:{lineno} uses token {match.group(1)!r} in {text!r}")
    return offenses


def _iter_ai_runtime_modules() -> list[Path]:
    return sorted(p for p in _AI_RUNTIME_DIR.glob("*.py") if p.is_file())


def test_semantic_boundary_module_is_importable():
    assert hasattr(_BOUNDARY, "FORBIDDEN_TOKENS")
    assert hasattr(_BOUNDARY, "GRANDFATHERED_MODULES")
    assert hasattr(_BOUNDARY, "ESCAPE_HATCH_MARKER")
    assert isinstance(_BOUNDARY.FORBIDDEN_TOKENS, frozenset)
    assert isinstance(_BOUNDARY.GRANDFATHERED_MODULES, frozenset)


def test_grandfather_list_only_names_existing_files():
    existing = {p.name for p in _iter_ai_runtime_modules()}
    missing = _BOUNDARY.GRANDFATHERED_MODULES - existing
    assert not missing, (
        f"Grandfather list references files that no longer exist: {sorted(missing)}. "
        "Remove them from GRANDFATHERED_MODULES."
    )


def test_new_ai_runtime_modules_have_no_semantic_leaks():
    pattern = _build_pattern(_BOUNDARY.FORBIDDEN_TOKENS)
    offenses: list[str] = []
    for path in _iter_ai_runtime_modules():
        if path.name in _BOUNDARY.GRANDFATHERED_MODULES:
            continue
        offenses.extend(_scan_file(path, pattern))

    if offenses:
        pytest.fail(
            "Semantic boundary violations in Engine Core (see REFACTOR §10):\n"
            + "\n".join(f"  - {line}" for line in offenses)
            + "\nMove the offending logic to python/Infernux/ai_adapters/ "
            "or use '# noqa: semantic-boundary' if the reference is unavoidable."
        )


def test_ai_runtime_does_not_import_from_adapters():
    """Spec §2.2: Core MUST NOT depend on Adapter."""
    pattern = re.compile(r"\bInfernux\.ai_adapters\b")
    offenses: list[str] = []
    for path in _iter_ai_runtime_modules():
        source = path.read_text(encoding="utf-8")
        for idx, line in enumerate(source.splitlines(), start=1):
            if pattern.search(line):
                offenses.append(f"{path.name}:{idx}: {line.strip()}")
    assert not offenses, (
        "Engine Core leaked an import from the Adapter layer — spec §2.2:\n"
        + "\n".join(f"  - {o}" for o in offenses)
    )
