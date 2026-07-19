"""Python-authored state behind PortaPy's native opaque-handle ABI.

This module deliberately contains all runtime/value ownership semantics. The C
shim only converts opaque pointers and out-parameters into the integer handles
used here. Source parsing and VM execution remain gated until PortaPy replaces
the bootstrap host-``ast`` frontend with its own Python-written parser.
"""

PORTAPY_OK = 0
PORTAPY_INVALID_ARGUMENT = 1
PORTAPY_COMPILE_ERROR = 2
PORTAPY_RUNTIME_ERROR = 3
PORTAPY_TYPE_ERROR = 4
PORTAPY_NOT_FOUND = 5
PORTAPY_CLOSED = 6
PORTAPY_INVALID_HANDLE = 7
PORTAPY_INTERRUPTED = 8
PORTAPY_ABI_MISMATCH = 9

PORTAPY_VALUE_NONE = 0
PORTAPY_VALUE_BOOL = 1
PORTAPY_VALUE_INT = 2
PORTAPY_VALUE_FLOAT = 3
PORTAPY_VALUE_STRING = 4
PORTAPY_VALUE_BYTES = 5
PORTAPY_VALUE_CALLABLE = 6
PORTAPY_VALUE_OBJECT = 7

_RUNTIME_CAPACITY = 64
_VALUE_CAPACITY = 4096

_runtime_active = [0] * (_RUNTIME_CAPACITY + 1)
_next_runtime = [1]

_value_active = [0] * (_VALUE_CAPACITY + 1)
_value_owner = [0] * (_VALUE_CAPACITY + 1)
_value_refs = [0] * (_VALUE_CAPACITY + 1)
_value_kind = [0] * (_VALUE_CAPACITY + 1)
_value_i64 = [0] * (_VALUE_CAPACITY + 1)
_next_value = [1]


def portapy_internal_runtime_status(runtime: int) -> int:
    if runtime <= 0 or runtime > _RUNTIME_CAPACITY:
        return PORTAPY_INVALID_HANDLE
    if _runtime_active[runtime] == 0:
        return PORTAPY_CLOSED
    return PORTAPY_OK


def portapy_internal_runtime_create() -> int:
    runtime = _next_runtime[0]
    if runtime > _RUNTIME_CAPACITY:
        return 0
    _next_runtime[0] = runtime + 1
    _runtime_active[runtime] = 1
    return runtime


def portapy_internal_runtime_destroy(runtime: int) -> int:
    status = portapy_internal_runtime_status(runtime)
    if status != PORTAPY_OK:
        return status

    value = 1
    limit = _next_value[0]
    while value < limit:
        if _value_active[value] != 0 and _value_owner[value] == runtime:
            _value_active[value] = 0
            _value_owner[value] = 0
            _value_refs[value] = 0
            _value_kind[value] = PORTAPY_VALUE_NONE
            _value_i64[value] = 0
        value = value + 1

    _runtime_active[runtime] = 0
    return PORTAPY_OK


def portapy_internal_value_status(runtime: int, value: int) -> int:
    runtime_status = portapy_internal_runtime_status(runtime)
    if runtime_status != PORTAPY_OK:
        return runtime_status
    if value <= 0 or value > _VALUE_CAPACITY:
        return PORTAPY_INVALID_HANDLE
    if _value_active[value] == 0:
        return PORTAPY_INVALID_HANDLE
    if _value_owner[value] != runtime:
        return PORTAPY_INVALID_HANDLE
    return PORTAPY_OK


def portapy_internal_value_create_i64(runtime: int, payload: int) -> int:
    if portapy_internal_runtime_status(runtime) != PORTAPY_OK:
        return 0
    value = _next_value[0]
    if value > _VALUE_CAPACITY:
        return 0
    _next_value[0] = value + 1
    _value_active[value] = 1
    _value_owner[value] = runtime
    _value_refs[value] = 1
    _value_kind[value] = PORTAPY_VALUE_INT
    _value_i64[value] = payload
    return value


def portapy_internal_value_retain(runtime: int, value: int) -> int:
    status = portapy_internal_value_status(runtime, value)
    if status != PORTAPY_OK:
        return status
    _value_refs[value] = _value_refs[value] + 1
    return PORTAPY_OK


def portapy_internal_value_release(runtime: int, value: int) -> int:
    status = portapy_internal_value_status(runtime, value)
    if status != PORTAPY_OK:
        return status
    refs = _value_refs[value] - 1
    _value_refs[value] = refs
    if refs <= 0:
        _value_active[value] = 0
        _value_owner[value] = 0
        _value_refs[value] = 0
        _value_kind[value] = PORTAPY_VALUE_NONE
        _value_i64[value] = 0
    return PORTAPY_OK


def portapy_internal_value_kind(runtime: int, value: int) -> int:
    if portapy_internal_value_status(runtime, value) != PORTAPY_OK:
        return PORTAPY_VALUE_OBJECT
    return _value_kind[value]


def portapy_internal_value_i64(runtime: int, value: int) -> int:
    if portapy_internal_value_status(runtime, value) != PORTAPY_OK:
        return 0
    return _value_i64[value]
