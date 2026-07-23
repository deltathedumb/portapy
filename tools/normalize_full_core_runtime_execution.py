"""Install explicit native execution state for iteration, closures, and exceptions.

The pinned compiler's generic ``iter``/``next`` lowering does not retain iterator
state for untagged runtime lists. The same limitation affects Python ``for`` loops
inside the VM itself, including closure capture. Native low-level exception
handlers also expose the runtime error message rather than a Python exception
object. This final AST pass replaces the critical paths with explicit indexed
state, wraps caught messages in a native object carrying traceback metadata, and
transports unresolved-name errors to the public ABI without relying on erased
native exception classes.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/vm.py")
_ITERATOR = "_NativeSequenceIterator"
_EXCEPTION = "_NativeCaughtException"
_ERROR_KIND = "_native_error_kind"

_HELPERS = '''
class _NativeSequenceIterator:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.index = 0


class _NativeCaughtException:
    def __init__(self, message: object) -> None:
        self.message = message
        self.__traceback__ = True
'''


def _is_attribute(node: ast.AST, owner: str, name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
    )


def _is_opcode_branch(node: ast.If, opcode: str) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "op"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and len(test.comparators) == 1
        and _is_attribute(test.comparators[0], "Op", opcode)
    )


def _is_closure_capture_loop(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "name"
        and isinstance(node.iter, ast.Attribute)
        and node.iter.attr == "free_names"
        and isinstance(node.iter.value, ast.Name)
        and node.iter.value.id == "nested"
    )


def _install_helpers(tree: ast.Module) -> int:
    existing = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in {_ITERATOR, _EXCEPTION}
    }
    if existing:
        raise RuntimeError(f"native execution helpers already exist: {sorted(existing)}")
    helpers = ast.parse(_HELPERS).body
    tree.body.extend(helpers)
    return len(helpers)


def _runtime_method(runtime: ast.ClassDef, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in runtime.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"native execution expected one VirtualMachine.{name}, found {len(matches)}"
        )
    return matches[0]


def _install_error_kind_transport(tree: ast.Module) -> tuple[int, int, int]:
    runtimes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "VirtualMachine"
    ]
    if len(runtimes) != 1:
        raise RuntimeError(
            f"native execution expected one VirtualMachine class, found {len(runtimes)}"
        )
    runtime = runtimes[0]
    initializer = _runtime_method(runtime, "__init__")
    lookup = _runtime_method(runtime, "_lookup")
    run_frame = _runtime_method(runtime, "_run_frame")

    if _ERROR_KIND in ast.unparse(runtime):
        raise RuntimeError("native error-kind transport is already installed")

    initializer.body.append(ast.parse(f'self.{_ERROR_KIND} = ""').body[0])

    raises = [
        index
        for index, statement in enumerate(lookup.body)
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "_raise_typed"
    ]
    if len(raises) != 1:
        raise RuntimeError(
            f"native lookup expected one terminal typed raise, found {len(raises)}"
        )
    lookup.body.insert(
        raises[0],
        ast.parse(f'self.{_ERROR_KIND} = "NameError"').body[0],
    )

    loops = [statement for statement in run_frame.body if isinstance(statement, ast.While)]
    if len(loops) != 1:
        raise RuntimeError(
            f"native frame execution expected one instruction loop, found {len(loops)}"
        )
    loops[0].body.insert(0, ast.parse(f'self.{_ERROR_KIND} = ""').body[0])
    return 1, 1, 1


class _OpcodeRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.get_iter = 0
        self.for_iter = 0
        self.closure_loops = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if _is_opcode_branch(node, "GET_ITER"):
            node.body = ast.parse(
                "sequence: list[object] = frame.stack.pop()\n"
                "frame.stack.append(_NativeSequenceIterator(sequence))\n"
            ).body
            self.get_iter += 1
        elif _is_opcode_branch(node, "FOR_ITER"):
            node.body = ast.parse(
                "if not frame.stack:\n"
                "    frame.ip = instr.arg\n"
                "    continue\n"
                "iterator: _NativeSequenceIterator = frame.stack[-1]\n"
                "if iterator.index >= len(iterator.values):\n"
                "    frame.stack.pop()\n"
                "    frame.ip = instr.arg\n"
                "else:\n"
                "    value = iterator.values[iterator.index]\n"
                "    iterator.index += 1\n"
                "    frame.stack.append(value)\n"
            ).body
            self.for_iter += 1
        elif _is_opcode_branch(node, "MAKE_FUNCTION"):
            replacements: list[ast.stmt] = []
            found = 0
            for statement in node.body:
                if not _is_closure_capture_loop(statement):
                    replacements.append(statement)
                    continue
                replacements.extend(
                    ast.parse(
                        "closure_index = 0\n"
                        "while closure_index < len(nested.free_names):\n"
                        "    name = nested.free_names[closure_index]\n"
                        "    if name in frame.locals:\n"
                        "        closure[name] = frame.locals[name]\n"
                        "    elif frame.closure is not None and name in frame.closure:\n"
                        "        closure[name] = frame.closure[name]\n"
                        "    closure_index += 1\n"
                    ).body
                )
                found += 1
            if found != 1:
                raise RuntimeError(
                    f"native MAKE_FUNCTION closure loop expected once, found {found}"
                )
            node.body = replacements
            self.closure_loops += found
        return node


class _ExceptionRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.in_run_frame = False
        self.catches = 0
        self.matchers = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        previous = self.in_run_frame
        self.in_run_frame = node.name == "_run_frame"
        self.generic_visit(node)
        self.in_run_frame = previous
        if node.name == "_exception_matches":
            guard = ast.parse(
                "if isinstance(value, _NativeCaughtException):\n"
                "    return True\n"
            ).body[0]
            node.body.insert(0, guard)
            self.matchers += 1
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        self.generic_visit(node)
        if not self.in_run_frame:
            return node
        if not (
            node.name == "exc"
            and isinstance(node.type, ast.Name)
            and node.type.id == "BaseException"
        ):
            return node
        node.body.insert(
            0,
            ast.Assign(
                targets=[ast.Name(id="exc", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id=_EXCEPTION, ctx=ast.Load()),
                    args=[ast.Name(id="exc", ctx=ast.Load())],
                    keywords=[],
                ),
            ),
        )
        self.catches += 1
        return node


def main() -> int:
    tree = ast.parse(PATH.read_text(encoding="utf-8"), filename=str(PATH))
    helper_count = _install_helpers(tree)
    error_kind = _install_error_kind_transport(tree)
    opcode = _OpcodeRewrite()
    tree = opcode.visit(tree)
    exceptions = _ExceptionRewrite()
    tree = exceptions.visit(tree)

    counts = (
        helper_count,
        opcode.get_iter,
        opcode.for_iter,
        opcode.closure_loops,
        exceptions.catches,
        exceptions.matchers,
        *error_kind,
    )
    if counts != (2, 1, 1, 1, 1, 1, 1, 1, 1):
        raise RuntimeError(
            "native execution normalization expected helpers/get-iter/for-iter/"
            f"closure/catch/matcher/error-kind transport once; found {counts}"
        )

    ast.fix_missing_locations(tree)
    source = ast.unparse(tree) + "\n"
    PATH.write_text(source, encoding="utf-8")

    required = (
        "class _NativeSequenceIterator:",
        "class _NativeCaughtException:",
        "frame.stack.append(_NativeSequenceIterator(sequence))",
        "iterator: _NativeSequenceIterator = frame.stack[-1]",
        "value = iterator.values[iterator.index]",
        "while closure_index < len(nested.free_names):",
        "exc = _NativeCaughtException(exc)",
        "if isinstance(value, _NativeCaughtException):",
        "self.__traceback__ = True",
        "self._native_error_kind = 'NameError'",
        "self._native_error_kind = ''",
    )
    missing = [marker for marker in required if marker not in source]
    forbidden = (
        "frame.stack.append(iter(value))",
        "frame.stack.append(next(frame.stack[-1]))",
        "for name in nested.free_names:",
    )
    remaining = [marker for marker in forbidden if marker in source]
    if missing or remaining:
        raise RuntimeError(
            f"native execution validation failed: missing={missing}, "
            f"remaining={remaining}"
        )

    print("NORMALIZED NATIVE RUNTIME EXECUTION", *counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
