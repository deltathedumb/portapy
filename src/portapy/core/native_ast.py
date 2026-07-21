"""Standalone AST compatibility layer backed by asmpython's self-hosted parser."""
from __future__ import annotations

from asmpython._compiler.lexer import Lexer
from asmpython._compiler.parser import Parser
from asmpython._compiler import ast_nodes as A


class AST:
    pass
class stmt(AST):
    pass
class expr(AST):
    pass
class pattern(AST):
    pass

class Load(AST): pass
class Store(AST): pass
class Del(AST): pass
class Add(AST): pass
class Sub(AST): pass
class Mult(AST): pass
class Div(AST): pass
class FloorDiv(AST): pass
class Mod(AST): pass
class Pow(AST): pass
class BitAnd(AST): pass
class BitOr(AST): pass
class BitXor(AST): pass
class LShift(AST): pass
class RShift(AST): pass
class MatMult(AST): pass
class Eq(AST): pass
class Lt(AST): pass
class LtE(AST): pass
class Gt(AST): pass
class GtE(AST): pass
class NotEq(AST): pass
class Is(AST): pass
class IsNot(AST): pass
class In(AST): pass
class NotIn(AST): pass
class And(AST): pass
class Or(AST): pass
class Not(AST): pass
class USub(AST): pass
class UAdd(AST): pass
class Invert(AST): pass

class Module(AST):
    def __init__(self, body: list[stmt]) -> None:
        self.body = body
        self.type_ignores: list[object] = []

class Name(expr):
    def __init__(self, id: str, ctx: object = None) -> None:
        self.id = id; self.ctx = Load() if ctx is None else ctx
class Constant(expr):
    def __init__(self, value: object) -> None:
        self.value = value
class BinOp(expr):
    def __init__(self, left: expr, op: object, right: expr) -> None:
        self.left = left; self.op = op; self.right = right
class UnaryOp(expr):
    def __init__(self, op: object, operand: expr) -> None:
        self.op = op; self.operand = operand
class BoolOp(expr):
    def __init__(self, op: object, values: list[expr]) -> None:
        self.op = op; self.values = values
class Compare(expr):
    def __init__(self, left: expr, ops: list[object], comparators: list[expr]) -> None:
        self.left = left; self.ops = ops; self.comparators = comparators
class IfExp(expr):
    def __init__(self, test: expr, body: expr, orelse: expr) -> None:
        self.test = test; self.body = body; self.orelse = orelse
class NamedExpr(expr):
    def __init__(self, target: expr, value: expr) -> None:
        self.target = target; self.value = value
class Attribute(expr):
    def __init__(self, value: expr, attr: str, ctx: object = None) -> None:
        self.value = value; self.attr = attr; self.ctx = Load() if ctx is None else ctx
class Subscript(expr):
    def __init__(self, value: expr, slice: expr, ctx: object = None) -> None:
        self.value = value; self.slice = slice; self.ctx = Load() if ctx is None else ctx
class Slice(expr):
    def __init__(self, lower: expr | None, upper: expr | None, step: expr | None) -> None:
        self.lower = lower; self.upper = upper; self.step = step
class Starred(expr):
    def __init__(self, value: expr, ctx: object = None) -> None:
        self.value = value; self.ctx = Load() if ctx is None else ctx
class List(expr):
    def __init__(self, elts: list[expr], ctx: object = None) -> None:
        self.elts = elts; self.ctx = Load() if ctx is None else ctx
class Tuple(expr):
    def __init__(self, elts: list[expr], ctx: object = None) -> None:
        self.elts = elts; self.ctx = Load() if ctx is None else ctx
class Set(expr):
    def __init__(self, elts: list[expr]) -> None:
        self.elts = elts
class Dict(expr):
    def __init__(self, keys: list[expr | None], values: list[expr]) -> None:
        self.keys = keys; self.values = values
class keyword(AST):
    def __init__(self, arg: str | None, value: expr) -> None:
        self.arg = arg; self.value = value
