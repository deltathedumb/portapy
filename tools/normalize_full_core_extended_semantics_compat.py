"""Run extended-semantics normalization across current parser pass ordering.

``normalize_full_core_keyword_calls`` replaces ``_parse_call_args`` before the
extended-semantics pass runs.  The latter historically tried to rewrite the
old method's explicit ``*`` and ``**`` branches even though it subsequently
replaces the whole method with the native bootstrap implementation.  This
wrapper permits those two stale textual rewrites to be absent only when the
current method contains no starred AST construction at all.
"""
from __future__ import annotations

from tools import normalize_full_core_extended_semantics as _base


_OPTIONAL_LABELS = {
    "keyword unpack parser": "_npr_ast_nodes_DoubleStarred",
    "positional unpack parser": "_npr_ast_nodes_Starred",
}


def _call_argument_method(source: str) -> str:
    signature = "    def _parse_call_args(self):"
    next_signature = "\n    def _parse_tuple_rhs(self):"
    start = source.find(signature)
    if start < 0:
        raise RuntimeError("call argument compatibility: method start not found")
    end = source.find(next_signature, start + len(signature))
    if end < 0:
        raise RuntimeError("call argument compatibility: next method not found")
    return source[start:end]


def _compatible_replace(
    source: str,
    old: str,
    new: str,
    *,
    label: str,
    expected: int = 1,
) -> str:
    count = source.count(old)
    marker = _OPTIONAL_LABELS.get(label)
    if marker is not None and count == 0:
        method = _call_argument_method(source)
        if marker in method:
            raise RuntimeError(
                f"{label}: stale rewrite missing while {marker} remains"
            )
        print("SKIPPED", label, "call parser already normalized")
        return source
    return _original_replace(
        source,
        old,
        new,
        label=label,
        expected=expected,
    )


_original_replace = _base._replace


def main() -> int:
    previous = _base._replace
    _base._replace = _compatible_replace
    try:
        return _base.main()
    finally:
        _base._replace = previous


if __name__ == "__main__":
    raise SystemExit(main())
