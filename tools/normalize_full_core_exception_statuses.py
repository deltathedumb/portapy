"""Preserve escaping exception identity and map missing names at the native ABI.

The native execution-state pass wraps caught low-level exceptions so interpreted
``try`` handlers have a stable object.  Overwriting the catch variable also makes
an unhandled exception escape as that untyped wrapper, causing the public Runtime
boundary to classify a NameError as TypeError.  Keep the original exception for
bare re-raise, create the wrapper only when dispatching into a bytecode handler,
and add the corresponding NOT_FOUND mapping at the public ABI boundary.
"""
from __future__ import annotations

import ast
from pathlib import Path


VM_PATH = Path("src/portapy/core/vm.py")
REFERENCE_PATH = Path("src/portapy/reference_api.py")
_EXCEPTION = "_NativeCaughtException"
_WRAPPED_NAME = "native_exception"


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_exc_wrapper_assignment(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and _is_name(node.targets[0], "exc")
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == _EXCEPTION
        and len(node.value.args) == 1
        and _is_name(node.value.args[0], "exc")
    )


def _is_stack_append_exc(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "append"
        and isinstance(node.value.func.value, ast.Attribute)
        and node.value.func.value.attr == "stack"
        and _is_name(node.value.func.value.value, "frame")
        and len(node.value.args) == 1
        and _is_name(node.value.args[0], "exc")
    )


def _is_active_exception_exc(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and node.targets[0].attr == "active_exception"
        and _is_name(node.targets[0].value, "frame")
        and _is_name(node.value, "exc")
    )


def _rewrite_statement_lists(statements: list[ast.stmt]) -> tuple[int, int]:
    append_count = 0
    active_count = 0
    index = 0
    while index < len(statements):
        statement = statements[index]
        if _is_stack_append_exc(statement):
            replacement = ast.parse(
                f"{_WRAPPED_NAME} = {_EXCEPTION}(exc)\n"
                f"frame.stack.append({_WRAPPED_NAME})\n"
            ).body
            statements[index:index + 1] = replacement
            append_count += 1
            index += len(replacement)
            continue
        if _is_active_exception_exc(statement):
            statement.value = ast.Name(id=_WRAPPED_NAME, ctx=ast.Load())
            active_count += 1

        child_lists: list[list[ast.stmt]] = []
        for field in ("body", "orelse", "finalbody"):
            value = getattr(statement, field, None)
            if isinstance(value, list):
                child_lists.append(value)
        if isinstance(statement, ast.Try):
            for handler in statement.handlers:
                child_lists.append(handler.body)
        for child in child_lists:
            nested_append, nested_active = _rewrite_statement_lists(child)
            append_count += nested_append
            active_count += nested_active
        index += 1
    return append_count, active_count


def _repair_vm() -> tuple[int, int, int]:
    tree = ast.parse(VM_PATH.read_text(encoding="utf-8"), filename=str(VM_PATH))
    runtime = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "VirtualMachine"
        ),
        None,
    )
    if runtime is None:
        raise RuntimeError("native VirtualMachine class is missing")
    method = next(
        (
            node
            for node in runtime.body
            if isinstance(node, ast.FunctionDef) and node.name == "_run_frame"
        ),
        None,
    )
    if method is None:
        raise RuntimeError("native VirtualMachine._run_frame is missing")
    handlers = [
        handler
        for node in ast.walk(method)
        if isinstance(node, ast.Try)
        for handler in node.handlers
        if handler.name == "exc"
        and isinstance(handler.type, ast.Name)
        and handler.type.id == "BaseException"
        and any(_is_exc_wrapper_assignment(item) for item in handler.body)
    ]
    if len(handlers) != 1:
        raise RuntimeError(
            f"native run-frame wrapper handler expected once, found {len(handlers)}"
        )
    handler = handlers[0]
    before = len(handler.body)
    handler.body = [item for item in handler.body if not _is_exc_wrapper_assignment(item)]
    removed = before - len(handler.body)
    append_count, active_count = _rewrite_statement_lists(handler.body)
    if (removed, append_count, active_count) != (1, 1, 1):
        raise RuntimeError(
            "native exception escape repair expected wrapper/append/active once; "
            f"found {(removed, append_count, active_count)}"
        )

    ast.fix_missing_locations(tree)
    source = ast.unparse(tree) + "\n"
    VM_PATH.write_text(source, encoding="utf-8")
    required = (
        f"{_WRAPPED_NAME} = {_EXCEPTION}(exc)",
        f"frame.stack.append({_WRAPPED_NAME})",
        f"frame.active_exception = {_WRAPPED_NAME}",
    )
    missing = [marker for marker in required if marker not in source]
    if missing or "exc = _NativeCaughtException(exc)" in source:
        raise RuntimeError(
            f"native exception escape validation failed: missing={missing}"
        )
    return removed, append_count, active_count


def _is_vm_run_try(statement: ast.stmt) -> bool:
    return isinstance(statement, ast.Try) and any(
        isinstance(item, ast.Expr)
        and isinstance(item.value, ast.Call)
        and isinstance(item.value.func, ast.Attribute)
        and item.value.func.attr == "run"
        for item in statement.body
    )


def _install_name_error_mapping() -> int:
    tree = ast.parse(
        REFERENCE_PATH.read_text(encoding="utf-8"),
        filename=str(REFERENCE_PATH),
    )
    runtime = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "Runtime"
        ),
        None,
    )
    if runtime is None:
        raise RuntimeError("reference Runtime class is missing")
    method = next(
        (
            node
            for node in runtime.body
            if isinstance(node, ast.FunctionDef) and node.name == "exec_utf8"
        ),
        None,
    )
    if method is None:
        raise RuntimeError("reference Runtime.exec_utf8 is missing")
    run_tries = [statement for statement in method.body if _is_vm_run_try(statement)]
    if len(run_tries) != 1:
        raise RuntimeError(
            f"reference Runtime.exec_utf8 run try expected once, found {len(run_tries)}"
        )
    run_try = run_tries[0]
    existing = [
        handler
        for handler in run_try.handlers
        if isinstance(handler.type, ast.Name) and handler.type.id == "NameError"
    ]
    if existing:
        raise RuntimeError("reference Runtime.exec_utf8 already maps NameError")
    broad_index = next(
        (
            index
            for index, handler in enumerate(run_try.handlers)
            if isinstance(handler.type, ast.Name) and handler.type.id == "BaseException"
        ),
        -1,
    )
    if broad_index < 0:
        raise RuntimeError("reference Runtime.exec_utf8 broad handler is missing")
    handler = ast.parse(
        '''try:
    pass
except NameError as error:
    return self._capture_native(
        Status.NOT_FOUND,
        "NameError",
        "PortaPy name not found",
    )
'''
    ).body[0].handlers[0]
    run_try.handlers.insert(broad_index, handler)

    ast.fix_missing_locations(tree)
    source = ast.unparse(tree) + "\n"
    REFERENCE_PATH.write_text(source, encoding="utf-8")
    verified = ast.parse(source, filename=str(REFERENCE_PATH))
    text = ast.unparse(verified)
    required = (
        "except NameError as error:",
        "Status.NOT_FOUND",
        "'NameError'",
        "'PortaPy name not found'",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"native NameError mapping was lost: {missing}")
    return 1


def main() -> int:
    vm_counts = _repair_vm()
    mapping_count = _install_name_error_mapping()
    print("NORMALIZED NATIVE EXCEPTION STATUSES", *vm_counts, mapping_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
