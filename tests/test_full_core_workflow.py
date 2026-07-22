from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "native-full-core-probe.yml"


def test_full_core_workflow_runs_complete_normalizer_once_per_platform() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert source.count("python tools/normalize_full_core_validation.py") == 2
    for obsolete_command in (
        "python tools/normalize_full_core_probe.py",
        "python tools/normalize_full_core_lambdas.py",
        "python tools/normalize_full_core_native_semantics.py",
        "python tools/normalize_full_core_opcode_maps.py",
    ):
        assert obsolete_command not in source
