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
    "PortaPyError",
    "PortaPyExecutionError",
    "Runtime",
    "Snapshot",
    "Status",
    "ValueKind",
    "new",
]
