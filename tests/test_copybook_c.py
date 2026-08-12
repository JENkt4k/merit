import subprocess
import sys
from pathlib import Path

from merit.copybook import parse_copybook
from merit.copybook_c import generate_c_header


ROOT = Path(__file__).resolve().parents[1]
COPYBOOK = ROOT / "examples" / "copybooks" / "transfer.cpy"


def test_generated_c_header_uses_raw_bytes_and_exact_offsets():
    schema = parse_copybook(COPYBOOK.read_text(encoding="utf-8"))
    header = generate_c_header(schema, prefix="merit_legacy")
    assert "uint8_t bytes[MERIT_LEGACY_TRANSFER_RECORD_RECORD_LENGTH];" in header
    assert "#define MERIT_LEGACY_TRANSFER_RECORD_RECORD_LENGTH 21u" in header
    assert "#define MERIT_LEGACY_TRANSFER_RECORD_AMOUNT_OFFSET 6u" in header
    assert "#define MERIT_LEGACY_TRANSFER_RECORD_AMOUNT_ELEMENT_LENGTH 5u" in header
    assert "#define MERIT_LEGACY_TRANSFER_RECORD_TAG_OCCURS 2u" in header
    assert "__attribute__((packed))" not in header
    assert "#pragma pack" not in header


def test_copybook_c_cli_generates_header():
    result = subprocess.run(
        [sys.executable, "-m", "merit.copybook_c", str(COPYBOOK), "--prefix", "merit_legacy"],
        check=True, capture_output=True, text=True,
    )
    assert "MERIT_LEGACY_TRANSFER_RECORD_RECORD_LENGTH 21u" in result.stdout
