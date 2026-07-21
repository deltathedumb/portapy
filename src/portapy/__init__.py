"""PortaPy public embedding API."""

# Install the function-body control-flow overlay before any hosted/native facade
# is imported. Direct imports such as ``from portapy import native_api_functions``
# also pass through package initialization, so they receive the same semantics.
from . import native_api_function_control as _native_api_function_control
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
