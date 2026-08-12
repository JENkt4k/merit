from decimal import Decimal

import pytest

from merit.copybook import (
    CopybookError,
    decode_comp3,
    decode_record,
    decode_zoned,
    encode_comp3,
    encode_record,
    encode_zoned,
    generate_merit,
    parse_copybook,
    verify_golden,
)


COPYBOOK = """
       01 TRANSFER-RECORD.
          05 ACCOUNT-ID PIC 9(6).
          05 AMOUNT PIC S9(7)V99 COMP-3.
          05 STATUS PIC X(2).
          05 SEQUENCE PIC 9(4) COMP.
          05 TAG PIC X(3) OCCURS 2 TIMES.
"""


def test_parse_copybook_layout_is_byte_exact():
    schema = parse_copybook(COPYBOOK)
    assert schema.name == "TRANSFER-RECORD"
    assert schema.record_length == 21
    assert [(f.name, f.offset, f.length, f.occurs, f.usage) for f in schema.fields] == [
        ("ACCOUNT-ID", 0, 6, 1, "DISPLAY"),
        ("AMOUNT", 6, 5, 1, "COMP-3"),
        ("STATUS", 11, 2, 1, "DISPLAY"),
        ("SEQUENCE", 13, 2, 1, "BINARY"),
        ("TAG", 15, 3, 2, "DISPLAY"),
    ]


def test_zoned_decimal_known_vectors():
    assert encode_zoned("123.45", digits=5, scale=2, signed=True) == bytes.fromhex("f1f2f3f4c5")
    assert decode_zoned(bytes.fromhex("f1f2f3f4c5"), scale=2, signed=True) == Decimal("123.45")
    assert encode_zoned("-123.45", digits=5, scale=2, signed=True) == bytes.fromhex("f1f2f3f4d5")
    assert decode_zoned(bytes.fromhex("f1f2f3f4d5"), scale=2, signed=True) == Decimal("-123.45")


def test_comp3_known_vectors_and_scale_guard():
    assert encode_comp3("125.50", digits=9, scale=2, signed=True) == bytes.fromhex("000012550c")
    assert decode_comp3(bytes.fromhex("000012550c"), digits=9, scale=2, signed=True) == Decimal("125.50")
    assert encode_comp3("-1.25", digits=9, scale=2, signed=True) == bytes.fromhex("000000125d")
    with pytest.raises(CopybookError, match="scale"):
        encode_comp3("1.234", digits=9, scale=2, signed=True)


def test_full_record_matches_external_style_golden_bytes_and_round_trips():
    schema = parse_copybook(COPYBOOK)
    values = {
        "ACCOUNT-ID": "123456",
        "AMOUNT": "125.50",
        "STATUS": "OK",
        "SEQUENCE": "41",
        "TAG": ["ACH", "USD"],
    }
    expected = bytes.fromhex(
        "f1f2f3f4f5f6"  # DISPLAY numeric
        "000012550c"    # COMP-3 125.50
        "d6d2"          # CP037 'OK'
        "0029"          # COMP/BINARY 41
        "c1c3c8"        # CP037 'ACH'
        "e4e2c4"        # CP037 'USD'
    )
    assert encode_record(schema, values) == expected
    decoded = decode_record(schema, expected)
    assert decoded == {
        "ACCOUNT-ID": Decimal("123456"),
        "AMOUNT": Decimal("125.50"),
        "STATUS": "OK",
        "SEQUENCE": Decimal("41"),
        "TAG": ["ACH", "USD"],
    }
    verify_golden(schema, [{"values": values, "hex": expected.hex()}])


def test_generated_merit_is_stable_canonical_not_raw_cobol_memory():
    generated = generate_merit(parse_copybook(COPYBOOK), module="legacy_transfer")
    assert "module legacy_transfer" in generated
    assert 'stable("copybook-text-2-v1") struct CopybookText2' in generated
    assert 'stable("copybook-text-3-v1") struct CopybookText3' in generated
    assert "decimal CopybookDecimal9S2(9, 2, half_even);" in generated
    assert 'pub stable("copybook-transfer_record-v1") struct TransferRecord' in generated
    assert "amount: CopybookDecimal9S2;" in generated
    assert "tag_0: CopybookText3;" in generated
    assert "tag_1: CopybookText3;" in generated


def test_unsupported_dynamic_or_overlay_constructs_fail_closed():
    with pytest.raises(CopybookError, match="REDEFINES"):
        parse_copybook("01 R. 05 A PIC X(4). 05 B REDEFINES A PIC 9(4).")
    with pytest.raises(CopybookError, match="OCCURS DEPENDING"):
        parse_copybook("01 R. 05 A PIC 9 OCCURS 2 TIMES OCCURS DEPENDING ON N.")
