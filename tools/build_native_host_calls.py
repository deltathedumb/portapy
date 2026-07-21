"""Build PortaPy's generated synchronous host-call native entry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.build_native import BuildFailure, _run, _sha256, _tool, build_native
from tools.generate_native_control_entry import generate_native_control_entry
from tools.generate_native_expression_entry import (
    generate_namespaced_scalar_entry,
    generate_native_expression_entry,
)
from tools.generate_native_function_entry import (
    generate_native_function_entry,
    rewrite_control_expression_imports,
)
from tools.generate_native_host_call_entry import generate_native_host_call_entry
from tools.generate_native_host_entry import generate_native_host_entry
from tools.nasm_exports import declare_exports
from tools.nasm_host_call_dispatch import patch_host_call_dispatch
from tools.namespace_generated_module import namespace_generated_module
from tools.native_surface import (
    DICT_GLUE_INTERNALS,
    ENVIRONMENT_GLUE_INTERNALS,
    HOST_CALL_GLUE_INTERNALS,
    LIST_GLUE_INTERNALS,
    TUPLE_GLUE_INTERNALS,
    linux_version_script,
    public_exports,
    windows_definition,
)
from tools.python_surface import PYTHON_MODULE_EXPORTS
from tools.rewrite_generated_function_stack import rewrite_generated_function
from tools.rewrite_generated_host_calls import rewrite_generated_host_calls
from tools.rewrite_generated_parser_safe import (
    rewrite_generated_control,
    rewrite_generated_expression,
    rewrite_generated_scalar,
)
from tools.rewrite_generated_public_dict import rewrite_generated_public_dict
from tools.rewrite_generated_public_list import rewrite_generated_public_list
from tools.rewrite_generated_public_tuple import rewrite_generated_public_tuple


def _compile_bridge_glue(
    *,
    gcc: str,
    target: str,
    source: Path,
    output: Path,
    log: Path,
) -> None:
    command = [
        gcc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-ffixed-rbx",
        "-I",
        str(REPOSITORY_ROOT / "include"),
        "-c",
        str(source),
        "-o",
        str(output),
    ]
    if target == "linux":
        command.insert(1, "-fPIC")
    _run(command, log=log)


def _linux_link_command(
    *,
    gcc: str,
    objects: list[str],
    version_script: Path,
    output: Path,
) -> list[str]:
    """Return a self-contained ELF shared-library link command.

    asmpython emits calls to ``pow`` for Python exponentiation. ``libportapy.so``
    must therefore declare its own libm dependency rather than relying on the
    embedding process to have loaded libm globally already.
    """
    return [
        gcc,
        "-shared",
        *objects,
        f"-Wl,--version-script={version_script}",
        "-lm",
        "-o",
        str(output),
    ]


def _upgrade_linked_artifact(
    *,
    target: str,
    output: Path,
    work_dir: Path,
) -> None:
    assembly = output.with_suffix(".asm")
    source = assembly.read_text(encoding="utf-8")
    source = patch_host_call_dispatch(source, target=target)
    source = declare_exports(
        source,
        list(
            HOST_CALL_GLUE_INTERNALS
            + ENVIRONMENT_GLUE_INTERNALS
            + TUPLE_GLUE_INTERNALS
            + DICT_GLUE_INTERNALS
            + LIST_GLUE_INTERNALS
        ),
    )
    assembly.write_text(source, encoding="utf-8")

    nasm = _tool("nasm")
    gcc = _tool("gcc")
    suffix = ".o" if target == "linux" else ".obj"
    python_object = work_dir / f"portapy-python{suffix}"
    call_object = work_dir / f"portapy-host-call-glue{suffix}"
    environment_object = work_dir / f"portapy-environment-glue{suffix}"
    environment_api_object = work_dir / f"portapy-environment-api{suffix}"
    tuple_object = work_dir / f"portapy-tuple-glue{suffix}"
    dict_object = work_dir / f"portapy-dict-glue{suffix}"
    list_object = work_dir / f"portapy-list-glue{suffix}"
    _run(
        [
            nasm,
            "-f",
            "elf64" if target == "linux" else "win64",
            "-w-label-redef-late",
            str(assembly),
            "-o",
            str(python_object),
        ],
        log=work_dir / f"{target}-host-call-nasm.log",
    )
    _compile_bridge_glue(
        gcc=gcc,
        target=target,
        source=REPOSITORY_ROOT / "native" / "host_call_glue.c",
        output=call_object,
        log=work_dir / f"{target}-host-call-glue.log",
    )
    _compile_bridge_glue(
        gcc=gcc,
        target=target,
        source=REPOSITORY_ROOT / "native" / "environment_glue.c",
        output=environment_object,
        log=work_dir / f"{target}-environment-glue.log",
    )
    _compile_bridge_glue(
        gcc=gcc,
        target=target,
        source=REPOSITORY_ROOT / "native" / "environment_api.c",
        output=environment_api_object,
        log=work_dir / f"{target}-environment-api.log",
    )
    _compile_bridge_glue(
        gcc=gcc,
        target=target,
        source=REPOSITORY_ROOT / "native" / "tuple_glue.c",
        output=tuple_object,
        log=work_dir / f"{target}-tuple-glue.log",
    )
    _compile_bridge_glue(
        gcc=gcc,
        target=target,
        source=REPOSITORY_ROOT / "native" / "dict_glue.c",
        output=dict_object,
        log=work_dir / f"{target}-dict-glue.log",
    )
    _compile_bridge_glue(
        gcc=gcc,
        target=target,
        source=REPOSITORY_ROOT / "native" / "list_glue.c",
        output=list_object,
        log=work_dir / f"{target}-list-glue.log",
    )

    objects = [
        str(python_object),
        str(work_dir / f"portapy-glue{suffix}"),
        str(work_dir / f"portapy-host-glue{suffix}"),
        str(call_object),
        str(environment_object),
        str(environment_api_object),
        str(tuple_object),
        str(dict_object),
        str(list_object),
    ]
    if target == "linux":
        version_script = work_dir / "portapy-host-calls.map"
        version_script.write_text(
            linux_version_script(host_bridge=True, host_calls=True),
            encoding="utf-8",
        )
        command = _linux_link_command(
            gcc=gcc,
            objects=objects,
            version_script=version_script,
            output=output,
        )
    else:
        definition = work_dir / "portapy-host-calls.def"
        definition.write_text(
            windows_definition(host_bridge=True, host_calls=True),
            encoding="ascii",
        )
        command = [gcc, "-shared", *objects, str(definition), "-o", str(output)]
    _run(command, log=work_dir / f"{target}-host-call-link.log")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    package = REPOSITORY_ROOT / "src" / "portapy"
    scalar_module = f"_native_api_scalar_calls_{args.target}"
    expression_module = f"_native_api_expressions_calls_{args.target}"
    control_module = f"_native_api_control_calls_{args.target}"
    function_module = f"_native_api_functions_calls_{args.target}"
    host_module = f"_native_api_host_calls_dependency_{args.target}"
    call_module = f"_native_api_host_calls_generated_{args.target}"
    scalar_source = package / f"{scalar_module}.py"
    expression_source = package / f"{expression_module}.py"
    control_source = package / f"{control_module}.py"
    function_source = package / f"{function_module}.py"
    host_source = package / f"{host_module}.py"
    call_source = package / f"{call_module}.py"
    generated = [
        scalar_source,
        expression_source,
        control_source,
        function_source,
        host_source,
        call_source,
    ]
    output = args.output.resolve()
    work_dir = args.work_dir.resolve()

    try:
        generate_namespaced_scalar_entry(scalar_source)
        rewrite_generated_scalar(scalar_source)
        generate_native_expression_entry(expression_source, scalar_module=scalar_module)
        rewrite_generated_expression(expression_source)
        namespace_generated_module(expression_source, "_expr_")
        generate_native_control_entry(
            control_source,
            expression_module=expression_module,
            scalar_module=scalar_module,
        )
        rewrite_generated_control(control_source)
        rewrite_control_expression_imports(control_source, expression_module)
        namespace_generated_module(control_source, "_ctrl_")
        generate_native_function_entry(
            function_source,
            scalar_module=scalar_module,
            expression_module=expression_module,
            control_module=control_module,
        )
        rewrite_generated_function(function_source)
        namespace_generated_module(function_source, "_fn_")
        generate_native_host_entry(
            host_source,
            scalar_module=scalar_module,
            function_module=function_module,
        )
        namespace_generated_module(host_source, "_host_")
        generate_native_host_call_entry(
            call_source,
            host_module=host_module,
            scalar_module=scalar_module,
        )
        rewrite_generated_host_calls(call_source)
        rewrite_generated_public_tuple(call_source)
        rewrite_generated_public_dict(call_source)
        rewrite_generated_public_list(call_source)

        metadata = build_native(
            target=args.target,
            output=output,
            source=call_source,
            work_dir=work_dir,
            host_bridge=True,
        )
        _upgrade_linked_artifact(
            target=args.target,
            output=output,
            work_dir=work_dir,
        )
    except (BuildFailure, ValueError) as error:
        print(f"portapy native host-call build failed: {error}", file=sys.stderr)
        return 1
    finally:
        for path in generated:
            path.unlink(missing_ok=True)

    metadata["size"] = output.stat().st_size
    metadata["sha256"] = _sha256(output)
    metadata["host_calls"] = True
    metadata["native_environment_adapter"] = True
    metadata["public_environment_api"] = True
    metadata["public_tuple_abi"] = True
    metadata["public_dict_abi"] = True
    metadata["public_list_abi"] = True
    metadata["generated_host_call_entry"] = True
    metadata["native_safe_host_call_rewrite"] = True
    metadata["host_call_glue_reserves_rbx"] = True
    metadata["public_exports"] = list(
        public_exports(host_bridge=True, host_calls=True)
    )
    metadata["python_module_exports"] = list(PYTHON_MODULE_EXPORTS)
    metadata["python_module_entry"] = "portapy"
    metadata["bridge_sources"] = [
        "native/environment_api.c",
        "native/environment_glue.c",
        "native/host_call_glue.c",
    ]
    metadata["semantic_sources"] = [
        "src/portapy/native_api.py",
        "src/portapy/native_api_typed.py",
        "src/portapy/native_api_scalar.py",
        "src/portapy/native_api_boolean.py",
        "src/portapy/native_api_control.py",
        "src/portapy/native_api_functions.py",
        "src/portapy/native_api_host.py",
        "src/portapy/native_api_host_calls.py",
        "src/portapy/native_api_environment.py",
        "tools/rewrite_generated_tuple.py",
        "tools/rewrite_generated_dict.py",
        "tools/rewrite_generated_list.py",
        "tools/rewrite_generated_public_tuple.py",
        "tools/rewrite_generated_public_dict.py",
        "tools/rewrite_generated_public_list.py",
    ]
    metadata_path = output.with_suffix(output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
