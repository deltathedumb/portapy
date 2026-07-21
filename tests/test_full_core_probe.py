from tools.materialize_full_reference_entry import main as materialize_reference_entry
from tools.normalize_full_reference_abi_helpers import (
    main as normalize_reference_abi_helpers,
)


def test_full_core_probe_executes_reference_abi_path() -> None:
    materialize_reference_entry()
    normalize_reference_abi_helpers()
    from portapy.native_full_core_probe import portapy_full_core_probe
    from portapy.native_full_reference_entry import _runtimes

    result = portapy_full_core_probe()
    errors = [
        runtime.last_error()
        for runtime in _runtimes
        if runtime is not None and runtime.last_error() is not None
    ]
    assert result == 42, errors
