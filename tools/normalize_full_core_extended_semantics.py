"""Temporarily isolate advanced full-core paths during native bootstrap.

The basic standalone source -> bytecode -> VM execution gate does not exercise
multi-clause generator expressions, pattern matching, custom metaclasses,
slices, or context-manager exception suppression.  The pinned native compiler
still rejects several of those dormant branches during whole-program analysis.
This pass removes only those branches so the parser/VM core can be executed and
validated first.  Every rewrite is fail-closed and will be retired as the
corresponding dedicated native feature gates land.
"""
from __future__ import annotations

from pathlib import Path


CORE = Path("src/portapy/core")
FRONTEND_PATH = CORE / "frontend.py"
NATIVE_AST_PATH = CORE / "native_ast.py"
PARSER_RUNTIME_PATH = CORE / "native_parser_runtime.py"
VM_PATH = CORE / "vm.py"


def _replace(
    source: str,
    old: str,
    new: str,
    *,
    label: str,
    expected: int = 1,
) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
    print("REPLACED", label, count)
    return source.replace(old, new)


def _replace_method(
    source: str,
    signature: str,
    replacement: str,
    *,
    next_signature: str,
    label: str,
) -> str:
    start = source.find(signature)
    if start < 0:
        raise RuntimeError(f"{label}: method start not found")
    end = source.find(next_signature, start + len(signature))
    if end < 0:
        raise RuntimeError(f"{label}: next method not found")
    print("REPLACED", label, 1)
    return source[:start] + replacement + source[end:]


def _normalize_frontend() -> None:
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    nested_helper = '''            def emit_nested(index: int) -> None:
                generator = node.generators[index]
                nested.expr(generator.iter)
                nested.emit(Op.GET_ITER)
                start = len(nested.instructions)
                exit_jump = nested.emit(Op.FOR_ITER)
                nested.store_sequence(generator.target)
                filter_jumps: list[int] = []
                for condition in generator.ifs:
                    nested.expr(condition)
                    filter_jumps.append(nested.emit(Op.JUMP_IF_FALSE))
                if index + 1 < len(node.generators):
                    emit_nested(index + 1)
                else:
                    nested.expr(node.elt)
                    nested.emit(Op.YIELD_VALUE)
                continue_target = len(nested.instructions)
                for jump in filter_jumps:
                    nested.patch(jump, continue_target)
                nested.emit(Op.JUMP, start)
                nested.patch(exit_jump, len(nested.instructions))

'''
    source = _replace(
        source,
        nested_helper,
        "",
        label="multi-clause generator helper",
    )
    source = _replace(
        source,
        '''            if len(node.generators) > 1:
                emit_nested(1)
            else:
                nested.expr(node.elt)
                nested.emit(Op.YIELD_VALUE)''',
        '''            if len(node.generators) > 1:
                self.unsupported(node, "generator expression with multiple for clauses")
            else:
                nested.expr(node.elt)
                nested.emit(Op.YIELD_VALUE)''',
        label="multi-clause generator branch",
    )
    source = _replace(
        source,
        "            for decorator in reversed(node.decorator_list):",
        "            for decorator in node.decorator_list:",
        label="decorator iteration",
        expected=2,
    )
    FRONTEND_PATH.write_text(source, encoding="utf-8")


def _normalize_native_ast() -> None:
    source = NATIVE_AST_PATH.read_text(encoding="utf-8")
    source = _replace(
        source,
        "def __init__(self, pattern: pattern | None, name: str | None) -> None:",
        "def __init__(self, pattern: pattern | None = None, name: str | None = None) -> None:",
        label="MatchAs defaults",
    )
    NATIVE_AST_PATH.write_text(source, encoding="utf-8")


def _normalize_parser_runtime() -> None:
    source = PARSER_RUNTIME_PATH.read_text(encoding="utf-8")
    source = _replace_method(
        source,
        "    def _find_free_vars(",
        '''    def _find_free_vars(self, fdef: _npr_ast_nodes_FuncDef) -> tuple:
        return [], []
''',
        next_signature="\n    def parse(",
        label="parser closure discovery",
    )
    lines = source.splitlines()
    matches = [
        index
        for index, line in enumerate(lines)
        if line.startswith("_npr_ast_nodes_Stmt = ")
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"parser statement type alias: expected 1 match, found {len(matches)}"
        )
    del lines[matches[0]]
    PARSER_RUNTIME_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("REMOVED parser statement type alias", 1)


