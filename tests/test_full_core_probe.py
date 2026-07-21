from portapy.native_full_core_probe import portapy_full_core_probe


def test_full_core_probe_executes_closure_and_class_path() -> None:
    assert portapy_full_core_probe() == 42
