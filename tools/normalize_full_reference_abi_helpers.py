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

_STATUS_CONSTANTS = {
    "PORTAPY_OK": "OK",
    "PORTAPY_INVALID_ARGUMENT": "INVALID_ARGUMENT",
    "PORTAPY_COMPILE_ERROR": "COMPILE_ERROR",
    "PORTAPY_RUNTIME_ERROR": "RUNTIME_ERROR",
    "PORTAPY_TYPE_ERROR": "TYPE_ERROR",
    "PORTAPY_NOT_FOUND": "NOT_FOUND",
    "PORTAPY_CLOSED": "CLOSED",
    "PORTAPY_INVALID_HANDLE": "INVALID_HANDLE",
    "PORTAPY_INTERRUPTED": "INTERRUPTED",
}

_NATIVE_ENUM_HELPERS_SOURCE = '''
def _native_status_code(status: object) -> int:
    if status is Status.OK:
        return PORTAPY_OK
    if status is Status.INVALID_ARGUMENT:
        return PORTAPY_INVALID_ARGUMENT
    if status is Status.COMPILE_ERROR:
        return PORTAPY_COMPILE_ERROR
    if status is Status.RUNTIME_ERROR:
        return PORTAPY_RUNTIME_ERROR
    if status is Status.TYPE_ERROR:
        return PORTAPY_TYPE_ERROR
    if status is Status.NOT_FOUND:
        return PORTAPY_NOT_FOUND
    if status is Status.CLOSED:
        return PORTAPY_CLOSED
    if status is Status.INVALID_HANDLE:
        return PORTAPY_INVALID_HANDLE
    if status is Status.INTERRUPTED:
        return PORTAPY_INTERRUPTED
    return PORTAPY_RUNTIME_ERROR


def _native_value_kind_code(kind: object) -> int:
    if kind is ValueKind.NONE:
        return PORTAPY_VALUE_NONE
    if kind is ValueKind.BOOL:
        return PORTAPY_VALUE_BOOL
    if kind is ValueKind.INT:
        return PORTAPY_VALUE_INT
    if kind is ValueKind.FLOAT:
        return PORTAPY_VALUE_FLOAT
    if kind is ValueKind.STRING:
        return PORTAPY_VALUE_STRING
    if kind is ValueKind.BYTES:
        return PORTAPY_VALUE_BYTES
    if kind is ValueKind.CALLABLE:
        return PORTAPY_VALUE_CALLABLE
    if kind is ValueKind.TUPLE:
        return PORTAPY_VALUE_TUPLE
    if kind is ValueKind.DICT:
        return PORTAPY_VALUE_DICT
    if kind is ValueKind.LIST:
        return PORTAPY_VALUE_LIST
    return PORTAPY_VALUE_OBJECT


def _set_status_code(value: int) -> int:
    _last_status[0] = value
    return value
'''

_SET_STATUS_SOURCE = '''
value = _native_status_code(status)
_last_status[0] = value
return value
'''

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
_set_status(Status.OK)
return len(_runtimes) - 1
'''

_VALUE_GET_KIND_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return PORTAPY_VALUE_OBJECT
status, kind = instance.value_kind(value)
_set_status(status)
return _native_value_kind_code(kind)
'''

_VALUE_AS_BOOL_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
status, kind = instance.value_kind(value)
if status is not Status.OK:
    _set_status(status)
    return 0
if kind is not ValueKind.BOOL:
    _set_status(Status.TYPE_ERROR)
    return 0
status, target = instance.unbox(value)
if status is not Status.OK:
    _set_status(status)
    return 0
_set_status(Status.OK)
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


def _native_enum_helper(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        if node.id == "kind":
            return "_native_value_kind_code"
        if node.id == "status":
            return "_native_status_code"
        return None
    if not isinstance(node, ast.Attribute):
        return None
    if node.attr == "status":
        return "_native_status_code"
    if isinstance(node.value, ast.Name):
        if node.value.id == "Status":
            return "_native_status_code"
        if node.value.id == "ValueKind":
            return "_native_value_kind_code"
    return None


def _contains_raw_status(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Name) and item.id in _STATUS_CONSTANTS
        for item in ast.walk(node)
    )


