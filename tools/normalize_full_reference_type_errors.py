"""Preserve real VM TypeError exceptions at the public native ABI boundary."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/reference_api.py")


def _is_vm_run_try(statement: ast.stmt) -> bool:
    return isinstance(statement, ast.Try) and any(
        isinstance(item, ast.Expr)
        and isinstance(item.value, ast.Call)
        and isinstance(item.value.func, ast.Attribute)
        and item.value.func.attr == "run"
        for item in statement.body
    )


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        if node.name != "Runtime":
            return node
        method = next(
            (
                item
                for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name == "exec_utf8"
            ),
            None,
        )
        if method is None:
            raise RuntimeError("reference Runtime.exec_utf8 is missing")
        for statement in method.body:
            if not _is_vm_run_try(statement):
                continue
            broad_index = next(
                (
                    index
                    for index, handler in enumerate(statement.handlers)
                    if isinstance(handler.type, ast.Name)
                    and handler.type.id == "BaseException"
                ),
                -1,
            )
            if broad_index < 0:
                raise RuntimeError(
                    "reference Runtime.exec_utf8 has no BaseException handler"
                )
            if any(
                isinstance(handler.type, ast.Name)
                and handler.type.id == "TypeError"
                for handler in statement.handlers
            ):
                raise RuntimeError(
                    "reference Runtime.exec_utf8 already preserves TypeError"
                )
            handler = ast.ExceptHandler(
                type=ast.Name(id="TypeError", ctx=ast.Load()),
                name="error",
                body=ast.parse(
                    '''if self._vm._native_error_kind == "NameError":
    return self._capture_native(
        Status.NOT_FOUND,
        "NameError",
        error,
    )
return self._capture_native(
    Status.TYPE_ERROR,
    "TypeError",
    error,
)
'''
                ).body,
            )
            statement.handlers.insert(broad_index, handler)
            self.count += 1
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    if rewriter.count != 1:
        raise RuntimeError(
            "native reference TypeError normalization expected 1 handler, "
            f"found {rewriter.count}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    runtime = next(
        node
        for node in verified.body
        if isinstance(node, ast.ClassDef) and node.name == "Runtime"
    )
    method = next(
        node
        for node in runtime.body
        if isinstance(node, ast.FunctionDef) and node.name == "exec_utf8"
    )
    run_try = next(
        statement for statement in method.body if _is_vm_run_try(statement)
    )
    handler_names = [
        handler.type.id if isinstance(handler.type, ast.Name) else ""
        for handler in run_try.handlers
    ]
    required_handlers = ("TypeError", "BaseException")
    missing = [name for name in required_handlers if name not in handler_names]
    if missing:
        raise RuntimeError(
            f"native reference TypeError validation failed: {missing}"
        )
    if handler_names.index("TypeError") > handler_names.index("BaseException"):
        raise RuntimeError("native TypeError handler follows the broad handler")

    type_handler = run_try.handlers[handler_names.index("TypeError")]
    text = ast.unparse(type_handler)
    required_markers = (
        "except TypeError as error:",
        "self._vm._native_error_kind == 'NameError'",
        "Status.NOT_FOUND",
        "Status.TYPE_ERROR",
        "self._capture_native(",
        "'NameError', error",
        "'TypeError', error",
    )
    missing_markers = [marker for marker in required_markers if marker not in text]
    if missing_markers:
        raise RuntimeError(
            f"native reference TypeError validation failed: {missing_markers}"
        )
    generic_markers = ("PortaPy name not found", "PortaPy type error")
    remaining = [marker for marker in generic_markers if marker in text]
    if remaining:
        raise RuntimeError(
            f"native TypeError detail is still replaced: {remaining}"
        )
    print("NORMALIZED NATIVE REFERENCE TYPE ERRORS", rewriter.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
