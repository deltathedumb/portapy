"""Normalize full Runtime helpers to the established adapter contract.

The verified source payload originally named several Python-authored functions
with the ``_portapy_cabi_`` prefix. PortaPy's linker layer reserves those names
for register-preserving assembly adapters. This pass renames the underlying
implementations, removes redundant forwarding wrappers, installs explicit
builtins and host-owned module resolution for every runtime, and preserves
UTF-8 C span semantics at the Python-authored ABI boundary.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_DROP = {
    "_portapy_cabi_last_status_impl",
    "_portapy_cabi_delete_global_span_impl",
    "_portapy_cabi_global_count_impl",
    "_portapy_cabi_global_name_size_impl",
    "_portapy_cabi_global_name_byte_impl",
}

_RENAME = {
    "_portapy_cabi_value_from_host_callable_impl": "_portapy_value_from_host_callable_impl",
    "_portapy_cabi_value_get_host_callable_id_impl": "_portapy_value_get_host_callable_id_impl",
    "_portapy_cabi_host_pending_arg_count_impl": "_portapy_host_pending_arg_count_impl",
    "_portapy_cabi_host_pending_arg_impl": "_portapy_host_pending_arg_impl",
    "_portapy_cabi_host_dispatch_complete_impl": "_portapy_host_dispatch_complete_impl",
    "_portapy_cabi_tuple_begin_impl": "_portapy_tuple_begin_impl",
    "_portapy_cabi_tuple_set_item_impl": "_portapy_tuple_set_item_impl",
    "_portapy_cabi_tuple_finish_impl": "_portapy_tuple_finish_impl",
    "_portapy_cabi_tuple_get_size_impl": "_portapy_tuple_get_size_impl",
    "_portapy_cabi_tuple_get_item_impl": "_portapy_tuple_get_item_impl",
    "_portapy_cabi_tuple_release_impl": "_portapy_tuple_release_impl",
    "_portapy_cabi_dict_begin_impl": "_portapy_dict_begin_impl",
    "_portapy_cabi_dict_set_span_impl": "_portapy_dict_set_span_impl",
    "_portapy_cabi_dict_get_size_impl": "_portapy_dict_get_size_impl",
    "_portapy_cabi_dict_key_size_impl": "_portapy_dict_key_size_impl",
    "_portapy_cabi_dict_key_byte_impl": "_portapy_dict_key_byte_impl",
    "_portapy_cabi_dict_get_item_span_impl": "_portapy_dict_get_item_span_impl",
    "_portapy_cabi_list_begin_impl": "_portapy_list_begin_impl",
    "_portapy_cabi_list_initialize_item_impl": "_portapy_list_initialize_item_impl",
    "_portapy_cabi_list_finish_impl": "_portapy_list_finish_impl",
    "_portapy_cabi_list_get_size_impl": "_portapy_list_get_size_impl",
    "_portapy_cabi_list_get_item_impl": "_portapy_list_get_item_impl",
    "_portapy_cabi_list_set_item_impl": "_portapy_list_set_item_impl",
    "_portapy_cabi_list_append_impl": "_portapy_list_append_impl",
}

_STORE_KIND_BY_FUNCTION = {
    "_portapy_value_from_data_begin_impl": "kind",
    "_portapy_value_from_host_object_impl": "ValueKind.OBJECT",
    "_portapy_value_from_host_callable_impl": "ValueKind.CALLABLE",
    "_portapy_tuple_begin_impl": "ValueKind.TUPLE",
    "_portapy_dict_begin_impl": "ValueKind.DICT",
    "_portapy_list_begin_impl": "ValueKind.LIST",
}

_IMPORT_LOADER_SOURCE = '''
class _PortaPyImportLoader:
    def __init__(self, instance: Runtime) -> None:
        self.instance = instance

    def __call__(self, name: str) -> object:
        parts = name.split(".")
        if len(parts) == 0 or parts[0] == "":
            raise ImportError(name)
        status, value = self.instance.read_global(parts[0])
        if status is not Status.OK:
            raise ImportError(name)
        index = 1
        while index < len(parts):
            try:
                value = getattr(value, parts[index])
            except AttributeError:
                raise ImportError(name)
            index += 1
        return value
'''

_RUNTIME_CREATE_SOURCE = '''
instance = Runtime()
instance._vm._seed_builtins(instance._globals)
instance.set_global("__pyinbin_import__", _PortaPyImportLoader(instance))
_runtimes.append(instance)
_set_status(PORTAPY_OK)
return len(_runtimes) - 1
'''

_VALUE_GET_KIND_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(PORTAPY_INVALID_HANDLE)
    return PORTAPY_VALUE_OBJECT
status, kind = instance.value_kind(value)
_set_status(status)
return int(kind)
'''

_VALUE_AS_BOOL_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(PORTAPY_INVALID_HANDLE)
    return 0
status, kind = instance.value_kind(value)
if status is not Status.OK:
    _set_status(status)
    return 0
if kind is not ValueKind.BOOL:
    _set_status(PORTAPY_TYPE_ERROR)
    return 0
status, target = instance.unbox(value)
if status is not Status.OK:
    _set_status(status)
    return 0
_set_status(PORTAPY_OK)
return 1 if target else 0
'''


def _is_utf8_source_upper_bound(node: ast.AST) -> bool:
    """Return True for ``source_size > len(source)``.

    C passes UTF-8 byte lengths, while the compiled Python function receives a
    decoded string. For non-ASCII source the byte count can legitimately exceed
    ``len(source)``. Slicing with that larger bound already returns the complete
    string, so only negative sizes are invalid here.
    """
    return (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "source_size"
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Gt)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Call)
        and isinstance(node.comparators[0].func, ast.Name)
        and node.comparators[0].func.id == "len"
        and len(node.comparators[0].args) == 1
        and isinstance(node.comparators[0].args[0], ast.Name)
        and node.comparators[0].args[0].id == "source"
    )


class _StoreTagger(ast.NodeTransformer):
    def __init__(self, kind_source: str) -> None:
        self.kind = ast.parse(kind_source, mode="eval").body
        self.count = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "_store"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "instance"
            and len(node.args) == 1
            and not node.keywords
        ):
            node.args.append(ast.copy_location(self.kind, node.args[0]))
            self.count += 1
        return node


class _Rewrite(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | None:
        if node.name in _DROP:
            return None
        node.name = _RENAME.get(node.name, node.name)
        self.generic_visit(node)
        if node.name == "_portapy_runtime_create_impl":
            node.body = ast.parse(_RUNTIME_CREATE_SOURCE).body
        elif node.name == "_portapy_value_get_kind_impl":
            node.body = ast.parse(_VALUE_GET_KIND_SOURCE).body
        elif node.name == "_portapy_value_as_bool_impl":
            node.body = ast.parse(_VALUE_AS_BOOL_SOURCE).body

        kind_source = _STORE_KIND_BY_FUNCTION.get(node.name)
        if kind_source is not None:
            tagger = _StoreTagger(kind_source)
            node = tagger.visit(node)
            if tagger.count != 1:
                raise RuntimeError(
                    f"native store tagging for {node.name}: expected one call, "
                    f"found {tagger.count}"
                )
        return node

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> ast.AST | None:
        if node.name in _DROP:
            return None
        node.name = _RENAME.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        renamed = _RENAME.get(node.id)
        if renamed is None:
            return node
        return ast.copy_location(ast.Name(id=renamed, ctx=node.ctx), node)

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.op, ast.Or):
            return node
        values = [value for value in node.values if not _is_utf8_source_upper_bound(value)]
        if len(values) == len(node.values):
            return node
        if len(values) == 1:
            return ast.copy_location(values[0], node)
        return ast.copy_location(ast.BoolOp(op=node.op, values=values), node)


def _function_text(module: ast.Module, name: str) -> str:
    function = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ),
        None,
    )
    return ast.unparse(function) if function is not None else ""


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    module = _Rewrite().visit(module)
    if any(
        isinstance(node, ast.ClassDef) and node.name == "_PortaPyImportLoader"
        for node in module.body
    ):
        raise RuntimeError("full Runtime already contains the PortaPy import loader")
    module.body.extend(ast.parse(_IMPORT_LOADER_SOURCE).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    definitions = {
        node.name
        for node in verified.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name
        for node in verified.body
        if isinstance(node, ast.ClassDef)
    }
    missing = sorted(set(_RENAME.values()) - definitions)
    stale = sorted((set(_RENAME) | _DROP) & definitions)
    unsafe_spans = [
        node
        for node in ast.walk(verified)
        if _is_utf8_source_upper_bound(node)
    ]
    runtime_create_text = _function_text(verified, "_portapy_runtime_create_impl")
    value_get_kind_text = _function_text(verified, "_portapy_value_get_kind_impl")
    value_as_bool_text = _function_text(verified, "_portapy_value_as_bool_impl")
    loader_ready = (
        "_PortaPyImportLoader" in classes
        and "__pyinbin_import__" in runtime_create_text
    )
    builtins_ready = "_seed_builtins" in runtime_create_text
    tagged_kind_ready = (
        "instance.value_kind(value)" in value_get_kind_text
        and "_value_kind(" not in value_get_kind_text
    )
    tagged_bool_ready = (
        "instance.value_kind(value)" in value_as_bool_text
        and "type(target)" not in value_as_bool_text
    )
    tagged_stores_ready = all(
        _function_text(verified, name).count("instance._store(") == 1
        and _function_text(verified, name).count(", ValueKind.") == 1
        for name in _STORE_KIND_BY_FUNCTION
        if name != "_portapy_value_from_data_begin_impl"
    ) and "instance._store(_DataBuilder(kind, size), kind)" in _function_text(
        verified, "_portapy_value_from_data_begin_impl"
    )
    if (
        missing
        or stale
        or unsafe_spans
        or not loader_ready
        or not builtins_ready
        or not tagged_kind_ready
        or not tagged_bool_ready
        or not tagged_stores_ready
    ):
        raise RuntimeError(
            "full Runtime ABI helper normalization failed; "
            f"missing={missing}, stale={stale}, "
            f"unsafe_utf8_spans={len(unsafe_spans)}, "
            f"loader_ready={loader_ready}, builtins_ready={builtins_ready}, "
            f"tagged_kind_ready={tagged_kind_ready}, "
            f"tagged_bool_ready={tagged_bool_ready}, "
            f"tagged_stores_ready={tagged_stores_ready}"
        )
    print(
        "NORMALIZED FULL RUNTIME ABI HELPERS",
        len(_RENAME),
        len(_DROP),
        "BUILTINS",
        "IMPORT_LOADER",
        "TAGGED_VALUES",
        "TAGGED_STORES",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
