"""Canonicalize frontend MAKE_FUNCTION constants to four native-safe fields.

The pinned compiler cannot safely lower ``len(node.args.defaults)`` because the
opaque AST attribute is mistaken for text and measured with ``strlen``. Count
default expressions while emitting them, and give every function/lambda the
same fixed specification layout:
``[code, default_count, kw_default_count, annotations]``.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")

_LAMBDA_OLD = '''            for default in node.args.defaults:
                self.expr(default)
            self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), len(node.args.defaults), 0)))
'''
_LAMBDA_NEW = '''            lambda_default_count = 0
            for default in node.args.defaults:
                self.expr(default)
                lambda_default_count += 1
            self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), lambda_default_count, 0, {})))
'''
_FUNCTION_DEFAULTS_OLD = '''            for default in node.args.defaults:
                self.expr(default)
            kw_default_count = 0
'''
_FUNCTION_DEFAULTS_NEW = '''            default_count = 0
            for default in node.args.defaults:
                self.expr(default)
                default_count += 1
            kw_default_count = 0
'''
_FUNCTION_SPEC_OLD = (
    "self.constant((nested.finish(), len(node.args.defaults), "
    "kw_default_count, annotations))"
)
_FUNCTION_SPEC_NEW = (
    "self.constant((nested.finish(), default_count, "
    "kw_default_count, annotations))"
)


def _replace_one(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"native frontend {label} expected one source shape, found {count}")
    return source.replace(old, new, 1)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    source = _replace_one(source, _LAMBDA_OLD, _LAMBDA_NEW, "lambda defaults")
    source = _replace_one(
        source,
        _FUNCTION_DEFAULTS_OLD,
        _FUNCTION_DEFAULTS_NEW,
        "function defaults",
    )
    source = _replace_one(
        source,
        _FUNCTION_SPEC_OLD,
        _FUNCTION_SPEC_NEW,
        "function specification",
    )
    PATH.write_text(source, encoding="utf-8")

    forbidden = (
        "self.constant((nested.finish(), len(node.args.defaults)",
        _LAMBDA_OLD,
        _FUNCTION_DEFAULTS_OLD,
    )
    remaining = [marker for marker in forbidden if marker in source]
    if remaining:
        raise RuntimeError(f"native frontend unsafe function specs remain: {remaining}")
    required = (
        "lambda_default_count += 1",
        "(nested.finish(), lambda_default_count, 0, {})",
        "default_count += 1",
        "(nested.finish(), default_count, kw_default_count, annotations)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native frontend function spec validation failed: {missing}")
    print("CANONICALIZED NATIVE FUNCTION SPECS", 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
