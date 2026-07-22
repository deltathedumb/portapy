"""Canonicalize every frontend MAKE_FUNCTION constant to four fields.

Normal function definitions already emit ``(code, defaults, kw_defaults,
annotations)``. Lambdas historically emitted only three fields. The native VM
cannot safely inspect the runtime container shape because tuple constants are
materialized as native lists and the pinned compiler lowers ``len(spec)`` to
``strlen``. Give every producer the same fixed layout instead.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")

_OLD_LAMBDA = (
    "            self.emit(Op.MAKE_FUNCTION, "
    "self.constant((nested.finish(), len(node.args.defaults), 0)))"
)
_NEW_LAMBDA = (
    "            self.emit(Op.MAKE_FUNCTION, "
    "self.constant((nested.finish(), len(node.args.defaults), 0, {})))"
)
_NORMAL_FUNCTION_MARKER = (
    "self.constant((nested.finish(), len(node.args.defaults), "
    "kw_default_count, annotations))"
)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    lambda_count = source.count(_OLD_LAMBDA)
    if lambda_count != 1:
        raise RuntimeError(
            "native frontend lambda function spec expected one three-field "
            f"producer, found {lambda_count}"
        )
    normal_count = source.count(_NORMAL_FUNCTION_MARKER)
    if normal_count != 1:
        raise RuntimeError(
            "native frontend function spec expected one four-field producer, "
            f"found {normal_count}"
        )

    source = source.replace(_OLD_LAMBDA, _NEW_LAMBDA, 1)
    PATH.write_text(source, encoding="utf-8")

    if _OLD_LAMBDA in source:
        raise RuntimeError("native frontend still emits a three-field lambda spec")
    if source.count(_NEW_LAMBDA) != 1 or source.count(_NORMAL_FUNCTION_MARKER) != 1:
        raise RuntimeError("native frontend four-field function specs were not preserved")
    print("CANONICALIZED NATIVE FUNCTION SPECS", lambda_count + normal_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
