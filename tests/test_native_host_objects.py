from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_host as host


def _runtime() -> int:
    runtime = host._portapy_runtime_create_impl()
    assert runtime != 0
    return runtime


def _object(runtime: int, host_id: int) -> int:
    value = host._portapy_value_from_host_object_impl(runtime, host_id)
    assert value != 0
    return value


def _set_attr(runtime: int, owner: int, name: str, value: int) -> None:
    assert (
        host._portapy_host_set_attr_span_impl(
            runtime,
            owner,
            name,
            len(name),
            value,
        )
        == base.PORTAPY_OK
    )


def _set_global(runtime: int, name: str, value: int) -> None:
    assert (
        host._portapy_set_global_span_impl(runtime, name, len(name), value)
        == base.PORTAPY_OK
    )


def test_host_object_ids_and_attributes() -> None:
    runtime = _runtime()
    game = _object(runtime, 100)
    provider = _object(runtime, 200)
    http_provider = _object(runtime, 300)

    _set_attr(runtime, game, "provider", provider)
    _set_attr(runtime, provider, "HttpProvider", http_provider)

    resolved = host._portapy_host_get_attr_span_impl(
        runtime,
        game,
        "provider",
        len("provider"),
    )
    assert resolved != 0
    assert host._portapy_value_get_host_id_impl(runtime, resolved) == 200


def test_dotted_host_path_exec_and_snapshot_handle() -> None:
    runtime = _runtime()
    game = _object(runtime, 100)
    provider = _object(runtime, 200)
    http_provider = _object(runtime, 300)
    _set_attr(runtime, game, "provider", provider)
    _set_attr(runtime, provider, "HttpProvider", http_provider)
    _set_global(runtime, "game", game)

    source = "http_provider = game.provider.HttpProvider\n"
    assert host._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK

    captured = host._portapy_get_global_span_impl(
        runtime,
        "http_provider",
        len("http_provider"),
    )
    assert captured != 0
    assert host._portapy_value_get_host_id_impl(runtime, captured) == 300

    evaluated = host._portapy_eval_span_impl(
        runtime,
        "game.provider.HttpProvider",
        len("game.provider.HttpProvider"),
    )
    assert evaluated != 0
    assert host._portapy_value_get_host_id_impl(runtime, evaluated) == 300


def test_host_binding_keeps_caller_value_alive() -> None:
    runtime = _runtime()
    game = _object(runtime, 100)
    _set_global(runtime, "game", game)
    assert host._portapy_value_release_impl(runtime, game) == base.PORTAPY_OK

    rebound = host._portapy_get_global_span_impl(runtime, "game", len("game"))
    assert rebound != 0
    assert host._portapy_value_get_host_id_impl(runtime, rebound) == 100


def test_host_attribute_replace_keeps_new_value_and_releases_old_graph_ref() -> None:
    runtime = _runtime()
    owner = _object(runtime, 1)
    first = _object(runtime, 2)
    second = _object(runtime, 3)
    _set_attr(runtime, owner, "value", first)
    _set_attr(runtime, owner, "value", second)

    resolved = host._portapy_host_get_attr_span_impl(
        runtime,
        owner,
        "value",
        len("value"),
    )
    assert host._portapy_value_get_host_id_impl(runtime, resolved) == 3


def test_missing_host_attribute_reports_attribute_error() -> None:
    runtime = _runtime()
    owner = _object(runtime, 1)
    missing = host._portapy_host_get_attr_span_impl(
        runtime,
        owner,
        "missing",
        len("missing"),
    )
    assert missing == 0
    assert host._portapy_last_status_impl() == base.PORTAPY_NOT_FOUND
    assert host._portapy_error_type_size_impl(runtime) == len("AttributeError")


def test_non_host_source_still_uses_function_and_control_runtime() -> None:
    runtime = _runtime()
    function_source = (
        "def add(left, right):\n"
        "    return left + right\n"
        "answer = add(20, 22)\n"
    )
    assert (
        host._portapy_exec_span_impl(runtime, function_source, len(function_source))
        == base.PORTAPY_OK
    )
    answer = host._portapy_eval_span_impl(runtime, "answer", len("answer"))
    assert base._portapy_value_as_i64_impl(runtime, answer) == 42
