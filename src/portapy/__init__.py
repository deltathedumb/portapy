"""PortaPy public embedding API."""
from .environment import (
    BindingError,
    Environment,
    EnvironmentClosedError,
    EnvironmentSnapshot,
    ExecutionError,
    PortaPyError,
    new,
)
from .native_binary import (
    NativeCallableReference,
    NativeEnvironment,
    NativeEnvironmentSnapshot,
    NativeHostReference,
    NativePortaPyModule,
    import_binary,
    load_native,
)
# Install recursive tuple boxing before any native module instance is created.
from . import native_tuple_binary as _native_tuple_binary
from .reference_api import ErrorInfo, Runtime, Status, ValueKind

Snapshot = EnvironmentSnapshot
PortaPyExecutionError = ExecutionError

__version__ = "3.14.0-dev"

__all__ = [
    "BindingError",
    "Environment",
    "EnvironmentClosedError",
    "EnvironmentSnapshot",
    "ErrorInfo",
    "ExecutionError",
    "NativeCallableReference",
    "NativeEnvironment",
    "NativeEnvironmentSnapshot",
    "NativeHostReference",
    "NativePortaPyModule",
    "PortaPyError",
    "PortaPyExecutionError",
    "Runtime",
    "Snapshot",
    "Status",
    "ValueKind",
    "import_binary",
    "load_native",
    "new",
]
