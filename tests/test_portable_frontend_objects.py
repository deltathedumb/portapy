from __future__ import annotations

import builtins
import importlib

import pytest

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {
        "__builtins__": builtins.__dict__,
        "__pyinbin_import__": importlib.import_module,
    }
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_portable_classes_defaults_keywords_and_inheritance() -> None:
    namespace = run_source(
        "class Base:\n"
        "    scale = 2\n"
        "    def base(self):\n"
        "        return 20\n"
        "class Child(Base):\n"
        "    def __init__(self, value=1):\n"
        "        self.value = value\n"
        "    def answer(self):\n"
        "        return (self.base() + self.value) * self.scale\n"
        "item = Child(value=1)\n"
        "answer = item.answer()\n"
    )
    assert namespace["answer"] == 42
    assert namespace["item"].value == 1


def test_portable_slices_destructuring_and_deletion() -> None:
    namespace = run_source(
        "items = [1, 2, 3, 4]\n"
        "middle = items[1:3]\n"
        "items[1:3] = [20, 30]\n"
        "first, *rest = items\n"
        "left = 20\n"
        "right = 22\n"
        "left, right = right, left\n"
        "same_a = same_b = 42\n"
        "del items[1]\n"
        "mapping = {'answer': 42, 'drop': 0}\n"
        "del mapping['drop']\n"
    )
    assert namespace["middle"] == [2, 3]
    assert namespace["first"] == 1
    assert namespace["rest"] == [30, 4]
    assert (namespace["left"], namespace["right"]) == (22, 20)
    assert namespace["same_a"] == namespace["same_b"] == 42
    assert namespace["items"] == [1, 30, 4]
    assert namespace["mapping"] == {"answer": 42}


def test_portable_lambda_fstring_walrus_and_global() -> None:
    namespace = run_source(
        "answer = 0\n"
        "def update():\n"
        "    global answer\n"
        "    answer = 42\n"
        "update()\n"
        "double = lambda value: value * 2\n"
        "result = (captured := double(21))\n"
        "text = f'answer={captured}'\n"
    )
    assert namespace["answer"] == 42
    assert namespace["result"] == 42
    assert namespace["captured"] == 42
    assert namespace["text"] == "answer=42"


def test_portable_imports_use_host_loader() -> None:
    namespace = run_source(
        "import math as mathematics\n"
        "from math import sqrt as root\n"
        "answer = mathematics.floor(root(1764))\n"
    )
    assert namespace["answer"] == 42


def test_portable_with_calls_enter_and_exit() -> None:
    namespace = run_source(
        "class Resource:\n"
        "    def __init__(self):\n"
        "        self.closed = False\n"
        "    def __enter__(self):\n"
        "        return 42\n"
        "    def __exit__(self, exc_type, exc_value, traceback):\n"
        "        self.closed = True\n"
        "resource = Resource()\n"
        "with resource as answer:\n"
        "    copied = answer\n"
        "closed = resource.closed\n"
    )
    assert namespace["copied"] == 42
    assert namespace["closed"] is True


def test_portable_raise_uses_vm_exception_semantics() -> None:
    with pytest.raises(ValueError, match="portable"):
        run_source("raise ValueError('portable')\n")