def _contains_native_enum_value_access(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Attribute)
        and item.attr == "value"
        and _native_enum_helper(item.value) is not None
        for item in ast.walk(node)
    )


class _RawDispatchStatusRewriter(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "_set_status"
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "status"
        ):
            node.func.id = "_set_status_code"
        return node


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
        if node.name == "_set_status":
            node.body = ast.parse(_SET_STATUS_SOURCE).body
        elif node.name == "_portapy_runtime_create_impl":
            node.body = ast.parse(_RUNTIME_CREATE_SOURCE).body
        elif node.name == "_portapy_value_get_kind_impl":
            node.body = ast.parse(_VALUE_GET_KIND_SOURCE).body
        elif node.name == "_portapy_value_as_bool_impl":
            node.body = ast.parse(_VALUE_AS_BOOL_SOURCE).body
        elif node.name == "_portapy_host_dispatch_complete_impl":
            node = _RawDispatchStatusRewriter().visit(node)

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

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "_set_status"
            and len(node.args) == 1
            and not node.keywords
            and _contains_raw_status(node.args[0])
        ):
            node.func.id = "_set_status_code"
            return node
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "int"
            and len(node.args) == 1
            and not node.keywords
        ):
            helper = _native_enum_helper(node.args[0])
            if helper is not None:
                return ast.copy_location(
                    ast.Call(
                        func=ast.Name(id=helper, ctx=ast.Load()),
                        args=node.args,
                        keywords=[],
                    ),
                    node,
                )
        return node

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
    module.body.extend(ast.parse(_NATIVE_ENUM_HELPERS_SOURCE).body)
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
    enum_int_calls = [
        node
        for node in ast.walk(verified)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "int"
        and len(node.args) == 1
        and _native_enum_helper(node.args[0]) is not None
    ]
    raw_status_calls = [
        node
        for node in ast.walk(verified)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_set_status"
        and len(node.args) == 1
        and _contains_raw_status(node.args[0])
    ]
    enum_value_accesses = [
        node
        for node in ast.walk(verified)
        if _contains_native_enum_value_access(node)
    ]
    runtime_create_text = _function_text(verified, "_portapy_runtime_create_impl")
    set_status_text = _function_text(verified, "_set_status")
    status_code_text = _function_text(verified, "_native_status_code")
    kind_code_text = _function_text(verified, "_native_value_kind_code")
    value_get_kind_text = _function_text(verified, "_portapy_value_get_kind_impl")
    value_as_bool_text = _function_text(verified, "_portapy_value_as_bool_impl")
    host_dispatch_text = _function_text(verified, "_portapy_host_dispatch_complete_impl")
    loader_ready = (
        "_PortaPyImportLoader" in classes
        and "__pyinbin_import__" in runtime_create_text
    )
    builtins_ready = "_seed_builtins" in runtime_create_text
    enum_values_ready = (
        not enum_int_calls
        and not enum_value_accesses
        and "_native_status_code(status)" in set_status_text
        and "_native_value_kind_code(kind)" in value_get_kind_text
        and "PORTAPY_OK" in status_code_text
        and "PORTAPY_VALUE_NONE" in kind_code_text
    )
    status_paths_ready = (
        not raw_status_calls
        and "_set_status_code(status)" in host_dispatch_text
        and "_set_status(status)" not in host_dispatch_text
    )
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
        or not enum_values_ready
        or not status_paths_ready
        or not tagged_kind_ready
        or not tagged_bool_ready
        or not tagged_stores_ready
    ):
        raise RuntimeError(
            "full Runtime ABI helper normalization failed; "
            f"missing={missing}, stale={stale}, "
            f"unsafe_utf8_spans={len(unsafe_spans)}, "
            f"enum_int_calls={len(enum_int_calls)}, "
            f"enum_value_accesses={len(enum_value_accesses)}, "
            f"raw_status_calls={len(raw_status_calls)}, "
            f"loader_ready={loader_ready}, builtins_ready={builtins_ready}, "
            f"enum_values_ready={enum_values_ready}, "
            f"status_paths_ready={status_paths_ready}, "
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
        "ENUM_CODES",
        "STATUS_CODES",
        "TAGGED_VALUES",
        "TAGGED_STORES",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
