"""Run extended-semantics normalization across current pass ordering.

Several earlier native-bootstrap passes now produce the exact target form that
``normalize_full_core_extended_semantics`` historically created itself. This
wrapper skips only those stale textual rewrites whose replacement semantics are
already present, while retaining the original fail-closed behavior everywhere
else.
"""
from __future__ import annotations

from tools import normalize_full_core_extended_semantics as _base


_CALL_PARSER_MARKERS = {
    "keyword unpack parser": "_npr_ast_nodes_DoubleStarred",
    "positional unpack parser": "_npr_ast_nodes_Starred",
}

_ALREADY_NORMALIZED_MARKERS = {
    "dynamic exception reraising": "RuntimeError: exception did not match handler",
    "exception stack extension": "frame.stack.append(matched)",
    "context-manager exception forwarding": "exit_args.append(exc_type)",
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
    call_marker = _CALL_PARSER_MARKERS.get(label)
    if call_marker is not None and count == 0:
        method = _call_argument_method(source)
        if call_marker in method:
            raise RuntimeError(
                f"{label}: stale rewrite missing while {call_marker} remains"
            )
        print("SKIPPED", label, "call parser already normalized")
        return source

    target_marker = _ALREADY_NORMALIZED_MARKERS.get(label)
    if target_marker is not None and count == 0:
        marker_count = source.count(target_marker)
        if marker_count != 1:
            raise RuntimeError(
                f"{label}: neither unique source nor normalized target form is present; "
                f"target matches={marker_count}"
            )
        print("PRESERVED", label, marker_count)
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
