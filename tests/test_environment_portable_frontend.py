from __future__ import annotations

from portapy import new


def test_public_environment_uses_standalone_frontend_end_to_end() -> None:
    def host_offset(value: int) -> int:
        return value + 2

    environment = new().add(host_offset)
    environment.execute(
        "class Counter:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "    def read(self):\n"
        "        return self.value\n"
        "def make_counter(start):\n"
        "    value = start\n"
        "    def step():\n"
        "        nonlocal value\n"
        "        value = host_offset(value)\n"
        "        return value\n"
        "    return step\n"
        "counter = make_counter(38)\n"
        "boxed = Counter(counter())\n"
    )
    assert environment.evaluate("boxed.read() + 2") == 42
    environment.close()


def test_public_environment_keeps_state_between_execute_calls() -> None:
    environment = new()
    environment.execute("value = 20\n")
    environment.execute("value = value + 22\n")
    assert environment.get("value") == 42
    environment.close()
