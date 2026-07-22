"""Canonicalize frontend MAKE_FUNCTION constants to native-safe fields.

The pinned compiler cannot safely infer either the length or element type of the
opaque AST default lists.  Count defaults while emitting them and read every
positional, keyword-only, and lambda default through an explicitly typed
``list[dict]`` so real AST node pointers reach ``_Lowerer.expr``.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")

_LAMBDA_OLD = '''            for default in node.args.defaults:
                self.expr(default)
            self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), len(node.args.defaults), 0)))
'''
_LAMBDA_NEW = '''            lambda_defaults: list[dict] = getattr(node.args, "defaults")
            lambda_default_count = 0
            lambda_default_index = 0
            while lambda_default_index < len(lambda_defaults):
                lambda_default: dict = lambda_defaults[lambda_default_index]
                self.expr(lambda_default)
                lambda_default_count += 1
                lambda_default_index += 1
            self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), lambda_default_count, 0, {})))
'''
_FUNCTION_DEFAULTS_OLD = '''            for default in node.args.defaults:
                self.expr(default)
            kw_default_count = 0
'''
_FUNCTION_DEFAULTS_NEW = '''            function_defaults: list[dict] = getattr(node.args, "defaults")
            default_count = 0
            default_index = 0
            while default_index < len(function_defaults):
                function_default: dict = function_defaults[default_index]
                self.expr(function_default)
                default_count += 1
                default_index += 1
            kw_default_count = 0
'''
_KW_DEFAULTS_OLD = '''            for default in node.args.kw_defaults:
                if default is None:
                    continue
                self.expr(default)
                kw_default_count += 1
'''
_KW_DEFAULTS_NEW = '''            keyword_defaults: list[dict] = getattr(node.args, "kw_defaults")
            keyword_default_index = 0
            while keyword_default_index < len(keyword_defaults):
                keyword_default: dict = keyword_defaults[keyword_default_index]
                if keyword_default is not None:
                    self.expr(keyword_default)
                    kw_default_count += 1
                keyword_default_index += 1
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
        _KW_DEFAULTS_OLD,
        _KW_DEFAULTS_NEW,
        "keyword-only defaults",
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
        _KW_DEFAULTS_OLD,
        "for default in node.args.defaults:",
        "for default in node.args.kw_defaults:",
    )
    remaining = [marker for marker in forbidden if marker in source]
    if remaining:
        raise RuntimeError(f"native frontend unsafe function specs remain: {remaining}")
    required = (
        'lambda_defaults: list[dict] = getattr(node.args, "defaults")',
        "lambda_default: dict = lambda_defaults[lambda_default_index]",
        "lambda_default_count += 1",
        "(nested.finish(), lambda_default_count, 0, {})",
        'function_defaults: list[dict] = getattr(node.args, "defaults")',
        "function_default: dict = function_defaults[default_index]",
        "default_count += 1",
        'keyword_defaults: list[dict] = getattr(node.args, "kw_defaults")',
        "keyword_default: dict = keyword_defaults[keyword_default_index]",
        "(nested.finish(), default_count, kw_default_count, annotations)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native frontend function spec validation failed: {missing}")
    print("CANONICALIZED NATIVE FUNCTION SPECS", 3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
