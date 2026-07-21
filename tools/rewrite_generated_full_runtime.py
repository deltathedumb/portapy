"""Replace the generated incremental executor with PortaPy's full frontend and VM.

The generated native handle tables remain the public ABI representation.  This
rewrite appends a Python-authored adapter that unboxes those handles into the
standalone VM, executes portable bytecode, and boxes the resulting globals back
into the same ABI.  C and NASM remain boundary glue only.
"""
from __future__ import annotations

from pathlib import Path


_IMPORTS = '''from .core.portable_frontend import compile_portable_source as _full_compile_source
from .core.vm import Frame as _FullFrame
from .core.vm import VirtualMachine as _FullVirtualMachine
from .native_api import (
    _byte_data as _full_byte_data,
    _find_global_slot as _full_find_global_slot,
    _global_name as _full_global_name,
    _global_runtime as _full_global_runtime,
    _global_value as _full_global_value,
    _value_data_size as _full_value_data_size,
    _value_data_start as _full_value_data_start,
    _value_i64 as _full_value_i64,
)
'''

_RENAMES = (
    ("_portapy_eval_span_impl", "_incremental_portapy_eval_span_impl"),
    ("_portapy_exec_span_impl", "_incremental_portapy_exec_span_impl"),
    ("_portapy_value_get_host_id_impl", "_incremental_portapy_value_get_host_id_impl"),
    (
        "_portapy_value_get_host_callable_id_impl",
        "_incremental_portapy_value_get_host_callable_id_impl",
    ),
    ("_portapy_error_clear_impl", "_incremental_portapy_error_clear_impl"),
    ("_portapy_runtime_destroy_impl", "_incremental_portapy_runtime_destroy_impl"),
)


