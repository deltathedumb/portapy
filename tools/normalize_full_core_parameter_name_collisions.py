"""Rename native parameters that collide with flattened class symbols.

Asmpython compiles PortaPy's imported modules into one symbol namespace. A
parameter named like any class can therefore resolve to the class token instead
of the runtime argument. Explicit functions are renamed in place. Dataclasses
whose generated initializer would collide receive an equivalent explicit
initializer with collision-safe parameter names. Matching keyword call sites
are rewritten across the source tree.
"""
from __future__ import annotations

import ast
import copy
from pathlib import Path


ROOT = Path("src/portapy")
_PREFIX = "__portapy_param_"


def _class_names(trees: dict[Path, ast.Module]) -> set[str]:
    return {
        node.name
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }


def _is_dataclass(node: ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == "dataclass":
            if isinstance(decorator, ast.Call):
                for keyword in decorator.keywords:
                    if (
                        keyword.arg == "init"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is False
                    ):
                        return False
            return True
        if isinstance(target, ast.Attribute) and target.attr == "dataclass":
            return True
    return False


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    result = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        result.append(node.args.vararg)
    if node.args.kwarg is not None:
        result.append(node.args.kwarg)
    return result


class _BodyRenamer(ast.NodeTransformer):
    def __init__(self, renames: dict[str, str]) -> None:
        self.renames = renames

    def visit_Name(self, node: ast.Name) -> ast.AST:
        replacement = self.renames.get(node.id)
        if replacement is not None:
            node.id = replacement
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return node


def _rename_explicit_parameters(
    tree: ast.Module,
    class_names: set[str],
    call_renames: dict[str, dict[str, str]],
) -> int:
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        renames: dict[str, str] = {}
        occupied = {argument.arg for argument in _parameters(node)} | class_names
        for argument in _parameters(node):
            if argument.arg in {"self", "cls"} or argument.arg not in class_names:
                continue
            old = argument.arg
            candidate = f"{_PREFIX}{old}"
            suffix = 2
            while candidate in occupied:
                candidate = f"{_PREFIX}{old}_{suffix}"
                suffix += 1
            occupied.add(candidate)
            argument.arg = candidate
            renames[old] = candidate
            count += 1
        if not renames:
            continue
        body_renamer = _BodyRenamer(renames)
        node.body = [body_renamer.visit(statement) for statement in node.body]
        existing = call_renames.setdefault(node.name, {})
        for old, new in renames.items():
            previous = existing.get(old)
            if previous is not None and previous != new:
                raise RuntimeError(
                    f"inconsistent parameter rename for {node.name}.{old}: "
                    f"{previous!r} vs {new!r}"
                )
            existing[old] = new
    return count


def _field_nodes(node: ast.ClassDef) -> list[ast.AnnAssign]:
    return [
        statement
        for statement in node.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.simple == 1
    ]


def _safe_factory_default(factory: ast.expr, label: str) -> ast.expr:
    if isinstance(factory, ast.Lambda):
        if (
            factory.args.posonlyargs
            or factory.args.args
            or factory.args.kwonlyargs
            or factory.args.vararg is not None
            or factory.args.kwarg is not None
        ):
            raise RuntimeError(f"{label}: default factory lambda takes arguments")
        value = factory.body
    else:
        raise RuntimeError(f"{label}: unsupported non-lambda default factory")
    if not isinstance(value, (ast.Name, ast.Attribute, ast.Constant)):
        raise RuntimeError(
            f"{label}: mutable or computed default factory cannot become a "
            "function default safely"
        )
    return copy.deepcopy(value)


def _field_default(field: ast.AnnAssign, label: str) -> ast.expr | None:
    value = field.value
    if value is None:
        return None
    if not (
        isinstance(value, ast.Call)
        and (
            (isinstance(value.func, ast.Name) and value.func.id == "field")
            or (isinstance(value.func, ast.Attribute) and value.func.attr == "field")
        )
    ):
        return copy.deepcopy(value)
    init_enabled = True
    default: ast.expr | None = None
    for keyword in value.keywords:
        if (
            keyword.arg == "init"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is False
        ):
            init_enabled = False
        elif keyword.arg == "default":
            default = copy.deepcopy(keyword.value)
        elif keyword.arg == "default_factory":
            default = _safe_factory_default(keyword.value, label)
    if not init_enabled:
        raise RuntimeError(f"{label}: colliding field uses init=False")
    if default is None:
        raise RuntimeError(f"{label}: field() has no supported default")
    return default


def _install_dataclass_initializers(
    tree: ast.Module,
    class_names: set[str],
    call_renames: dict[str, dict[str, str]],
) -> tuple[int, int]:
    classes_changed = 0
    parameters_changed = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _is_dataclass(node):
            continue
        if any(
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == "__init__"
            for statement in node.body
        ):
            continue
        fields = _field_nodes(node)
        collisions = {
            field.target.id
            for field in fields
            if field.target.id in class_names
        }
        if not collisions:
            continue

        arguments = [ast.arg(arg="self")]
        defaults: list[ast.expr] = []
        body: list[ast.stmt] = []
        saw_default = False
        renames: dict[str, str] = {}
        for field in fields:
            field_name = field.target.id
            parameter_name = (
                f"{_PREFIX}{field_name}"
                if field_name in collisions
                else field_name
            )
            arguments.append(
                ast.arg(
                    arg=parameter_name,
                    annotation=copy.deepcopy(field.annotation),
                )
            )
            default = _field_default(
                field,
                f"{node.name}.{field_name}",
            )
            if default is None:
                if saw_default:
                    raise RuntimeError(
                        f"{node.name}: required field follows a default field"
                    )
            else:
                saw_default = True
                defaults.append(default)
            body.append(
                ast.Assign(
                    targets=[
                        ast.Attribute(
                            value=ast.Name(id="self", ctx=ast.Load()),
                            attr=field_name,
                            ctx=ast.Store(),
                        )
                    ],
                    value=ast.Name(id=parameter_name, ctx=ast.Load()),
                )
            )
            if field_name in collisions:
                renames[field_name] = parameter_name
                parameters_changed += 1

        initializer = ast.FunctionDef(
            name="__init__",
            args=ast.arguments(
                posonlyargs=[],
                args=arguments,
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=defaults,
            ),
            body=body or [ast.Pass()],
            decorator_list=[],
            returns=ast.Constant(value=None),
            type_comment=None,
        )
        node.body.append(initializer)
        classes_changed += 1
        existing = call_renames.setdefault(node.name, {})
        for old, new in renames.items():
            previous = existing.get(old)
            if previous is not None and previous != new:
                raise RuntimeError(
                    f"inconsistent constructor rename for {node.name}.{old}"
                )
            existing[old] = new
    return classes_changed, parameters_changed


class _CallKeywordRenamer(ast.NodeTransformer):
    def __init__(self, renames: dict[str, dict[str, str]]) -> None:
        self.renames = renames
        self.count = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            return node
        mapping = self.renames.get(name)
        if not mapping:
            return node
        for keyword in node.keywords:
            replacement = mapping.get(keyword.arg or "")
            if replacement is not None:
                keyword.arg = replacement
                self.count += 1
        return node


def _remaining_parameter_collisions(
    trees: dict[Path, ast.Module],
    class_names: set[str],
) -> list[str]:
    remaining: list[str] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                collisions = sorted(
                    argument.arg
                    for argument in _parameters(node)
                    if argument.arg not in {"self", "cls"}
                    and argument.arg in class_names
                )
                if collisions:
                    remaining.append(
                        f"{path}:{node.lineno}:{node.name}:"
                        + ",".join(collisions)
                    )
            elif isinstance(node, ast.ClassDef) and _is_dataclass(node):
                has_init = any(
                    isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and statement.name == "__init__"
                    for statement in node.body
                )
                collisions = sorted(
                    field.target.id
                    for field in _field_nodes(node)
                    if field.target.id in class_names
                )
                if collisions and not has_init:
                    remaining.append(
                        f"{path}:{node.lineno}:{node.name}:generated:"
                        + ",".join(collisions)
                    )
    return remaining


def normalize_tree(root: Path) -> tuple[int, int, int, int]:
    paths = sorted(root.rglob("*.py"))
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    class_names = _class_names(trees)
    call_renames: dict[str, dict[str, str]] = {}
    explicit_parameters = 0
    dataclass_parameters = 0
    dataclass_classes = 0

    for tree in trees.values():
        explicit_parameters += _rename_explicit_parameters(
            tree,
            class_names,
            call_renames,
        )
        classes, parameters = _install_dataclass_initializers(
            tree,
            class_names,
            call_renames,
        )
        dataclass_classes += classes
        dataclass_parameters += parameters

    keyword_calls = 0
    for tree in trees.values():
        renamer = _CallKeywordRenamer(call_renames)
        renamer.visit(tree)
        keyword_calls += renamer.count

    changed_files = 0
    for path, tree in trees.items():
        rendered = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
        if rendered != path.read_text(encoding="utf-8"):
            path.write_text(rendered, encoding="utf-8")
            changed_files += 1

    verified = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in paths
    }
    remaining = _remaining_parameter_collisions(verified, class_names)
    if remaining:
        raise RuntimeError(
            "native parameter/class collisions remain: " + "; ".join(remaining)
        )
    return (
        explicit_parameters,
        dataclass_parameters,
        dataclass_classes,
        keyword_calls,
    )


def main() -> int:
    result = normalize_tree(ROOT)
    if sum(result[:2]) < 1:
        raise RuntimeError("native parameter/class collision pass changed no parameters")
    print("RENAMED NATIVE PARAMETER CLASS COLLISIONS", *result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
