"""Preserve real VM TypeError exceptions at the public native ABI boundary."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/reference_api.py")


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
            if not isinstance(statement, ast.Try):
                continue
            if not any(
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Call)
                and isinstance(item.value.func, ast.Attribute)
                and item.value.func.attr == "run"
                for item in statement.body
            ):
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
                body=[
                    ast.Return(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="self", ctx=ast.Load()),
                                attr="_capture_native",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Attribute(
                                    value=ast.Name(id="Status", ctx=ast.Load()),
                                    attr="TYPE_ERROR",
                                    ctx=ast.Load(),
                                ),
                                ast.Constant("TypeError"),
                                ast.Constant("PortaPy type error"),
                            ],
                            keywords=[],
                        )
                    )
                ],
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
    text = ast.unparse(method)
    required = (
        "except TypeError as error:",
        "Status.TYPE_ERROR",
        "self._capture_native(",
        "except BaseException as error:",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(
            f"native reference TypeError validation failed: {missing}"
        )
    if text.find("except TypeError as error:") > text.find(
        "except BaseException as error:"
    ):
        raise RuntimeError("native TypeError handler follows the broad handler")
    print("NORMALIZED NATIVE REFERENCE TYPE ERRORS", rewriter.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
