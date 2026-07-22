"""Run extended-semantics normalization across current pass ordering.

Several earlier native-bootstrap passes now produce either the exact target form
or a compact equivalent of source that ``normalize_full_core_extended_semantics``
historically rewrote. This wrapper recognizes only those verified shapes while
retaining the original fail-closed behavior everywhere else.
"""
from __future__ import annotations

from tools import normalize_full_core_extended_semantics as _base
from tools.normalize_full_core_pattern_constructor_collisions import (
    main as normalize_pattern_constructor_collisions,
)


_CALL_PARSER_MARKERS = {
    "keyword unpack parser": "_npr_ast_nodes_DoubleStarred",
    "positional unpack parser": "_npr_ast_nodes_Starred",
}

_ALREADY_NORMALIZED_MARKERS = {
    "exception stack extension": "frame.stack.append(matched)",
    "context-manager exception forwarding": "exit_args.append(exc_type)",
}

_DYNAMIC_EXCEPTION_COMPACT = '''                    if not self._exception_matches(value, expected):
                         if isinstance(value, (BaseException, PyException)): raise value
                         _raise_typed("RuntimeError: invalid exception value")'''

_DYNAMIC_EXCEPTION_TARGET = '''                    if not self._exception_matches(value, expected):
                         if isinstance(value, (BaseException, PyException)):
                             _raise_typed("RuntimeError: exception did not match handler")
                         _raise_typed("RuntimeError: invalid exception value")'''


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

    if label == "dynamic exception reraising" and count == 0:
        compact_count = source.count(_DYNAMIC_EXCEPTION_COMPACT)
        if compact_count != 1:
            raise RuntimeError(
                "dynamic exception reraising: neither canonical nor compact "
                f"source form is unique; compact matches={compact_count}"
            )
        print("REPLACED", label, compact_count, "compact form")
        return source.replace(
            _DYNAMIC_EXCEPTION_COMPACT,
            _DYNAMIC_EXCEPTION_TARGET,
            1,
        )

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
        result = _base.main()
        if result not in (None, 0):
            return int(result)
        return normalize_pattern_constructor_collisions()
    finally:
        _base._replace = previous


if __name__ == "__main__":
    raise SystemExit(main())