class Call(expr):
    def __init__(self, func: expr, args: list[expr], keywords: list[keyword]) -> None:
        self.func = func; self.args = args; self.keywords = keywords
class arg(AST):
    def __init__(self, arg: str, annotation: expr | None = None) -> None:
        self.arg = arg; self.annotation = annotation; self.type_comment = None
class arguments(AST):
    def __init__(self, posonlyargs: list[arg], args: list[arg], vararg: arg | None,
                 kwonlyargs: list[arg], kw_defaults: list[expr | None],
                 kwarg: arg | None, defaults: list[expr]) -> None:
        self.posonlyargs = posonlyargs; self.args = args; self.vararg = vararg
        self.kwonlyargs = kwonlyargs; self.kw_defaults = kw_defaults
        self.kwarg = kwarg; self.defaults = defaults
class Lambda(expr):
    def __init__(self, args: arguments, body: expr) -> None:
        self.args = args; self.body = body
class Await(expr):
    def __init__(self, value: expr) -> None: self.value = value
class Yield(expr):
    def __init__(self, value: expr | None) -> None: self.value = value
class YieldFrom(expr):
    def __init__(self, value: expr) -> None: self.value = value
class JoinedStr(expr):
    def __init__(self, values: list[expr]) -> None: self.values = values
class FormattedValue(expr):
    def __init__(self, value: expr, conversion: int = -1, format_spec: expr | None = None) -> None:
        self.value = value; self.conversion = conversion; self.format_spec = format_spec
class TemplateStr(JoinedStr): pass
class Interpolation(FormattedValue): pass

class comprehension(AST):
    def __init__(self, target: expr, iter: expr, ifs: list[expr], is_async: int = 0) -> None:
        self.target = target; self.iter = iter; self.ifs = ifs; self.is_async = is_async
class ListComp(expr):
    def __init__(self, elt: expr, generators: list[comprehension]) -> None:
        self.elt = elt; self.generators = generators
class SetComp(ListComp): pass
class GeneratorExp(ListComp): pass
class DictComp(expr):
    def __init__(self, key: expr, value: expr, generators: list[comprehension]) -> None:
        self.key = key; self.value = value; self.generators = generators

class Expr(stmt):
    def __init__(self, value: expr) -> None: self.value = value
class Assign(stmt):
    def __init__(self, targets: list[expr], value: expr) -> None:
        self.targets = targets; self.value = value; self.type_comment = None
class AnnAssign(stmt):
    def __init__(self, target: expr, annotation: expr, value: expr | None) -> None:
        self.target = target; self.annotation = annotation; self.value = value; self.simple = 1
class AugAssign(stmt):
    def __init__(self, target: expr, op: object, value: expr) -> None:
        self.target = target; self.op = op; self.value = value
class Return(stmt):
    def __init__(self, value: expr | None) -> None: self.value = value
class Raise(stmt):
    def __init__(self, exc: expr | None, cause: expr | None = None) -> None:
        self.exc = exc; self.cause = cause
class Pass(stmt): pass
class Break(stmt): pass
class Continue(stmt): pass
class Global(stmt):
    def __init__(self, names: list[str]) -> None: self.names = names
class Nonlocal(stmt):
    def __init__(self, names: list[str]) -> None: self.names = names
class Delete(stmt):
    def __init__(self, targets: list[expr]) -> None: self.targets = targets
class Assert(stmt):
    def __init__(self, test: expr, msg: expr | None = None) -> None:
        self.test = test; self.msg = msg
class If(stmt):
    def __init__(self, test: expr, body: list[stmt], orelse: list[stmt]) -> None:
        self.test = test; self.body = body; self.orelse = orelse
class While(stmt):
    def __init__(self, test: expr, body: list[stmt], orelse: list[stmt]) -> None:
        self.test = test; self.body = body; self.orelse = orelse
