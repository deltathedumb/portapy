from __future__ import annotations

from portapy import NativeObjectReference
from portapy import native_binary as native
from portapy.reference_api import Status, ValueKind


class FakeObjectApi:
    def __init__(self, *, host_id: int | None) -> None:
        self.host_id = host_id
        self.cleared = 0

    def portapy_value_get_kind(self, runtime, handle, out_kind) -> int:
        del runtime, handle
        out_kind._obj.value = int(ValueKind.OBJECT)
        return int(Status.OK)

    def portapy_value_get_host_id(self, runtime, handle, out_host_id) -> int:
        del runtime, handle
        if self.host_id is None:
            return int(Status.TYPE_ERROR)
        out_host_id._obj.value = self.host_id
        return int(Status.OK)

    def portapy_error_clear(self, runtime) -> int:
        del runtime
        self.cleared += 1
        return int(Status.OK)


def environment_for(api: FakeObjectApi) -> native.NativeEnvironment:
    environment = object.__new__(native.NativeEnvironment)
    environment._api = api
    environment._runtime = native._U64(1)
    environment._closed = False
    environment._objects = {}
    return environment


def test_vm_owned_object_returns_opaque_reference() -> None:
    api = FakeObjectApi(host_id=None)
    environment = environment_for(api)
    result = environment._unbox(99)
    assert isinstance(result, NativeObjectReference)
    assert api.cleared == 1


def test_registered_host_object_still_resolves_to_python_object() -> None:
    api = FakeObjectApi(host_id=42)
    environment = environment_for(api)
    expected = object()
    environment._objects[42] = expected
    assert environment._unbox(99) is expected
    assert api.cleared == 0
