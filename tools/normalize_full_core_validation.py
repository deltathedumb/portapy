"""Apply the complete native full-core normalization pipeline."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
import traceback
from typing import Callable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))


from tools.combine_full_core_native_parser import main as combine_native_parser
from tools.materialize_full_reference_entry import main as materialize_reference_entry
from tools.normalize_full_core_boolops import main as normalize_boolops
from tools.normalize_full_core_builtin_parameter_collisions import main as normalize_builtin_parameter_collisions
from tools.normalize_full_core_builtins import main as normalize_builtins
from tools.normalize_full_core_calls_closures import main as normalize_calls_closures
from tools.normalize_full_core_closures import main as normalize_closures
from tools.normalize_full_core_collections import main as normalize_collections
from tools.normalize_full_core_expr_stmt_initializer import main as normalize_expr_stmt_initializer
from tools.normalize_full_core_extended_semantics_compat import main as normalize_extended_semantics
from tools.normalize_full_core_function_binding import main as normalize_function_binding
from tools.normalize_full_core_function_parameter_names import main as normalize_function_parameter_names
from tools.normalize_full_core_function_specs import main as normalize_function_specs
from tools.normalize_full_core_keyword_calls import main as normalize_keyword_calls
from tools.normalize_full_core_lambdas import main as normalize_lambdas
from tools.normalize_full_core_local_name_collisions import main as normalize_local_name_collisions
from tools.normalize_full_core_make_function import main as normalize_make_function
from tools.normalize_full_core_name_index import main as normalize_name_index
from tools.normalize_full_core_native_argument_defaults import main as normalize_native_argument_defaults
from tools.normalize_full_core_native_keyword_transport import main as normalize_native_keyword_transport
from tools.normalize_full_core_native_node_fields import main as normalize_native_node_fields
from tools.normalize_full_core_native_parser import main as normalize_native_parser
from tools.normalize_full_core_native_parser_expressions import main as normalize_native_parser_expressions
from tools.normalize_full_core_native_parser_target_dispatch import main as normalize_native_parser_target_dispatch
from tools.normalize_full_core_native_semantics import main as normalize_native_semantics
from tools.normalize_full_core_native_statement_bodies import main as normalize_native_statement_bodies
from tools.normalize_full_core_opcode_maps import main as normalize_opcode_maps
from tools.normalize_full_core_parameter_name_collisions import main as normalize_parameter_name_collisions
from tools.normalize_full_core_parser_errors import main as normalize_parser_errors
from tools.normalize_full_core_pattern_constructor_collisions import main as normalize_pattern_constructor_collisions
from tools.normalize_full_core_pattern_slices import main as normalize_pattern_slices
from tools.normalize_full_core_pop_top import main as normalize_pop_top
from tools.normalize_full_core_probe import main as normalize_probe
from tools.normalize_full_core_runtime_dispatch import main as normalize_runtime_dispatch
from tools.normalize_full_core_runtime_execution import main as normalize_runtime_execution
from tools.normalize_full_core_runtime_specs import main as normalize_runtime_specs
from tools.normalize_full_core_string_addition import main as normalize_string_addition
from tools.normalize_full_core_string_comparisons import main as normalize_truthiness
from tools.normalize_full_core_tracebacks import main as normalize_tracebacks
from tools.normalize_full_reference_abi_helpers import main as normalize_reference_abi_helpers
from tools.normalize_full_reference_bytes_literals import main as normalize_reference_bytes_literals
from tools.normalize_full_reference_data_access import main as normalize_reference_data_access
from tools.normalize_full_reference_data_builders import main as normalize_reference_data_builders
from tools.normalize_full_reference_error_locations import main as normalize_reference_error_locations
from tools.normalize_full_reference_error_text import main as normalize_reference_error_text
from tools.normalize_full_reference_errors import main as normalize_reference_errors
from tools.normalize_full_reference_expression_kinds import main as normalize_reference_expression_kinds
from tools.normalize_full_reference_float_bits import main as normalize_reference_float_bits
from tools.normalize_full_reference_function_return_kinds import main as normalize_reference_function_return_kinds
from tools.normalize_full_reference_handle_kind_access import main as normalize_reference_handle_kind_access
from tools.normalize_full_reference_nested_kinds import main as normalize_reference_nested_kinds
from tools.normalize_full_reference_runtime import main as normalize_reference_runtime
from tools.normalize_full_reference_safe_host_ids import main as normalize_reference_safe_host_ids
from tools.normalize_full_reference_source_preprocess import main as normalize_reference_source_preprocess
from tools.normalize_full_reference_type_errors import main as normalize_reference_type_errors
from tools.normalize_full_reference_value_kinds import main as normalize_reference_value_kinds


BYTECODE_PATH = Path("src/portapy/core/bytecode.py")
DIAGNOSTIC_PATH = Path("dist/full-core-normalization-error.txt")
NORMALIZATION_LOG_PATH = Path("dist/full-core-normalization.log")


def _normalize_nested_code_introspection() -> None:
    source = BYTECODE_PATH.read_text(encoding="utf-8")
    old = '''def _unwrap_nested_code(item: object) -> object:
    if isinstance(item, tuple) and len(item) in (2, 3) and isinstance(item[0], CodeObject):
        return item[0]
    if isinstance(item, tuple) and len(item) in (3, 4) and isinstance(item[1], CodeObject):
        return item[1]
    return item
'''
    new = '''def _unwrap_nested_code(item: object) -> object:
    return item
'''
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one nested-code introspection helper, found {count}"
        )
    BYTECODE_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("DISABLED HOST-ONLY NESTED CODE INTROSPECTION", count, flush=True)


def _normalize_opcode_validation() -> None:
    source = BYTECODE_PATH.read_text(encoding="utf-8")
    old = "            if type(instr.op) is not int or instr.op not in _VALID_OPS:"
    new = "            if instr.op not in _VALID_OPS:"
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one opcode host-type check, found {count}")
    BYTECODE_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("REMOVED HOST OPCODE TYPE IDENTITY", count, flush=True)


def _append_step_log(name: str, output: str) -> None:
    NORMALIZATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NORMALIZATION_LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(f"=== {name} ===\n")
        if output:
            stream.write(output)
            if not output.endswith("\n"):
                stream.write("\n")
        stream.write("\n")


def _run_step(name: str, callback: Callable[[], object]) -> None:
    print(f"FULL-CORE NORMALIZE START: {name}", flush=True)
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            result = callback()
        if result not in (None, 0):
            raise RuntimeError(f"normalizer returned non-zero result {result!r}")
    except BaseException:
        output = captured.getvalue()
        _append_step_log(name, output)
        diagnostic = f"failed step: {name}\n"
        if output:
            diagnostic += f"\nstep output:\n{output.rstrip()}\n"
        diagnostic += f"\n{traceback.format_exc()}"
        DIAGNOSTIC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DIAGNOSTIC_PATH.write_text(diagnostic, encoding="utf-8")
        print(diagnostic, flush=True)
        raise
    output = captured.getvalue()
    _append_step_log(name, output)
    print(f"FULL-CORE NORMALIZE OK: {name}", flush=True)


def main() -> int:
    steps: tuple[tuple[str, Callable[[], object]], ...] = (
        # This pass relies on pristine VM source anchors. Keep it before every
        # normalizer that rewrites or unparses src/portapy/core/vm.py.
        ("native_keyword_transport", normalize_native_keyword_transport),
        ("probe", normalize_probe),
        ("lambdas", normalize_lambdas),
        ("function_specs", normalize_function_specs),
        ("function_binding", normalize_function_binding),
        ("native_semantics", normalize_native_semantics),
        ("function_parameter_names", normalize_function_parameter_names),
        ("opcode_maps", normalize_opcode_maps),
        ("name_index", normalize_name_index),
        ("reference_runtime", normalize_reference_runtime),
        ("materialize_reference_entry", materialize_reference_entry),
        ("reference_abi_helpers", normalize_reference_abi_helpers),
        ("reference_safe_host_ids", normalize_reference_safe_host_ids),
        ("reference_float_bits", normalize_reference_float_bits),
        ("reference_errors", normalize_reference_errors),
        ("reference_error_text", normalize_reference_error_text),
        ("reference_error_locations", normalize_reference_error_locations),
        ("reference_value_kinds", normalize_reference_value_kinds),
        ("reference_expression_kinds", normalize_reference_expression_kinds),
        ("reference_function_return_kinds", normalize_reference_function_return_kinds),
        ("reference_nested_kinds", normalize_reference_nested_kinds),
        ("reference_source_preprocess", normalize_reference_source_preprocess),
        ("reference_data_builders", normalize_reference_data_builders),
        ("reference_data_access", normalize_reference_data_access),
        ("reference_handle_kind_access", normalize_reference_handle_kind_access),
        ("reference_bytes_literals", normalize_reference_bytes_literals),
        ("native_parser", normalize_native_parser),
        ("native_argument_defaults", normalize_native_argument_defaults),
        ("calls_closures", normalize_calls_closures),
        ("keyword_calls", normalize_keyword_calls),
        ("combine_native_parser", combine_native_parser),
        ("native_parser_expressions", normalize_native_parser_expressions),
        ("native_parser_target_dispatch", normalize_native_parser_target_dispatch),
        ("parser_errors", normalize_parser_errors),
        ("boolops", normalize_boolops),
        ("closures", normalize_closures),
        ("pattern_slices", normalize_pattern_slices),
        ("extended_semantics", normalize_extended_semantics),
        # Extended semantics installs MatchAs defaults using the original
        # constructor signature. Rename colliding parameters only afterwards.
        ("expr_stmt_initializer", normalize_expr_stmt_initializer),
        ("pattern_constructor_collisions", normalize_pattern_constructor_collisions),
        ("native_statement_bodies", normalize_native_statement_bodies),
        ("native_node_fields", normalize_native_node_fields),
        ("pop_top", normalize_pop_top),
        ("make_function", normalize_make_function),
        ("collections", normalize_collections),
        ("builtins", normalize_builtins),
        ("tracebacks", normalize_tracebacks),
        ("nested_code_introspection", _normalize_nested_code_introspection),
        ("opcode_validation", _normalize_opcode_validation),
        ("truthiness", normalize_truthiness),
        ("string_addition", normalize_string_addition),
        ("reference_type_errors", normalize_reference_type_errors),
        # These AST passes intentionally run only after all text-sensitive VM
        # passes, replacing unsafe specs, host introspection, and implicit
        # iterator/exception state.
        ("runtime_specs", normalize_runtime_specs),
        ("runtime_dispatch", normalize_runtime_dispatch),
        ("runtime_execution", normalize_runtime_execution),
        # Parameter collisions include explicit functions and dataclass-generated
        # initializers. Repair them before the final local-variable collision pass.
        ("parameter_name_collisions", normalize_parameter_name_collisions),
        ("builtin_parameter_collisions", normalize_builtin_parameter_collisions),
        # Run last: it unparses all changed modules and must see the complete
        # flattened class namespace produced by every earlier pass.
        ("local_name_collisions", normalize_local_name_collisions),
    )
    DIAGNOSTIC_PATH.unlink(missing_ok=True)
    NORMALIZATION_LOG_PATH.unlink(missing_ok=True)
    for name, callback in steps:
        _run_step(name, callback)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