class For(stmt):
    def __init__(self, target: expr, iter: expr, body: list[stmt], orelse: list[stmt]) -> None:
        self.target = target; self.iter = iter; self.body = body; self.orelse = orelse; self.type_comment = None
class AsyncFor(For): pass
class alias(AST):
    def __init__(self, name: str, asname: str | None = None) -> None:
        self.name = name; self.asname = asname
class Import(stmt):
    def __init__(self, names: list[alias]) -> None: self.names = names
class ImportFrom(stmt):
    def __init__(self, module: str | None, names: list[alias], level: int = 0) -> None:
        self.module = module; self.names = names; self.level = level
class withitem(AST):
    def __init__(self, context_expr: expr, optional_vars: expr | None = None) -> None:
        self.context_expr = context_expr; self.optional_vars = optional_vars
class With(stmt):
    def __init__(self, items: list[withitem], body: list[stmt]) -> None:
        self.items = items; self.body = body; self.type_comment = None
class AsyncWith(With): pass
class ExceptHandler(AST):
    def __init__(self, type: expr | None, name: str | None, body: list[stmt]) -> None:
        self.type = type; self.name = name; self.body = body
class Try(stmt):
    def __init__(self, body: list[stmt], handlers: list[ExceptHandler], orelse: list[stmt], finalbody: list[stmt]) -> None:
        self.body = body; self.handlers = handlers; self.orelse = orelse; self.finalbody = finalbody
TryStar = Try
class FunctionDef(stmt):
    def __init__(self, name: str, args: arguments, body: list[stmt],
                 decorator_list: list[expr] | None = None, returns: expr | None = None) -> None:
        self.name = name; self.args = args; self.body = body
        self.decorator_list = [] if decorator_list is None else decorator_list
        self.returns = returns; self.type_comment = None; self.type_params: list[object] = []
class AsyncFunctionDef(FunctionDef): pass
class ClassDef(stmt):
    def __init__(self, name: str, bases: list[expr], body: list[stmt],
                 decorator_list: list[expr] | None = None) -> None:
        self.name = name; self.bases = bases; self.keywords: list[keyword] = []
        self.body = body; self.decorator_list = [] if decorator_list is None else decorator_list
        self.type_params: list[object] = []
class TypeAlias(stmt):
    def __init__(self, name: expr, value: expr) -> None:
        self.name = name; self.value = value; self.type_params: list[object] = []

class MatchValue(pattern):
    def __init__(self, value: expr) -> None: self.value = value
class MatchSingleton(pattern):
    def __init__(self, value: object) -> None: self.value = value
class MatchAs(pattern):
    def __init__(self, pattern: pattern | None, name: str | None) -> None:
        self.pattern = pattern; self.name = name
class MatchStar(pattern):
    def __init__(self, name: str | None) -> None: self.name = name
class MatchOr(pattern):
    def __init__(self, patterns: list[pattern]) -> None: self.patterns = patterns
class MatchSequence(pattern):
    def __init__(self, patterns: list[pattern]) -> None: self.patterns = patterns
class MatchMapping(pattern):
    def __init__(self, keys: list[expr], patterns: list[pattern], rest: str | None = None) -> None:
        self.keys = keys; self.patterns = patterns; self.rest = rest
class MatchClass(pattern):
    def __init__(self, cls: expr, patterns: list[pattern], kwd_attrs: list[str], kwd_patterns: list[pattern]) -> None:
        self.cls = cls; self.patterns = patterns; self.kwd_attrs = kwd_attrs; self.kwd_patterns = kwd_patterns
class match_case(AST):
    def __init__(self, pattern: pattern, guard: expr | None, body: list[stmt]) -> None:
        self.pattern = pattern; self.guard = guard; self.body = body
class Match(stmt):
    def __init__(self, subject: expr, cases: list[match_case]) -> None:
        self.subject = subject; self.cases = cases


