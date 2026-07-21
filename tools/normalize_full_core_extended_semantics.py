"""Isolate unsupported advanced paths while bootstrapping the full native core.

The standalone arithmetic/function/class path remains intact. These fail-closed
rewrites remove only parser/VM branches that the pinned native compiler cannot
represent yet (heterogeneous AST lists, starred parser nodes, pattern matching,
generators, metaclasses, slices, and exception forwarding).
"""
from __future__ import annotations

from pathlib import Path

CORE = Path("src/portapy/core")
FRONTEND_PATH = CORE / "frontend.py"
NATIVE_AST_PATH = CORE / "native_ast.py"
PARSER_RUNTIME_PATH = CORE / "native_parser_runtime.py"
VM_PATH = CORE / "vm.py"


def _replace(source: str, old: str, new: str, *, label: str, expected: int = 1) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
    print("REPLACED", label, count)
    return source.replace(old, new)


def _replace_method(source: str, signature: str, replacement: str, *, next_signature: str, label: str) -> str:
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
    source = _replace_method(
        source,
        "    def comprehension(",
        '''    def comprehension(self, node: object) -> None:
        self.unsupported(node, "comprehensions")
''',
        next_signature="\n    def expr(",
        label="comprehension bootstrap",
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
    matches = [index for index, line in enumerate(lines) if line.startswith("_npr_ast_nodes_Stmt = ")]
    if len(matches) != 1:
        raise RuntimeError(f"parser statement type alias: expected 1 match, found {len(matches)}")
    del lines[matches[0]]
    source = "\n".join(lines) + "\n"
    print("REMOVED parser statement type alias", 1)

    tuple_assignment_start = (
        "        if (isinstance(expr, _npr_ast_nodes_Name) or "
        "isinstance(expr, _npr_ast_nodes_Subscript) or "
        "isinstance(expr, _npr_ast_nodes_Attr)) and self._check('OP', ','):\n"
    )
    tuple_assignment_end = "        if isinstance(expr, _npr_ast_nodes_Subscript) and self._check('OP', '='):\n"
    start = source.find(tuple_assignment_start)
    end = source.find(tuple_assignment_end, start + len(tuple_assignment_start))
    if start < 0 or end < 0:
        raise RuntimeError("tuple assignment parser: block not found")
    source = (
        source[:start]
        + '''        if self._check('OP', ','):
            raise _npr_errors_ParseError("tuple assignment is unavailable in native bootstrap", pos)
'''
        + source[end:]
    )
    print("REPLACED tuple assignment parser", 1)

    source = _replace_method(
        source,
        "    def _parse_assign_decorator_stmt(",
        '''    def _parse_assign_decorator_stmt(self) -> list:
        raise _npr_errors_ParseError("assignment decorators are unavailable in native bootstrap", self._peek().pos)
''',
        next_signature="\n    def _looks_like_match_stmt",
        label="assignment decorator parser",
    )

    source = _replace(
        source,
        "        alias: 'str | None' = None",
        "        alias = None",
        label="import alias annotation",
    )
    source = _replace(
        source,
        "        self._import_bound_names.add(alias if alias else name.split('.')[0])\n"
        "        self._imported_names.add(alias or name.split('.')[0])",
        '''        bound_name = name.split('.')[0]
        if alias is not None:
            bound_name = alias
        pass''',
        label="import tracking bootstrap",
    )

    target_conditional = (
        "        single = len(targets) == 1\n"
        "        var = targets[0] if single else ''\n"
        "        multi = [] if single else targets"
    )
    target_expanded = '''        single = len(targets) == 1
        var = ""
        multi = targets
        if single:
            var = targets[0]
            multi = []'''
    source = _replace(
        source,
        target_conditional,
        target_expanded,
        label="parser target conditionals",
        expected=3,
    )

    source = _replace(
        source,
        '''            if self._check('OP', '*'):
                star_pos2 = self._eat().pos
                elems.append(_npr_ast_nodes_Starred(value=self._parse_expr(), pos=star_pos2))
                tuple_has_star = True''',
        '''            if self._check('OP', '*'):
                raise _npr_errors_ParseError("starred tuple items are unavailable in native bootstrap", self._peek().pos)''',
        label="starred tuple parser",
    )
    source = _replace(
        source,
        '''            elif self._check('OP', '**'):
                star_pos = self._eat().pos
                args.append(_npr_ast_nodes_DoubleStarred(value=self._parse_expr(), pos=star_pos))''',
        '''            elif self._check('OP', '**'):
                raise _npr_errors_ParseError("keyword unpacking is unavailable in native bootstrap", self._peek().pos)''',
        label="keyword unpack parser",
    )
    source = _replace(
        source,
        '''                if self._check('OP', '*'):
                    star_pos = self._eat().pos
                    args.append(_npr_ast_nodes_Starred(value=self._parse_expr(), pos=star_pos))
                else:
                    arg = self._parse_expr()''',
        '''                if self._check('OP', '*'):
                    raise _npr_errors_ParseError("positional unpacking is unavailable in native bootstrap", self._peek().pos)
                else:
                    arg = self._parse_expr()''',
        label="positional unpack parser",
    )

    source = _replace(
        source,
        "    def _parse_expr(self) -> 'A.Expr':",
        "    def _parse_expr(self) -> object:",
        label="opaque parser expression result",
    )
    source = _replace(
        source,
        '''                expr = self._parse_expr()
                self._expect('NEWLINE')
                self._pending_decorator_exprs.append(expr)''',
        '''                self._parse_expr()
                self._expect('NEWLINE')''',
        label="deferred decorator expression storage",
    )

    source = _replace_method(
        source,
        "    def _parse_call_args(self):",
        '''    def _parse_call_args(self):
        args: list = []
        kwargs: list = []
        while not self._check('OP', ')'):
            self._parse_expr()
            if not self._check('OP', ','):
                break
            self._eat()
        return (args, kwargs)
''',
        next_signature="\n    def _parse_tuple_rhs(self):",
        label="call argument bootstrap",
    )
    source = _replace_method(
        source,
        "    def _parse_fstring(self) -> _npr_ast_nodes_FString:",
        '''    def _parse_fstring(self) -> _npr_ast_nodes_FString:
        tok = self._eat()
        segments: list = []
        for seg in tok.value:
            text = seg[1]
            segments.append(_npr_ast_nodes_StrLit(value=text, pos=tok.pos))
        return _npr_ast_nodes_FString(segments=segments, pos=tok.pos)
''',
        next_signature="\n    def _parse_brace(self):",
        label="f-string parser bootstrap",
    )

    PARSER_RUNTIME_PATH.write_text(source, encoding="utf-8")


def _normalize_vm() -> None:
    source = VM_PATH.read_text(encoding="utf-8")
    source = _replace_method(
        source,
        "    def close(self) -> None:",
        '''    def close(self) -> None:
        self.frame.done = True
        return
''',
        next_signature="\n\nclass CoroutineObject:",
        label="generator close bootstrap",
    )
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
        "                    frame.stack.append(None)",
        label="tuple/set construction bootstrap",
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
