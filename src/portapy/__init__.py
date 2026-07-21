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
# Install recursive container boxing, environment helpers, and traceback support
# before any native module instance is created.
from . import native_tuple_binary as _native_tuple_binary
from . import native_dict_binary as _native_dict_binary
from . import native_list_binary as _native_list_binary
from . import native_environment_helpers as _native_environment_helpers
from .native_traceback_binary import NativeTracebackFrame
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
    "NativeTracebackFrame",
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