_BIN_OPS: dict[str, object] = {
    "+": Add(), "-": Sub(), "*": Mult(), "/": Div(), "//": FloorDiv(),
    "%": Mod(), "**": Pow(), "&": BitAnd(), "|": BitOr(), "^": BitXor(),
    "<<": LShift(), ">>": RShift(), "@": MatMult(),
}
_COMPARE: dict[str, object] = {
    "==": Eq(), "<": Lt(), "<=": LtE(), ">": Gt(), ">=": GtE(), "!=": NotEq(),
    "is": Is(), "is not": IsNot(), "in": In(), "not in": NotIn(),
}
_UNARY: dict[str, object] = {"-": USub(), "+": UAdd(), "not": Not(), "~": Invert()}


def _name_target(name: str) -> Name:
    return Name(name, Store())

def _convert_expr(node: object, lifted: dict[str, A.FuncDef]) -> expr:
    if isinstance(node, A.IntLit):
        if node.is_none: return Constant(None)
        if node.is_bool: return Constant(bool(node.value))
        return Constant(node.value)
    if isinstance(node, A.FloatLit): return Constant(node.value)
    if isinstance(node, A.StrLit): return Constant(node.value)
    if isinstance(node, A.Name): return Name(node.name)
    if isinstance(node, A.BinOp): return BinOp(_convert_expr(node.left, lifted), _BIN_OPS[node.op], _convert_expr(node.right, lifted))
    if isinstance(node, A.UnaryOp): return UnaryOp(_UNARY[node.op], _convert_expr(node.operand, lifted))
    if isinstance(node, A.BoolOp): return BoolOp(And() if node.op == "and" else Or(), [_convert_expr(node.left, lifted), _convert_expr(node.right, lifted)])
    if isinstance(node, A.Compare):
        operands = [_convert_expr(value, lifted) for value in node.operands]
        return Compare(operands[0], [_COMPARE[op] for op in node.ops], operands[1:])
    if isinstance(node, A.IfExp): return IfExp(_convert_expr(node.test, lifted), _convert_expr(node.body, lifted), _convert_expr(node.orelse, lifted))
    if isinstance(node, A.NamedExpr): return NamedExpr(_name_target(node.target), _convert_expr(node.value, lifted))
    if isinstance(node, A.Attr): return Attribute(_convert_expr(node.obj, lifted), node.name)
    if isinstance(node, A.Subscript): return Subscript(_convert_expr(node.obj, lifted), _convert_expr(node.index, lifted))
    if isinstance(node, A.Slice):
        return Slice(None if node.start is None else _convert_expr(node.start, lifted), None if node.stop is None else _convert_expr(node.stop, lifted), None if node.step is None else _convert_expr(node.step, lifted))
    if isinstance(node, A.Starred): return Starred(_convert_expr(node.value, lifted))
    if isinstance(node, A.ListLit): return List([_convert_expr(value, lifted) for value in node.elems])
    if isinstance(node, A.TupleLit): return Tuple([_convert_expr(value, lifted) for value in node.elems])
    if isinstance(node, A.SetLit): return Set([_convert_expr(value, lifted) for value in node.elems])
    if isinstance(node, A.DictLit):
        return Dict([None if key is None else _convert_expr(key, lifted) for key in node.keys], [_convert_expr(value, lifted) for value in node.values])
    if isinstance(node, A.Call):
        keys = [keyword(name, _convert_expr(value, lifted)) for name, value in (node.kwargs or [])]
        if node.dstar is not None: keys.append(keyword(None, _convert_expr(node.dstar, lifted)))
        return Call(Name(node.func), [_convert_expr(value, lifted) for value in node.args], keys)
    if isinstance(node, A.MethodCall):
        keys = [keyword(name, _convert_expr(value, lifted)) for name, value in (node.kwargs or [])]
        return Call(Attribute(_convert_expr(node.obj, lifted), node.method), [_convert_expr(value, lifted) for value in node.args], keys)
    if isinstance(node, A.Lambda):
        args = arguments([], [arg(name) for name in node.params], None, [], [], None, [])
        return Lambda(args, _convert_expr(node.body, lifted))
    if isinstance(node, A.FString):
        values: list[expr] = []
        for segment in node.segments:
            if isinstance(segment, A.StrLit): values.append(Constant(segment.value))
            else: values.append(FormattedValue(_convert_expr(segment, lifted)))
        return JoinedStr(values)
    if isinstance(node, A.Comprehension):
        generators = [comprehension(_name_target(node.var), _convert_expr(node.iter, lifted), [] if node.cond is None else [_convert_expr(node.cond, lifted)])]
        return ListComp(_convert_expr(node.elt, lifted), generators)
    if isinstance(node, A.DictComprehension):
        generators = [comprehension(_name_target(node.var), _convert_expr(node.iter, lifted), [] if node.cond is None else [_convert_expr(node.cond, lifted)])]
        return DictComp(_convert_expr(node.key, lifted), _convert_expr(node.value, lifted), generators)
    raise RuntimeError("unsupported native AST expression")