def _overlay(target: str) -> str:
    argument_register = "rcx" if target == "windows" else "rdi"
    return f'''

# ---- Full portable frontend / VM adapter ------------------------------------


def assembly_func(function):
    return function


@assembly_func
def _full_bits_to_float(bits: int) -> float:
    """
    movq xmm0, {argument_register}
    ret
    """


@assembly_func
def _full_float_to_bits(value: float) -> int:
    """
    movq rax, xmm0
    ret
    """


_full_runtime_ids = [0]
_full_runtime_machines = [None]
_full_runtime_namespaces = [None]
_full_runtime_reserved = [None]
_full_runtime_users = [None]
_full_object_runtime = [0]
_full_object_handle = [0]
_full_object_value = [None]


def _full_runtime_slot(runtime: int) -> int:
    index = 1
    while index < len(_full_runtime_ids):
        if _full_runtime_ids[index] == runtime:
            return index
        index += 1
    return 0


def _full_seed_builtins(namespace: dict) -> None:
    namespace["print"] = print
    namespace["len"] = len
    namespace["range"] = range
    namespace["str"] = str
    namespace["int"] = int
    namespace["float"] = float
    namespace["bool"] = bool
    namespace["list"] = list
    namespace["dict"] = dict
    namespace["tuple"] = tuple
    namespace["set"] = set
    namespace["bytes"] = bytes
    namespace["bytearray"] = bytearray
    namespace["object"] = object
    namespace["type"] = type
    namespace["slice"] = slice
    namespace["property"] = property
    namespace["classmethod"] = classmethod
    namespace["staticmethod"] = staticmethod
    namespace["abs"] = abs
    namespace["min"] = min
    namespace["max"] = max
    namespace["sum"] = sum
    namespace["sorted"] = sorted
    namespace["enumerate"] = enumerate
    namespace["zip"] = zip
    namespace["map"] = map
    namespace["filter"] = filter
    namespace["isinstance"] = isinstance
    namespace["hasattr"] = hasattr
    namespace["getattr"] = getattr
    namespace["setattr"] = setattr
    namespace["repr"] = repr
    namespace["hash"] = hash
    namespace["id"] = id
    namespace["Exception"] = Exception
    namespace["BaseException"] = BaseException
    namespace["NameError"] = NameError
    namespace["TypeError"] = TypeError
    namespace["ValueError"] = ValueError
    namespace["RuntimeError"] = RuntimeError
    namespace["AttributeError"] = AttributeError
    namespace["KeyError"] = KeyError
    namespace["IndexError"] = IndexError
    namespace["StopIteration"] = StopIteration
    namespace["StopAsyncIteration"] = StopAsyncIteration
    namespace["ZeroDivisionError"] = ZeroDivisionError
    namespace["OverflowError"] = OverflowError
    namespace["ArithmeticError"] = ArithmeticError
    namespace["LookupError"] = LookupError
    namespace["UnboundLocalError"] = UnboundLocalError
    namespace["NotImplementedError"] = NotImplementedError
    namespace["OSError"] = OSError
    namespace["IOError"] = IOError
    namespace["ImportError"] = ImportError
    namespace["ModuleNotFoundError"] = ModuleNotFoundError
    namespace["AssertionError"] = AssertionError


def _full_source_line(lines, line: int) -> str:
    if line <= 0 or line > len(lines):
        return ""
    return lines[line - 1].strip()


class _FullTracingVirtualMachine(_FullVirtualMachine):
    def __init__(self, runtime: int) -> None:
        super().__init__()
        self.runtime = runtime
        self.trace_frames = []

    def _run_frame(self, frame: _FullFrame):
        try:
            return super()._run_frame(frame)
        except BaseException:
            offset = frame.ip - 1
            if offset < 0:
                offset = 0
            lines = getattr(frame.code, "instruction_lines", [])
            columns = getattr(frame.code, "instruction_columns", [])
            line = getattr(frame.code, "first_line", 1)
            column = 1
            if offset < len(lines) and lines[offset] > 0:
                line = lines[offset]
            if offset < len(columns) and columns[offset] > 0:
                column = columns[offset]
            definition_line = getattr(frame.code, "definition_line", line)
            definition_column = getattr(frame.code, "definition_column", 1)
            source_lines = getattr(frame.code, "source_lines", [])
            self.trace_frames.append([
                line,
                column,
                definition_line,
                definition_column,
                frame.code.name,
                _full_source_line(source_lines, line),
                _full_source_line(source_lines, definition_line),
            ])
            raise


class _FullHostObject:
    def __init__(self, runtime: int, host_id: int) -> None:
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "host_id", host_id)

    def __getattr__(self, name: str):
        owner = _host_portapy_value_from_host_object_impl(self.runtime, self.host_id)
        if owner == 0:
            raise AttributeError(name)
        value = _host_portapy_host_get_attr_span_impl(
            self.runtime,
            owner,
            name,
            len(name),
        )
        _scalar_release(self.runtime, owner)
        if value == 0:
            raise AttributeError(name)
        result = _full_unbox(self.runtime, value)
        _scalar_release(self.runtime, value)
        return result

    def __setattr__(self, name: str, value) -> None:
        if name == "runtime" or name == "host_id":
            object.__setattr__(self, name, value)
            return
        owner = _host_portapy_value_from_host_object_impl(self.runtime, self.host_id)
        item = _full_box(self.runtime, value)
        if owner == 0 or item == 0:
            raise AttributeError(name)
        status = _host_portapy_host_set_attr_span_impl(
            self.runtime,
            owner,
            name,
            len(name),
            item,
        )
        _scalar_release(self.runtime, owner)
        _scalar_release(self.runtime, item)
        if status != PORTAPY_OK:
            raise AttributeError(name)


class _FullHostCallable:
    def __init__(self, runtime: int, callable_id: int) -> None:
        self.runtime = runtime
        self.callable_id = callable_id

    def __call__(self, *args, **kwargs):
        if kwargs:
            raise TypeError("native host callbacks do not accept keyword arguments")
        handles = []
        index = 0
        while index < len(args):
            handle = _full_box(self.runtime, args[index])
            if handle == 0:
                raise RuntimeError("could not box host callback argument")
            handles.append(handle)
            index += 1
        dispatched = _dispatch_host_call(
            self.runtime,
            self.callable_id,
            handles,
            0,
        )
        if dispatched[2] != PORTAPY_OK or dispatched[0] == 0:
            raise RuntimeError("native host callback failed")
        result = _full_unbox(self.runtime, dispatched[0])
        _scalar_release(self.runtime, dispatched[0])
        return result


class _FullImportLoader:
    def __init__(self, namespace: dict) -> None:
        self.namespace = namespace

    def __call__(self, module_name: str):
        pieces = module_name.split(".")
        if not pieces or pieces[0] not in self.namespace:
            raise ModuleNotFoundError(module_name)
        value = self.namespace[pieces[0]]
        index = 1
        while index < len(pieces):
            try:
                value = getattr(value, pieces[index])
            except AttributeError:
                raise ModuleNotFoundError(module_name)
            index += 1
        return value


def _full_ensure_runtime(runtime: int) -> int:
    if not _runtime_is_valid(runtime):
        return 0
    existing = _full_runtime_slot(runtime)
    if existing != 0:
        return existing
    namespace = {{
        "__name__": "__main__",
        "__package__": "",
        "__doc__": None,
        "__annotations__": {{}},
    }}
    _full_seed_builtins(namespace)
    namespace["__pyinbin_import__"] = _FullImportLoader(namespace)
    machine = _FullTracingVirtualMachine(runtime)
    _full_runtime_ids.append(runtime)
    _full_runtime_machines.append(machine)
    _full_runtime_namespaces.append(namespace)
    _full_runtime_reserved.append(dict(namespace))
    _full_runtime_users.append([])
    return len(_full_runtime_ids) - 1


def _full_object_slot(runtime: int, handle: int) -> int:
    index = 1
    while index < len(_full_object_handle):
        if (
            _full_object_runtime[index] == runtime
            and _full_object_handle[index] == handle
            and _value_is_valid(runtime, handle)
        ):
            return index
        index += 1
    return 0


def _full_box_opaque(runtime: int, value) -> int:
    kind = PORTAPY_VALUE_OBJECT
    if callable(value):
        kind = PORTAPY_VALUE_CALLABLE
    handle = _append_value(runtime, kind, 0)
    if handle == 0:
        return 0
    _full_object_runtime.append(runtime)
    _full_object_handle.append(handle)
    _full_object_value.append(value)
    return handle


def _full_data(runtime: int, handle: int):
    start = _full_value_data_start[handle]
    size = _full_value_data_size[handle]
    data = bytearray()
    index = 0
    while index < size:
        data.append(_full_byte_data[start + index])
        index += 1
    return bytes(data)


def _full_unbox(runtime: int, handle: int):
    if not _value_is_valid(runtime, handle):
        raise RuntimeError("invalid PortaPy value handle")
    opaque = _full_object_slot(runtime, handle)
    if opaque != 0:
        return _full_object_value[opaque]
    kind = _value_kind[handle]
    if kind == PORTAPY_VALUE_NONE:
        return None
    if kind == PORTAPY_VALUE_BOOL:
        return _full_value_i64[handle] != 0
    if kind == PORTAPY_VALUE_INT:
        return _full_value_i64[handle]
    if kind == PORTAPY_VALUE_FLOAT:
        return _full_bits_to_float(_full_value_i64[handle])
    if kind == PORTAPY_VALUE_STRING:
        return _full_data(runtime, handle).decode("utf-8")
    if kind == PORTAPY_VALUE_BYTES:
        return _full_data(runtime, handle)
    if kind == PORTAPY_VALUE_TUPLE:
        result = []
        size = _scalar_tuple_size_unchecked(handle)
        index = 0
        while index < size:
            result.append(_full_unbox(runtime, _scalar_tuple_item_unchecked(handle, index)))
            index += 1
        return tuple(result)
    if kind == PORTAPY_VALUE_LIST:
        result = []
        size = _scalar_list_size_unchecked(handle)
        index = 0
        while index < size:
            result.append(_full_unbox(runtime, _scalar_list_item_unchecked(handle, index)))
            index += 1
        return result
    if kind == PORTAPY_VALUE_DICT:
        result = {{}}
        index = 1
        while index < len(_scalar_dict_entry_owner):
            if _scalar_dict_entry_owner[index] == handle:
                result[_scalar_dict_entry_key[index]] = _full_unbox(
                    runtime,
                    _scalar_dict_entry_value[index],
                )
            index += 1
        return result
    if kind == PORTAPY_VALUE_CALLABLE:
        resolved = _host_callable_identifier(runtime, handle)
        if resolved[1] != PORTAPY_OK:
            raise TypeError("callable handle is not a registered host callback")
        return _FullHostCallable(runtime, resolved[0])
    if kind == PORTAPY_VALUE_OBJECT:
        host_id = _host_portapy_value_get_host_id_impl(runtime, handle)
        if _portapy_last_status_impl() != PORTAPY_OK:
            raise TypeError("object handle is not a registered host object")
        return _FullHostObject(runtime, host_id)
    raise TypeError("unsupported PortaPy value kind")


def _full_box_data(runtime: int, kind: int, data) -> int:
    handle = _append_data_value(runtime, kind, len(data))
    if handle == 0:
        return 0
    index = 0
    while index < len(data):
        if _set_data_byte(runtime, handle, index, data[index]) != PORTAPY_OK:
            _scalar_release(runtime, handle)
            return 0
        index += 1
    if kind == PORTAPY_VALUE_STRING:
        if _validate_utf8_value(runtime, handle) != PORTAPY_OK:
            _scalar_release(runtime, handle)
            return 0
    return handle


def _full_box_sequence(runtime: int, value, mutable: bool) -> int:
    if mutable:
        result = _portapy_list_begin_impl(runtime, len(value))
    else:
        result = _portapy_tuple_begin_impl(runtime, len(value))
    if result == 0:
        return 0
    index = 0
    while index < len(value):
        item = _full_box(runtime, value[index])
        if item == 0:
            _scalar_release(runtime, result)
            return 0
        if mutable:
            status = _portapy_list_initialize_item_impl(runtime, result, index, item)
        else:
            status = _portapy_tuple_set_item_impl(runtime, result, index, item)
        _scalar_release(runtime, item)
        if status != PORTAPY_OK:
            _scalar_release(runtime, result)
            return 0
        index += 1
    if mutable:
        status = _portapy_list_finish_impl(runtime, result)
    else:
        status = _portapy_tuple_finish_impl(runtime, result)
    if status != PORTAPY_OK:
        _scalar_release(runtime, result)
        return 0
    return result


def _full_box_dict(runtime: int, value: dict) -> int:
    for key in value:
        if type(key) is not str:
            return _full_box_opaque(runtime, value)
    result = _portapy_dict_begin_impl(runtime)
    if result == 0:
        return 0
    for key in value:
        item = _full_box(runtime, value[key])
        if item == 0:
            _scalar_release(runtime, result)
            return 0
        status = _portapy_dict_set_span_impl(runtime, result, key, len(key), item)
        _scalar_release(runtime, item)
        if status != PORTAPY_OK:
            _scalar_release(runtime, result)
            return 0
    return result


def _full_box(runtime: int, value) -> int:
    if isinstance(value, _FullHostObject):
        return _host_portapy_value_from_host_object_impl(runtime, value.host_id)
    if isinstance(value, _FullHostCallable):
        return _portapy_value_from_host_callable_impl(runtime, value.callable_id)
    if value is None:
        return _append_value(runtime, PORTAPY_VALUE_NONE, 0)
    if type(value) is bool:
        return _append_value(runtime, PORTAPY_VALUE_BOOL, 1 if value else 0)
    if type(value) is int:
        return _append_value(runtime, PORTAPY_VALUE_INT, value)
    if type(value) is float:
        return _append_value(runtime, PORTAPY_VALUE_FLOAT, _full_float_to_bits(value))
    if type(value) is str:
        return _full_box_data(runtime, PORTAPY_VALUE_STRING, value.encode("utf-8"))
    if type(value) is bytes or type(value) is bytearray:
        return _full_box_data(runtime, PORTAPY_VALUE_BYTES, bytes(value))
    if type(value) is tuple:
        return _full_box_sequence(runtime, value, False)
    if type(value) is list:
        return _full_box_sequence(runtime, value, True)
    if type(value) is dict:
        return _full_box_dict(runtime, value)
    return _full_box_opaque(runtime, value)


def _full_native_names(runtime: int):
    names = []
    slot = 1
    while slot < len(_full_global_runtime):
        if _full_global_runtime[slot] == runtime and _full_global_name[slot] != "":
            names.append(_full_global_name[slot])
        slot += 1
    return names


def _full_remove_global(runtime: int, name: str) -> None:
    slot = _full_find_global_slot(runtime, name)
    if slot == 0:
        return
    value = _full_global_value[slot]
    if _value_is_valid(runtime, value):
        _scalar_release(runtime, value)
    _full_global_runtime[slot] = 0
    _full_global_name[slot] = ""
    _full_global_value[slot] = 0


def _full_sync_in(runtime: int, state: int) -> None:
    namespace = _full_runtime_namespaces[state]
    current = _full_native_names(runtime)
    previous = _full_runtime_users[state]
    index = 0
    while index < len(previous):
        if previous[index] not in current and previous[index] in namespace:
            del namespace[previous[index]]
        index += 1
    slot = 1
    while slot < len(_full_global_runtime):
        if _full_global_runtime[slot] == runtime and _full_global_name[slot] != "":
            namespace[_full_global_name[slot]] = _full_unbox(
                runtime,
                _full_global_value[slot],
            )
        slot += 1
    _full_runtime_users[state] = current


def _full_is_reserved(state: int, name: str, value) -> bool:
    reserved = _full_runtime_reserved[state]
    return name in reserved and reserved[name] is value


def _full_sync_out(runtime: int, state: int) -> int:
    namespace = _full_runtime_namespaces[state]
    names = []
    for name in namespace:
        value = namespace[name]
        if not name.startswith("__") and not _full_is_reserved(state, name, value):
            names.append(name)
    previous = _full_runtime_users[state]
    index = 0
    while index < len(previous):
        if previous[index] not in names:
            _full_remove_global(runtime, previous[index])
        index += 1
    index = 0
    while index < len(names):
        name = names[index]
        handle = _full_box(runtime, namespace[name])
        if handle == 0:
            return _portapy_last_status_impl()
        status = _bind_global(runtime, name, handle)
        if status != PORTAPY_OK:
            _scalar_release(runtime, handle)
            return status
        index += 1
    _full_runtime_users[state] = names
    return _set_status(PORTAPY_OK)


def _full_status_for_error(error, compile_phase: bool) -> int:
    if compile_phase:
        return PORTAPY_COMPILE_ERROR
    if isinstance(error, ModuleNotFoundError):
        return PORTAPY_NOT_FOUND
    if isinstance(error, TypeError):
        return PORTAPY_TYPE_ERROR
    return PORTAPY_RUNTIME_ERROR


def _full_error_position(error):
    position = getattr(error, "pos", None)
    line = int(getattr(position, "line", 1))
    column = int(getattr(position, "column", 1))
    if line <= 0:
        line = 1
    if column <= 0:
        column = 1
    return [line, column]


def _full_publish_traceback(runtime: int, machine, filename: str, source: str) -> None:
    source_lines = source.splitlines()
    recorded = machine.trace_frames
    index = len(recorded) - 1
    while index >= 0:
        frame = recorded[index]
        line = frame[0]
        column = frame[1]
        function_name = frame[4]
        source_line = frame[5]
        if function_name == filename:
            function_name = "<module>"
        elif index != 0:
            line = frame[2]
            column = frame[3]
            source_line = frame[6]
        if source_line == "":
            source_line = _full_source_line(source_lines, line)
        _portapy_traceback_add_impl(
            runtime,
            line,
            column,
            function_name,
            source_line,
        )
        index -= 1


def _full_run(runtime: int, source: str, mode: str):
    state = _full_ensure_runtime(runtime)
    if state == 0:
        return [PORTAPY_INVALID_HANDLE, 0]
    _clear_runtime_error(runtime)
    _portapy_traceback_reset_impl(runtime)
    _full_sync_in(runtime, state)
    machine = _full_runtime_machines[state]
    machine.trace_frames = []
    filename = _traceback_filename_for_runtime(runtime)
    try:
        code = _full_compile_source(source, filename, mode)
    except BaseException as error:
        position = _full_error_position(error)
        status = _full_status_for_error(error, True)
        source_line = _full_source_line(source.splitlines(), position[0])
        _portapy_traceback_add_impl(
            runtime,
            position[0],
            position[1],
            "<module>",
            source_line,
        )
        _fail(
            runtime,
            status,
            type(error).__name__,
            str(error),
            position[0],
            position[1],
        )
        return [status, 0]
    try:
        result = machine.run(code, _full_runtime_namespaces[state])
    except BaseException as error:
        status = _full_status_for_error(error, False)
        _full_publish_traceback(runtime, machine, filename, source)
        position = [1, 1]
        if machine.trace_frames:
            position = [machine.trace_frames[0][0], machine.trace_frames[0][1]]
        _fail(
            runtime,
            status,
            type(error).__name__,
            str(error),
            position[0],
            position[1],
        )
        return [status, 0]
    status = _full_sync_out(runtime, state)
    if status != PORTAPY_OK:
        return [status, 0]
    if mode == "eval":
        handle = _full_box(runtime, result)
        if handle == 0:
            return [_portapy_last_status_impl(), 0]
        return [PORTAPY_OK, handle]
    return [PORTAPY_OK, 0]


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    if source_size < 0 or source_size > len(source):
        return _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "source size is invalid",
        )
    executed = _full_run(runtime, source[:source_size], "exec")
    return _set_status(executed[0])


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    if source_size < 0 or source_size > len(source):
        _fail(
            runtime,
            PORTAPY_INVALID_ARGUMENT,
            "ValueError",
            "source size is invalid",
        )
        return 0
    evaluated = _full_run(runtime, source[:source_size], "eval")
    _set_status(evaluated[0])
    return evaluated[1]


def _portapy_value_get_host_id_impl(runtime: int, value: int) -> int:
    if _full_object_slot(runtime, value) != 0:
        _fail(
            runtime,
            PORTAPY_TYPE_ERROR,
            "TypeError",
            "value is a PortaPy-owned object, not a host object",
        )
        return 0
    return _incremental_portapy_value_get_host_id_impl(runtime, value)


def _portapy_value_get_host_callable_id_impl(runtime: int, value: int) -> int:
    if _full_object_slot(runtime, value) != 0:
        _fail(
            runtime,
            PORTAPY_TYPE_ERROR,
            "TypeError",
            "value is a PortaPy-owned callable, not a host callback",
        )
        return 0
    return _incremental_portapy_value_get_host_callable_id_impl(runtime, value)


def _portapy_error_clear_impl(runtime: int) -> int:
    slot = _full_runtime_slot(runtime)
    if slot != 0:
        _full_runtime_machines[slot].trace_frames = []
    return _incremental_portapy_error_clear_impl(runtime)


def _portapy_runtime_destroy_impl(runtime: int) -> int:
    slot = _full_runtime_slot(runtime)
    if slot != 0:
        _full_runtime_ids[slot] = 0
        _full_runtime_machines[slot] = None
        _full_runtime_namespaces[slot] = None
        _full_runtime_reserved[slot] = None
        _full_runtime_users[slot] = None
    index = 1
    while index < len(_full_object_runtime):
        if _full_object_runtime[index] == runtime:
            _full_object_runtime[index] = 0
            _full_object_handle[index] = 0
            _full_object_value[index] = None
        index += 1
    return _incremental_portapy_runtime_destroy_impl(runtime)
'''


def rewrite_generated_full_runtime(path: Path, *, target: str) -> Path:
    if target not in {"linux", "windows"}:
        raise ValueError(f"unsupported full-runtime target: {target}")
    source = path.read_text(encoding="utf-8")
    future = "from __future__ import annotations\n"
    if future not in source:
        raise ValueError("generated entry is missing future annotations import")
    if "def _full_run(" in source:
        raise ValueError("generated entry already contains the full runtime adapter")
    source = source.replace(future, future + "\n" + _IMPORTS, 1)
    for original, replacement in _RENAMES:
        marker = f"def {original}("
        if source.count(marker) != 1:
            raise ValueError(
                f"generated entry expected exactly one {original} definition"
            )
        source = source.replace(marker, f"def {replacement}(", 1)
    path.write_text(source.rstrip() + _overlay(target) + "\n", encoding="utf-8")
    return path


__all__ = ["rewrite_generated_full_runtime"]
