"""Normalize full Runtime helpers to the established adapter contract.

The verified source payload originally named several Python-authored functions
with the ``_portapy_cabi_`` prefix.  PortaPy's linker layer reserves those names
for register-preserving assembly adapters.  This pass renames the underlying
implementations and removes redundant forwarding wrappers before compilation.
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


class _Rewrite(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | None:
        if node.name in _DROP:
            return None
        node.name = _RENAME.get(node.name, node.name)
        self.generic_visit(node)
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


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    module = _Rewrite().visit(module)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    definitions = {
        node.name
        for node in verified.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(_RENAME.values()) - definitions)
    stale = sorted((set(_RENAME) | _DROP) & definitions)
    if missing or stale:
        raise RuntimeError(
            f"full Runtime ABI helper normalization failed; missing={missing}, stale={stale}"
        )
    print("NORMALIZED FULL RUNTIME ABI HELPERS", len(_RENAME), len(_DROP))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
