from __future__ import annotations

import builtins

import pytest

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import AsyncGeneratorObject, CoroutineObject, VirtualMachine
from portapy.parser.errors import ParseError


class Ready:
    def __await__(self):
        if False:
            yield None
        return 42


class Paused:
    def __await__(self):
        value = yield "pause"
        return value + 1


def run_source(source: str, **bindings: object) -> dict[str, object]:
    namespace: dict[str, object] = {
        "__builtins__": builtins.__dict__,
        **bindings,
    }
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_portable_async_function_returns_coroutine() -> None:
    namespace = run_source(
        "async def compute():\n"
        "    return await ready\n"
        "result = compute()\n",
        ready=Ready(),
    )
    coroutine = namespace["result"]
    assert isinstance(coroutine, CoroutineObject)
    with pytest.raises(StopIteration) as stopped:
        coroutine.send(None)
    assert stopped.value.value == 42


def test_portable_await_can_suspend_and_resume() -> None:
    namespace = run_source(
        "async def compute():\n"
        "    return await paused\n"
        "result = compute()\n",
        paused=Paused(),
    )
    coroutine = namespace["result"]
    assert isinstance(coroutine, CoroutineObject)
    assert coroutine.send(None) == "pause"
    with pytest.raises(StopIteration) as stopped:
        coroutine.send(41)
    assert stopped.value.value == 42


def test_portable_async_generator_uses_async_protocol() -> None:
    namespace = run_source(
        "async def values():\n"
        "    yield 42\n"
        "stream = values()\n"
    )
    stream = namespace["stream"]
    assert isinstance(stream, AsyncGeneratorObject)
    with pytest.raises(StopIteration) as stopped:
        next(stream.__anext__())
    assert stopped.value.value == 42


def test_portable_await_outside_async_function_is_rejected() -> None:
    with pytest.raises(ParseError, match="outside async function"):
        compile_portable_source("answer = await ready\n")
