from tools.materialize_full_reference_entry import main as materialize_reference_entry
from tools.normalize_full_reference_abi_helpers import (
    main as normalize_reference_abi_helpers,
)


def test_full_core_probe_executes_reference_abi_path() -> None:
    materialize_reference_entry()
    normalize_reference_abi_helpers()
    from portapy.native_full_core_probe import portapy_full_core_probe

    assert portapy_full_core_probe() == 42
