from __future__ import annotations

from pathlib import Path
import sys
import traceback

from portapy import import_binary


def list_roundtrip(value: list[object]) -> list[object]:
    assert value == [18, [1, 2], 24]
    return [value[-1], value[1], value[0] + 24]


def run(library: Path) -> None:
    print("stage:load", flush=True)
    module = import_binary(library)
    with module.new() as environment:
        print("stage:expose", flush=True)
        environment.expose({"list_roundtrip": list_roundtrip})
        print("stage:set", flush=True)
        environment.set("input_list", [18, [1, 2], 24])
        print("stage:execute", flush=True)
        environment.execute(
            "list_first = input_list[0]\n"
            "list_size = len(input_list)\n"
            "list_result = list_roundtrip(input_list)\n"
        )

        print("stage:snapshot", flush=True)
        snapshot = environment.snapshot()
        assert snapshot.var["input_list"] == [18, [1, 2], 24]
        assert snapshot.var["list_first"] == 18
        assert snapshot.var["list_size"] == 3
        assert snapshot.var["list_result"] == [24, [1, 2], 42]

        print("stage:restore", flush=True)
        environment.set("input_list", [99])
        assert environment.get("input_list") == [99]
        snapshot.restore()
        assert environment.get("input_list") == [18, [1, 2], 24]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_list_adapter_probe.py <library>")
    try:
        run(Path(sys.argv[1]))
    except BaseException:
        traceback.print_exc(file=sys.stdout)
        return 1
    print("native-list-adapter: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
