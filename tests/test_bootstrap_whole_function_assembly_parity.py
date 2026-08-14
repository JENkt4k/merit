from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from merit.bootstrap.mir_contract import canonical_mir_json
from merit.bootstrap.mir_function_assembly_parity import lower_native_whole_function_assembly
from merit.bootstrap.mir_to_c import emit_c_module


SOURCE = "module demo\nfn compute()->i64 requires_caps [clock] requires true ensures true { if 1 { return 7; } return 9; }\n"


def _span(text: str) -> tuple[int, int]:
    start = SOURCE.index(text)
    return start, len(text)


def _records():
    fn_start, fn_len = _span("compute")
    true_start, true_len = _span("true")
    one_start, one_len = _span("1")
    seven_start, seven_len = _span("7")
    nine_start, nine_len = _span("9")

    header = (1, fn_start, fn_len, 0, -1, -1, -1, fn_start, fn_len, 0, 1, 0, -1, 0, -1, 0)
    body = (
        header,
        (3, 0, 0, 0, -1, -1, -1, -1, 0, 0, 2, 0, -1, 0, 0, 0),
        (3, 0, 0, 1, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 1, 1),
        (3, 0, 0, 2, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 2, 2),
        (4, one_start, one_len, 0, 0, -1, -1, -1, 0, 0, 2, 0, -1, 0, 0, 0),
        (4, seven_start, seven_len, 1, 1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 1, 1),
        (4, nine_start, nine_len, 2, 2, -1, -1, -1, 0, 0, 1, 0, -1, 0, 2, 2),
    )
    contracts = (
        (2, 0, 1, true_start, true_len, 0, 0, -1, -1, 0, 2, 1),
        (4, 0, 1, true_start, true_len, 1, -1, 0, -1, 0, 2, 0),
        (2, 1, 2, true_start, true_len, 2, 1, -1, -1, 0, 2, 1),
        (4, 1, 2, true_start, true_len, 3, -1, 1, -1, 0, 2, 0),
    )
    contract_locals = (
        (3, 0, 2, 1, 0),
        (4, 1, 2, 2, 1),
    )
    sources = (
        (0, 1, 0, 1, 0, 3, -1, -1),
        (1, 1, 1, 1, 0, -1, 3, -1),
        (2, 2, 0, 0, -1, -1, -1, -1),
        (3, 2, 1, 0, -1, -1, -1, -1),
        (4, 1, 2, 2, 1, 4, -1, -1),
        (5, 1, 3, 2, 1, -1, 4, -1),
        (6, 2, 2, 0, -1, -1, -1, -1),
        (7, 1, 2, 2, 1, 4, -1, -1),
        (8, 1, 3, 2, 1, -1, 4, -1),
    )
    cfg = (
        (10, 0, -1, -1, -1, 0, 0),
        (10, 1, -1, -1, -1, 0, 1),
        (10, 2, -1, -1, -1, 0, 2),
        (10, 3, -1, -1, -1, 0, 3),
        (12, 0, 0, 1, 2, 0, 0),
        (15, 1, 1, -1, -1, 0, 0),
        (11, 2, -1, 3, -1, 0, 0),
        (15, 3, 2, -1, -1, 0, 0),
    )
    placements = (
        (0, 0, 0), (0, 1, 1), (0, 2, 2),
        (1, 3, 0), (1, 4, 1), (1, 5, 2),
        (3, 6, 0), (3, 7, 1), (3, 8, 2),
    )
    return body, contracts, contract_locals, sources, cfg, placements


def _module():
    body, contracts, contract_locals, sources, cfg, placements = _records()
    return lower_native_whole_function_assembly(
        source=SOURCE,
        module_name="demo",
        body_records=body,
        contract_records=contracts,
        contract_locals=contract_locals,
        instruction_sources=sources,
        cfg_records=cfg,
        placements=placements,
        capability_ids=(9,),
        capability_names={9: "clock"},
    )


def test_native_assembly_materializes_canonical_contract_cfg():
    module = _module()
    function = module.functions[0]
    assert function.name == "compute"
    assert function.capabilities == ("clock",)
    assert [block.block_id for block in function.blocks] == [0, 1, 2, 3]
    assert [instruction.instruction_id for block in function.blocks for instruction in block.instructions] == list(range(9))
    assert [instruction.contract_kind for instruction in function.blocks[0].instructions[:2]] == ["none", "precondition"]
    assert [instruction.contract_kind for instruction in function.blocks[1].instructions[-2:]] == ["none", "postcondition"]
    assert [instruction.contract_kind for instruction in function.blocks[3].instructions[-2:]] == ["none", "postcondition"]
    assert function.blocks[0].terminator.kind == "branch"
    assert function.blocks[1].terminator.kind == "return"
    assert function.blocks[2].terminator.kind == "jump"
    assert function.blocks[3].terminator.kind == "return"
    data = canonical_mir_json(module)
    assert '\"capabilities\":[\"clock\"]' in data
    assert data.count('\"contract_kind\":\"postcondition\"') == 2


def test_canonical_assembled_mir_emits_and_executes_c(tmp_path: Path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("system C compiler is unavailable")
    c_source = emit_c_module(_module()) + "\n#include <stdio.h>\nint main(void){ printf(\"%lld\\n\", (long long)compute()); return 0; }\n"
    c_path = tmp_path / "whole_function.c"
    executable = tmp_path / "whole_function"
    c_path.write_text(c_source, encoding="utf-8")
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-O2", str(c_path), "-o", str(executable)], check=True, text=True, capture_output=True)
    completed = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert completed.stdout.strip() == "7"


def test_assembly_rejects_unresolved_capability_identity():
    body, contracts, contract_locals, sources, cfg, placements = _records()
    with pytest.raises(ValueError, match="unresolved capability identity 9"):
        lower_native_whole_function_assembly(
            source=SOURCE,
            module_name="demo",
            body_records=body,
            contract_records=contracts,
            contract_locals=contract_locals,
            instruction_sources=sources,
            cfg_records=cfg,
            placements=placements,
            capability_ids=(9,),
            capability_names={},
        )
