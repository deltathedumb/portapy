from __future__ import annotations

from pathlib import Path

from tools.build_native_host_calls import _linux_link_command


def test_linux_shared_library_links_its_math_dependency() -> None:
    command = _linux_link_command(
        gcc="gcc",
        objects=["runtime.o", "glue.o"],
        version_script=Path("portapy.map"),
        output=Path("libportapy.so"),
    )

    assert command == [
        "gcc",
        "-shared",
        "runtime.o",
        "glue.o",
        "-Wl,--version-script=portapy.map",
        "-lm",
        "-o",
        "libportapy.so",
    ]
