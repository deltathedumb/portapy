from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import portapy


class HttpProvider:
    pass


def test_environment_injection_execution_and_snapshot() -> None:
    somnia_env = SimpleNamespace(
        game=SimpleNamespace(
            provider=SimpleNamespace(HttpProvider=HttpProvider),
        ),
        hidden_value=41,
    )

    environment = portapy.new()
    environment.add_modules(math)
    environment.expose(somnia_env)
    environment.execute(
        """
http_provider = game.provider.HttpProvider
answer = hidden_value + 1
root = math.sqrt(81)
"""
    )

    snapshot = environment.snapshot()
    assert snapshot.var["http_provider"] is HttpProvider
    assert snapshot.var["answer"] == 42
    assert snapshot.var["root"] == 9.0
    assert snapshot["math"] is math


def test_expose_accepts_mappings_and_selected_names() -> None:
    environment = portapy.new()
    environment.expose({"seed": 41, "unused": 99}, names=["seed"])
    environment.execute("answer = seed + 1")

    snapshot = environment.snapshot()
    assert snapshot.var["answer"] == 42
    assert "unused" not in snapshot.var


def test_snapshot_is_detached_and_read_only() -> None:
    environment = portapy.new()
    environment.expose({"value": 1})
    first = environment.snapshot()

    environment.expose({"value": 2})
    second = environment.snapshot()

    assert first.var["value"] == 1
    assert second.var["value"] == 2
    with pytest.raises(TypeError):
        first.var["value"] = 3  # type: ignore[index]


def test_evaluate_returns_a_host_value() -> None:
    environment = portapy.new()
    environment.expose({"seed": 6})
    assert environment.evaluate("seed * 7") == 42


def test_execution_failure_raises_structured_exception() -> None:
    environment = portapy.new()

    with pytest.raises(portapy.PortaPyExecutionError) as caught:
        environment.execute("broken =")

    assert caught.value.info is not None
    assert caught.value.info.status is portapy.Status.COMPILE_ERROR


def test_environment_context_manager_closes_runtime() -> None:
    with portapy.new() as environment:
        environment.execute("answer = 42")

    with pytest.raises(portapy.PortaPyExecutionError):
        environment.snapshot()
