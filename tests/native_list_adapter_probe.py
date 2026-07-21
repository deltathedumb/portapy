from __future__ import annotations

from pathlib import Path
import sys

from portapy import import_binary


def list_roundtrip(value: list[object]) -> list[object]:
    assert value == [18, [1, 2], 24]
    return [value[-1], value[1], value[0] + 24]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_list_adapter_probe.py <library>")

    module = import_binary(Path(sys.argv[1]))
    with module.new() as environment:
        environment.expose({"list_roundtrip": list_roundtrip})
        environment.set("input_list", [18, [1, 2], 24])
        environment.execute(
            "list_first = input_list[0]\n"
            "list_size = len(input_list)\n"
            "list_result = list_roundtrip(input_list)\n"
            "input_list[0] = 20\n"
            "input_list.append(22)\n"
        )

        snapshot = environment.snapshot()
        assert snapshot.var["input_list"] == [20, [1, 2], 24, 22]
        assert snapshot.var["list_first"] == 18
        assert snapshot.var["list_size"] == 3
        assert snapshot.var["list_result"] == [24, [1, 2], 42]

        environment.set("input_list", [99])
        assert environment.get("input_list") == [99]
        snapshot.restore()
        assert environment.get("input_list") == [20, [1, 2], 24, 22]

    print("native-list-adapter: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
