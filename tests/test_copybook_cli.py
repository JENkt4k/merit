import json
import subprocess
import sys
from pathlib import Path

from merit.copybook import generate_merit, parse_copybook


ROOT = Path(__file__).resolve().parents[1]
COPYBOOK = ROOT / "examples" / "copybooks" / "transfer.cpy"
GOLDEN = ROOT / "examples" / "copybooks" / "transfer.golden.json"


def test_copybook_cli_inspect_generate_and_verify():
    inspect = subprocess.run(
        [sys.executable, "-m", "merit.copybook", "inspect", str(COPYBOOK)],
        check=True, capture_output=True, text=True,
    )
    manifest = json.loads(inspect.stdout)
    assert manifest["name"] == "TRANSFER-RECORD"
    assert manifest["record_length"] == 21

    generated = subprocess.run(
        [sys.executable, "-m", "merit.copybook", "generate", str(COPYBOOK), "--module", "legacy_transfer"],
        check=True, capture_output=True, text=True,
    )
    assert "module legacy_transfer" in generated.stdout
    assert "struct TransferRecord" in generated.stdout

    verified = subprocess.run(
        [sys.executable, "-m", "merit.copybook", "verify", str(COPYBOOK), str(GOLDEN)],
        check=True, capture_output=True, text=True,
    )
    assert "verified 1 golden vector(s); record_length=21" in verified.stdout


def test_generated_copybook_declarations_pass_merit_check(tmp_path):
    schema = parse_copybook(COPYBOOK.read_text(encoding="utf-8"))
    source = generate_merit(schema, module="legacy_transfer")
    generated = tmp_path / "legacy_transfer.mrt"
    generated.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "merit.compiler", "check", str(generated)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