def _convert_arguments(node: A.FuncDef, lifted: dict[str, A.FuncDef]) -> arguments:
    all_args = [arg(name) for name in node.params]
    defaults: list[expr] = []
    first_default = len(node.defaults)
    index = 0
    while index < len(node.defaults):
        if node.defaults[index] is not None:
            first_default = index
            break
        index += 1
    if first_default < len(node.defaults):
        index = first_default
        while index < len(node.defaults):
            defaults.append(_convert_expr(node.defaults[index], lifted))
            index += 1
    return arguments([], all_args, None if node.vararg is None else arg(node.vararg), [], [], None if node.kwarg is None else arg(node.kwarg), defaults)


def _convert_func(node: A.FuncDef, lifted: dict[str, A.FuncDef]) -> FunctionDef:
    body: list[stmt] = []
    for item in node.body:
        converted = _convert_stmt(item, lifted)
        if converted is not None: body.append(converted)
    return FunctionDef(node.name, _convert_arguments(node, lifted), body)


def _target(value: object, lifted: dict[str, A.FuncDef]) -> expr:
    if isinstance(value, str): return _name_target(value)
    result = _convert_expr(value, lifted)
    result.ctx = Store()
    return result


def _convert_stmt(node: object, lifted: dict[str, A.FuncDef]) -> stmt | None:
    if isinstance(node, A.Assign): return Assign([_name_target(node.target)], _convert_expr(node.value, lifted))
    if isinstance(node, A.AttrAssign): return Assign([Attribute(_convert_expr(node.obj, lifted), node.name, Store())], _convert_expr(node.value, lifted))
    if isinstance(node, A.IndexAssign): return Assign([Subscript(_convert_expr(node.target.obj, lifted), _convert_expr(node.target.index, lifted), Store())], _convert_expr(node.value, lifted))
    if isinstance(node, A.MultiAssign): return Assign([_name_target(name) for name in node.targets], _convert_expr(node.value, lifted))
    if isinstance(node, A.TupleAssign): return Assign([Tuple([_target(value, lifted) for value in node.targets], Store())], Tuple([_convert_expr(value, lifted) for value in node.values]))
    if isinstance(node, A.AugAssign): return AugAssign(_name_target(node.target), _BIN_OPS[node.op], _convert_expr(node.value, lifted))
    if isinstance(node, A.Return): return Return(None if node.value is None else _convert_expr(node.value, lifted))
    if isinstance(node, A.ExprStmt): return Expr(_convert_expr(node.expr, lifted))
    if isinstance(node, A.Pass): return Pass()
    if isinstance(node, A.Break): return Break()
    if isinstance(node, A.Continue): return Continue()
    if isinstance(node, A.Global): return Global(list(node.names))
    if isinstance(node, A.Nonlocal): return Nonlocal(list(node.names))
    if isinstance(node, A.Raise): return Raise(None if node.value is None else _convert_expr(node.value, lifted))
    if isinstance(node, A.If): return If(_convert_expr(node.test, lifted), _convert_body(node.then, lifted), _convert_body(node.orelse, lifted))
    if isinstance(node, A.While): return While(_convert_expr(node.test, lifted), _convert_body(node.body, lifted), _convert_body(node.orelse, lifted))
    if isinstance(node, A.For):
        target = _name_target(node.var) if node.var else Tuple([_target(value, lifted) for value in node.targets], Store())
        iterator = _convert_expr(node.iter, lifted) if node.iter is not None else Call(Name("range"), [_convert_expr(value, lifted) for value in node.range_args], [])
        return For(target, iterator, _convert_body(node.body, lifted), _convert_body(node.orelse, lifted))
    if isinstance(node, A.ClosureBind): return _convert_func(lifted[node.func_name], lifted)
    if isinstance(node, A.Import): return Import([alias(node.module, node.alias)])
    if isinstance(node, A.FromImport):
        names = [alias(original, renamed) for original, renamed in zip(node.orig_names or node.names, node.names)]
        return ImportFrom(node.module, names, node.level)
    if isinstance(node, A.With): return With([withitem(_convert_expr(node.expr, lifted), None if node.name is None else _name_target(node.name))], _convert_body(node.body, lifted))
    if isinstance(node, A.Try):
        handlers: list[ExceptHandler] = []
        if node.handler or node.handler_types:
            htype: expr | None = None
            if node.handler_types:
                htype = Name(node.handler_types[0]) if len(node.handler_types) == 1 else Tuple([Name(name) for name in node.handler_types])
            handlers.append(ExceptHandler(htype, node.bind_name, _convert_body(node.handler, lifted)))
        for types, bind, body in node.extra_handlers or []:
            htype = None if not types else Name(types[0]) if len(types) == 1 else Tuple([Name(name) for name in types])
            handlers.append(ExceptHandler(htype, bind, _convert_body(body, lifted)))
        return Try(_convert_body(node.body, lifted), handlers, _convert_body(node.else_body, lifted), _convert_body(node.finally_body, lifted))
    if isinstance(node, A.FuncDef): return _convert_func(node, lifted)
    return None


