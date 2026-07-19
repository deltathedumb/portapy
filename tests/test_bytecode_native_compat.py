from __future__ import annotations

from portapy.core.bytecode import CodeObject, Instruction, Op


def test_opcode_value_and_validation_remain_exact() -> None:
    instruction = Instruction(Op.BINARY_ADD, 0)
    assert instruction.op.value == 10
    code = CodeObject(
        name="probe",
        instructions=[Instruction(Op.LOAD_CONST, 0), Instruction(Op.RETURN, 0)],
        constants=[42],
    )
    code.validate()


def test_explicit_replace_preserves_unchanged_fields() -> None:
    original = CodeObject(
        name="original",
        instructions=[Instruction(Op.RETURN, 0)],
        constants=[1],
        names=["value"],
        arg_names=["arg"],
        kwonly_names=["kw"],
        vararg_name="args",
        kwarg_name="kwargs",
        posonly_names=["pos"],
        is_generator=True,
        is_coroutine=True,
        free_names=["free"],
        interactive=True,
        is_async_generator=True,
    )
    changed = original.replace(name="changed", constants=[2])
    assert changed.name == "changed"
    assert changed.constants == [2]
    assert changed.instructions == original.instructions
    assert changed.names == original.names
    assert changed.arg_names == original.arg_names
    assert changed.kwonly_names == original.kwonly_names
    assert changed.vararg_name == original.vararg_name
    assert changed.kwarg_name == original.kwarg_name
    assert changed.posonly_names == original.posonly_names
    assert changed.is_generator is True
    assert changed.is_coroutine is True
    assert changed.free_names == original.free_names
    assert changed.interactive is True
    assert changed.is_async_generator is True
