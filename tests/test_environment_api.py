from __future__ import annotations

import math
from types import ModuleType, SimpleNamespace

import pytest

import portapy


def test_new_add_modules_expose_execute_and_snapshot() -> None:
    somnia_env = ModuleType("somnia.env")
    somnia_env.game = SimpleNamespace(
        provider=SimpleNamespace(HttpProvider="http-provider")
    )

    environment = portapy.new()
    environment.add_modules(math)
    environment.expose(somnia_env)
    environment.execute(
        """
http_service = game.provider.HttpProvider
root = math.sqrt(81)
label = "before"
"""
    )

    assert environment.get("http_service") == "http-provider"
    assert environment.get("root") == 9.0

    snapshot = environment.snapshot()
    assert snapshot.var["http_service"] == "http-provider"
    assert snapshot["root"] == 9.0
    assert snapshot.get("missing", 42) == 42
    with pytest.raises(TypeError):
        snapshot.var["label"] = "mutated"  # type: ignore[index]

    environment.execute('label = "after"\nnew_value = 42\n')
    assert environment.get("label") == "after"
    assert environment.get("new_value") == 42
    assert snapshot.var["label"] == "before"

    snapshot.restore()
    assert environment.get("label") == "before"
    with pytest.raises(portapy.ExecutionError):
        environment.get("new_value")


def test_add_modules_uses_leaf_module_name() -> None:
    module = ModuleType("package.helpers")
    module.answer = 42

    environment = portapy.new().add_modules(module)
    environment.execute("result = helpers.answer\n")

    assert environment.get("result") == 42


def test_expose_supports_mappings_and_add_builtin_alias() -> None:
    environment = portapy.new()
    environment.expose({"game": SimpleNamespace(name="Somnia")})
    environment.add_builtin({"engine_version": "3.14"})
    environment.execute("name = game.name\nversion = engine_version\n")

    assert environment.get("name") == "Somnia"
    assert environment.get("version") == "3.14"


def test_binding_collisions_require_explicit_replace() -> None:
    environment = portapy.new().set("value", 1)

    with pytest.raises(portapy.BindingError):
        environment.set("value", 2, replace=False)

    environment.set("value", 2)
    assert environment.get("value") == 2


def test_snapshot_is_shallow_for_host_objects() -> None:
    host = SimpleNamespace(value=1)
    environment = portapy.new().set("host", host)
    snapshot = environment.snapshot()

    host.value = 2
    snapshot.restore()

    assert environment.get("host") is host
    assert environment.get("host").value == 2


def test_evaluate_returns_unboxed_values() -> None:
    environment = portapy.new().set("value", 40)
    assert environment.evaluate("value + 2") == 42


def test_environment_context_manager_closes_runtime() -> None:
    with portapy.new() as environment:
        environment.execute("value = 1\n")
        assert environment.get("value") == 1

    with pytest.raises(portapy.EnvironmentClosedError):
        environment.execute("value = 2\n")