def _convert_body(body: list[object], lifted: dict[str, A.FuncDef]) -> list[stmt]:
    result: list[stmt] = []
    for node in body:
        converted = _convert_stmt(node, lifted)
        if converted is not None: result.append(converted)
    return result


def _line(node: object) -> int:
    return node.pos.line if hasattr(node, "pos") else 0


def parse(source: str, filename: str = "<native>", mode: str = "exec") -> Module:
    parsed = Parser(Lexer(source).tokenize()).parse()
    lifted: dict[str, A.FuncDef] = {}
    top: list[object] = list(parsed.body)
    for function in parsed.funcs:
        lifted[function.name] = function
        if not function.is_lifted: top.append(function)
    for cls in parsed.classes: top.append(cls)
    top.sort(key=_line)
    result: list[stmt] = []
    for node in top:
        if isinstance(node, A.ClassDef):
            class_body: list[stmt] = []
            for variable in node.class_vars:
                converted = _convert_stmt(variable, lifted)
                if converted is not None: class_body.append(converted)
            for method in node.methods: class_body.append(_convert_func(method, lifted))
            bases = [] if node.parent is None else [Name(node.parent)]
            result.append(ClassDef(node.name, bases, class_body))
        else:
            converted = _convert_stmt(node, lifted)
            if converted is not None: result.append(converted)
    return Module(result)


def walk(node: object) -> list[AST]:
    result: list[AST] = []
    pending: list[object] = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, AST):
            result.append(current)
            for value in vars(current).values():
                if isinstance(value, AST): pending.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, AST): pending.append(item)
    return result


def unparse(node: object) -> str:
    if isinstance(node, Name): return node.id
    if isinstance(node, Constant): return str(node.value)
    if isinstance(node, Attribute): return unparse(node.value) + "." + node.attr
    return "<annotation>"
