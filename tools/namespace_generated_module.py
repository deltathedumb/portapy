"""Namespace top-level functions in an ephemeral generated Python module.

asmpython currently lowers imported Python functions into a shared native symbol
space. Prefixing generated dependency helpers prevents unrelated parser/runtime
layers from defining the same private symbol. Only identifiers are transformed;
interpreter semantics remain in the canonical Python source files.
"""
from __future__ import annotations

import ast
from io import StringIO
from pathlib import Path
import token
import tokenize


def top_level_function_names(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    return tuple(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def namespace_source(source: str, prefix: str) -> tuple[str, dict[str, str]]:
    if not prefix.isidentifier() or not prefix.endswith("_"):
        raise ValueError("namespace prefix must be an identifier ending in underscore")
    names = top_level_function_names(source)
    mapping = {name: prefix + name.lstrip("_") for name in names}
    rewritten: list[tokenize.TokenInfo] = []
    for item in tokenize.generate_tokens(StringIO(source).readline):
        if item.type == token.NAME and item.string in mapping:
            item = tokenize.TokenInfo(
                item.type,
                mapping[item.string],
                item.start,
                item.end,
                item.line,
            )
        rewritten.append(item)
    return tokenize.untokenize(rewritten), mapping


def namespace_generated_module(path: Path, prefix: str) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    rewritten, mapping = namespace_source(source, prefix)
    path.write_text(rewritten, encoding="utf-8")
    return mapping


__all__ = [
    "namespace_generated_module",
    "namespace_source",
    "top_level_function_names",
]
