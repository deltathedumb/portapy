from __future__ import annotations

from tools.rewrite_generated_closures import _find_function_slot, _state_and_helpers


def _namespace() -> dict[str, object]:
    refs = [0] * 32
    refs[10] = 1
    refs[11] = 1
    globals_by_name: dict[str, int] = {}

    def value_is_valid(runtime: int, value: int) -> bool:
        return runtime == 1 and value in (10, 11, 20, 21)

    def bind_global(runtime: int, name: str, value: int) -> int:
        assert runtime == 1
        globals_by_name[name] = value
        return 0

    namespace: dict[str, object] = {
        "PORTAPY_OK": 0,
        "PORTAPY_COMPILE_ERROR": 2,
        "PORTAPY_VALUE_CALLABLE": 6,
        "_value_is_valid": value_is_valid,
        "_value_refs": refs,
        "_bind_global": bind_global,
        "_collect_local_names": lambda body, parameters: [parameters] if parameters else [],
        "_trim": lambda source, start, end: [start, end],
        "_word_at": lambda source, start, end, word: source[start:end].startswith(word),
        "_parse_definition_header": lambda source, start, end: ["nested", "", end, 0],
        "globals_by_name": globals_by_name,
        "refs": refs,
    }
    exec(_state_and_helpers(), namespace)
    return namespace


def test_closure_observes_mutation_after_definition() -> None:
    namespace = _namespace()

    frame = namespace["_closure_begin_frame"](1, 5, ["value"])
    namespace["_closure_update_active_cell"](1, "value", 10)
    namespace["_closure_capture_active_cells"](1, 5, 6)
    namespace["_closure_update_active_cell"](1, "value", 11)
    namespace["_closure_end_frame"](1, frame)

    namespace["_closure_bind_captures"](1, 6, [])
    assert namespace["globals_by_name"]["value"] == 11


def test_separate_closure_instances_keep_separate_cells() -> None:
    namespace = _namespace()

    first_frame = namespace["_closure_begin_frame"](1, 5, ["value"])
    namespace["_closure_update_active_cell"](1, "value", 10)
    namespace["_closure_capture_active_cells"](1, 5, 6)
    namespace["_closure_end_frame"](1, first_frame)

    second_frame = namespace["_closure_begin_frame"](1, 5, ["value"])
    namespace["_closure_update_active_cell"](1, "value", 11)
    namespace["_closure_capture_active_cells"](1, 5, 7)
    namespace["_closure_end_frame"](1, second_frame)

    namespace["_closure_bind_captures"](1, 6, [])
    assert namespace["globals_by_name"]["value"] == 10
    namespace["_closure_bind_captures"](1, 7, [])
    assert namespace["globals_by_name"]["value"] == 11


def test_callable_alias_resolves_function_slot_from_value_handle() -> None:
    namespace: dict[str, object] = {
        "PORTAPY_VALUE_CALLABLE": 6,
        "_global_value": [0, 20],
        "_value_kind": [0] * 20 + [6],
        "_value_i64": [0] * 20 + [3],
        "_function_runtime": [0, 0, 0, 1],
        "_find_global_slot": lambda runtime, name: 1 if runtime == 1 and name == "alias" else 0,
        "_value_is_valid": lambda runtime, value: runtime == 1 and value == 20,
    }
    exec(_find_function_slot(), namespace)

    assert namespace["_find_function_slot"](1, "alias") == 3
    assert namespace["_find_function_slot"](1, "missing") == 0