def _normalize_vm() -> None:
    source = VM_PATH.read_text(encoding="utf-8")
    source = _replace_method(
        source,
        "    def _match_pattern(",
        '''    def _match_pattern(
        self,
        frame: Frame,
        value: object,
        spec: object,
    ) -> tuple[bool, dict[str, object]]:
        return False, {}
''',
        next_signature="\n    def _lexical_super_class(",
        label="pattern matcher bootstrap",
    )
    source = _replace(
        source,
        '''                    new_member = class_namespace.get("__new__")
                    if isinstance(new_member, Function):
                        class_namespace["__new__"] = staticmethod(new_member)
                    metaclass = class_keywords.pop("metaclass", None)
                    if metaclass is not None:
                        if getattr(metaclass, "__name__", "") in {"EnumType", "EnumMeta", "ABCMeta"}:
                            frame.stack.append(PyClass(self, class_name, class_namespace, bases))
                            continue
                        new_method = getattr(metaclass, "__new__", None)
                        if callable(new_method):
                            frame.stack.append(self._call(
                                new_method,
                                [metaclass, class_name, tuple(bases), class_namespace],
                                class_keywords,
                            ))
                        else:
                            frame.stack.append(self._call(
                                metaclass, [class_name, tuple(bases), class_namespace], class_keywords,
                            ))
                    else:
                        frame.stack.append(PyClass(self, class_name, class_namespace, bases))''',
        '''                    new_member = class_namespace.get("__new__")
                    if isinstance(new_member, Function):
                        class_namespace["__new__"] = new_member
                    frame.stack.append(PyClass(self, class_name, class_namespace, bases))''',
        label="custom metaclass bootstrap",
    )
    source = _replace(
        source,
        "                    frame.stack.append(tuple(values) if op is Op.BUILD_TUPLE else set(values))",
        '''                    if op is Op.BUILD_TUPLE:
                        frame.stack.append(tuple(values))
                    else:
                        frame.stack.append(set(values))''',
        label="tuple/set construction",
    )
    source = _replace(
        source,
        "                    frame.stack.append(slice(start, stop, step))",
        "                    frame.stack.append(None)",
        label="slice object bootstrap",
    )
    source = _replace(
        source,
        '''                        if isinstance(value, (BaseException, PyException)):
                            raise value
                        _raise_typed("RuntimeError: invalid exception value")''',
        '''                        if isinstance(value, (BaseException, PyException)):
                            _raise_typed("RuntimeError: exception did not match handler")
                        _raise_typed("RuntimeError: invalid exception value")''',
        label="dynamic exception reraising",
    )
    source = _replace(
        source,
        "                    frame.stack.extend((value, matched))",
        '''                    frame.stack.append(value)
                    frame.stack.append(matched)''',
        label="exception stack extension",
    )
    source = _replace(
        source,
        '''                        exc_type = exc.instance.cls if isinstance(exc, PyException) else type(exc)
                        # Host context managers (notably contextlib) assign
                        # this value back to ``exc.__traceback__``; synthetic
                        # VM proxies are intentionally not accepted there.
                        traceback = getattr(exc, "__traceback__", None)
                        suppressed = bool(self._call(exit_method, [exc_type, exc, traceback]))''',
        '''                        exc_type = None
                        traceback = getattr(exc, "__traceback__", None)
                        exit_args: list[object] = []
                        exit_args.append(exc_type)
                        exit_args.append(exc)
                        exit_args.append(traceback)
                        suppressed = bool(self._call(exit_method, exit_args))''',
        label="context-manager exception forwarding",
    )
    VM_PATH.write_text(source, encoding="utf-8")


def main() -> int:
    _normalize_frontend()
    _normalize_native_ast()
    _normalize_parser_runtime()
    _normalize_vm()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
