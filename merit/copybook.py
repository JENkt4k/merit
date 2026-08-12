from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping


class CopybookError(ValueError):
    """Deterministic source/schema/codec error raised by merit-copybook."""


@dataclass(frozen=True)
class Picture:
    raw: str
    kind: str
    digits: int = 0
    scale: int = 0
    signed: bool = False
    chars: int = 0


@dataclass(frozen=True)
class CopybookField:
    level: int
    name: str
    picture: Picture
    usage: str
    occurs: int
    offset: int
    length: int
    source_line: int

    @property
    def end(self) -> int:
        return self.offset + self.length * self.occurs


@dataclass(frozen=True)
class CopybookSchema:
    name: str
    fields: tuple[CopybookField, ...]
    record_length: int

    def to_manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "record_length": self.record_length,
            "fields": [
                {
                    "level": field.level,
                    "name": field.name,
                    "picture": asdict(field.picture),
                    "usage": field.usage,
                    "occurs": field.occurs,
                    "offset": field.offset,
                    "element_length": field.length,
                    "storage_length": field.length * field.occurs,
                    "source_line": field.source_line,
                }
                for field in self.fields
            ],
        }


_LINE = re.compile(
    r"^(?P<level>\d{2})\s+(?P<name>[A-Z0-9-]+)"
    r"(?:\s+REDEFINES\s+(?P<redefines>[A-Z0-9-]+))?"
    r"(?:\s+(?:PIC|PICTURE)\s+(?P<pic>[^\s.]+))?"
    r"(?P<tail>.*?)\.$",
    re.IGNORECASE,
)
_OCCURS = re.compile(r"\bOCCURS\s+(\d+)\s+TIMES\b", re.IGNORECASE)
_DEPENDING = re.compile(r"\bOCCURS\b.*?\bDEPENDING\s+ON\b", re.IGNORECASE)
_USAGE = re.compile(
    r"\b(?:USAGE\s+(?:IS\s+)?)?"
    r"(COMP-3|PACKED-DECIMAL|COMP-5|COMP-4|COMP|BINARY|DISPLAY)\b",
    re.IGNORECASE,
)


def _logical_lines(source: str) -> list[tuple[int, str]]:
    logical: list[tuple[int, str]] = []
    pending = ""
    pending_line = 0
    for line_no, raw in enumerate(source.splitlines(), 1):
        line = raw.rstrip("\r\n")
        # Accept traditional fixed-format sequence columns without requiring them.
        if len(line) >= 7 and line[:6].strip().isdigit():
            indicator = line[6]
            if indicator in "*/":
                continue
            text = line[7:72].strip()
        else:
            text = line.strip()
            if text.startswith("*"):
                continue
        if not text:
            continue
        if not pending:
            pending_line = line_no
        pending = f"{pending} {text}".strip()
        while "." in pending:
            statement, pending = pending.split(".", 1)
            statement = statement.strip()
            if statement:
                logical.append((pending_line, statement + "."))
            pending = pending.strip()
            pending_line = line_no
    if pending:
        raise CopybookError(f"line {pending_line}: unterminated copybook entry")
    return logical


def _count_picture_atoms(fragment: str, atom: str) -> int:
    total = 0
    position = 0
    pattern = re.compile(re.escape(atom) + r"(?:\((\d+)\))?", re.IGNORECASE)
    while position < len(fragment):
        match = pattern.match(fragment, position)
        if not match:
            raise CopybookError(f"unsupported PIC fragment: {fragment!r}")
        total += int(match.group(1) or 1)
        position = match.end()
    return total


def parse_picture(raw: str) -> Picture:
    token = raw.upper().replace(" ", "")
    signed = token.startswith("S")
    if signed:
        token = token[1:]
    if token.startswith("X"):
        if signed or "V" in token:
            raise CopybookError(f"invalid alphanumeric PIC {raw!r}")
        return Picture(raw=raw.upper(), kind="text", chars=_count_picture_atoms(token, "X"))
    parts = token.split("V")
    if len(parts) > 2:
        raise CopybookError(f"unsupported PIC {raw!r}")
    integer_digits = _count_picture_atoms(parts[0], "9")
    scale = _count_picture_atoms(parts[1], "9") if len(parts) == 2 else 0
    return Picture(
        raw=raw.upper(),
        kind="numeric",
        digits=integer_digits + scale,
        scale=scale,
        signed=signed,
    )


def _storage_length(picture: Picture, usage: str) -> int:
    if picture.kind == "text":
        if usage != "DISPLAY":
            raise CopybookError(f"PIC X is only supported with DISPLAY, not {usage}")
        return picture.chars
    if usage == "DISPLAY":
        return picture.digits
    if usage == "COMP-3":
        return (picture.digits + 2) // 2
    if usage == "BINARY":
        if picture.digits <= 4:
            return 2
        if picture.digits <= 9:
            return 4
        if picture.digits <= 18:
            return 8
        raise CopybookError("BINARY numeric fields above 18 digits are unsupported")
    raise CopybookError(f"unsupported usage {usage}")


def _consume_supported_tail(tail: str, occurs: re.Match[str] | None, usage: re.Match[str] | None) -> str:
    spans = [match.span() for match in (occurs, usage) if match is not None]
    chars = list(tail)
    for start, end in spans:
        for index in range(start, end):
            chars[index] = " "
    return "".join(chars).strip()


def parse_copybook(source: str, *, name: str = "COPYBOOK") -> CopybookSchema:
    fields: list[CopybookField] = []
    seen_names: set[str] = set()
    offset = 0
    root_name = name
    for line_no, statement in _logical_lines(source):
        match = _LINE.match(statement)
        if not match:
            raise CopybookError(f"line {line_no}: unsupported copybook entry: {statement}")
        level = int(match.group("level"))
        field_name = match.group("name").upper()
        if level in (66, 77, 88):
            raise CopybookError(f"line {line_no}: level {level} is outside the v1 subset")
        if match.group("redefines"):
            raise CopybookError(f"line {line_no}: REDEFINES is outside the v1 subset")

        picture_raw = match.group("pic")
        tail = match.group("tail") or ""
        if _DEPENDING.search(tail):
            raise CopybookError(f"line {line_no}: OCCURS DEPENDING ON is outside the v1 subset")
        occurs_match = _OCCURS.search(tail)
        usage_match = _USAGE.search(tail)

        if picture_raw is None:
            if occurs_match:
                raise CopybookError(f"line {line_no}: group-level OCCURS is outside the v1 subset")
            if usage_match or tail.strip():
                raise CopybookError(f"line {line_no}: unsupported group clause: {tail.strip()}")
            if level == 1:
                root_name = field_name
            continue

        remaining = _consume_supported_tail(tail, occurs_match, usage_match)
        if remaining:
            raise CopybookError(f"line {line_no}: unsupported field clause: {remaining}")
        if field_name in seen_names:
            raise CopybookError(f"line {line_no}: duplicate leaf name {field_name}")
        seen_names.add(field_name)

        occurs = int(occurs_match.group(1)) if occurs_match else 1
        if occurs <= 0:
            raise CopybookError(f"line {line_no}: OCCURS count must be positive")
        usage = usage_match.group(1).upper() if usage_match else "DISPLAY"
        usage = {
            "PACKED-DECIMAL": "COMP-3",
            "COMP": "BINARY",
            "COMP-4": "BINARY",
            # COMP-5 is accepted only as an adapter-normalized canonical binary
            # representation. Source-platform byte order must be handled upstream.
            "COMP-5": "BINARY",
        }.get(usage, usage)
        picture = parse_picture(picture_raw)
        length = _storage_length(picture, usage)
        fields.append(
            CopybookField(
                level=level,
                name=field_name,
                picture=picture,
                usage=usage,
                occurs=occurs,
                offset=offset,
                length=length,
                source_line=line_no,
            )
        )
        offset += length * occurs

    if not fields:
        raise CopybookError("copybook contains no supported leaf fields")
    return CopybookSchema(name=root_name, fields=tuple(fields), record_length=offset)


def decode_ebcdic(data: bytes, *, codec: str = "cp037") -> str:
    try:
        return data.decode(codec)
    except (UnicodeDecodeError, LookupError) as exc:
        raise CopybookError(f"invalid EBCDIC data for {codec}: {exc}") from exc


def encode_ebcdic(text: str, *, codec: str = "cp037") -> bytes:
    try:
        return text.encode(codec)
    except (UnicodeEncodeError, LookupError) as exc:
        raise CopybookError(f"text is not representable in {codec}: {exc}") from exc


def decode_zoned(data: bytes, *, scale: int = 0, signed: bool = False) -> Decimal:
    if not data:
        raise CopybookError("zoned decimal cannot be empty")
    digits: list[int] = []
    sign = 1
    for index, byte in enumerate(data):
        digit = byte & 0x0F
        zone = byte >> 4
        if digit > 9:
            raise CopybookError(f"invalid zoned digit nibble 0x{digit:x} at byte {index}")
        if index < len(data) - 1:
            if zone != 0xF:
                raise CopybookError(f"invalid zoned prefix nibble 0x{zone:x} at byte {index}")
        elif signed:
            if zone in (0xC, 0xF):
                sign = 1
            elif zone == 0xD:
                sign = -1
            else:
                raise CopybookError(f"invalid zoned sign nibble 0x{zone:x}")
        elif zone != 0xF:
            raise CopybookError(f"unsigned zoned field has sign nibble 0x{zone:x}")
        digits.append(digit)
    unscaled = int("".join(str(digit) for digit in digits)) * sign
    return Decimal(unscaled).scaleb(-scale)


def encode_zoned(
    value: Decimal | int | str,
    *,
    digits: int,
    scale: int = 0,
    signed: bool = False,
) -> bytes:
    decimal = Decimal(value)
    quantum = Decimal(1).scaleb(-scale)
    if decimal.quantize(quantum) != decimal:
        raise CopybookError(f"{decimal} exceeds zoned scale {scale}")
    negative = decimal < 0
    if negative and not signed:
        raise CopybookError("negative value cannot be encoded in unsigned zoned field")
    unscaled = int(abs(decimal).scaleb(scale))
    text = str(unscaled)
    if len(text) > digits:
        raise CopybookError(f"{decimal} exceeds zoned precision {digits}")
    text = text.zfill(digits)
    output = bytearray(0xF0 | int(char) for char in text)
    if signed:
        output[-1] = (0xD0 if negative else 0xC0) | int(text[-1])
    return bytes(output)


def decode_comp3(
    data: bytes,
    *,
    digits: int,
    scale: int = 0,
    signed: bool = True,
) -> Decimal:
    nibbles: list[int] = []
    for byte in data:
        nibbles.extend((byte >> 4, byte & 0x0F))
    if not nibbles:
        raise CopybookError("COMP-3 field cannot be empty")
    sign_nibble = nibbles.pop()
    if sign_nibble in (0xC, 0xF):
        sign = 1
    elif sign_nibble == 0xD and signed:
        sign = -1
    else:
        raise CopybookError(f"invalid COMP-3 sign nibble 0x{sign_nibble:x}")
    while len(nibbles) > digits:
        pad = nibbles.pop(0)
        if pad != 0:
            raise CopybookError("non-zero COMP-3 pad nibble")
    if len(nibbles) != digits or any(nibble > 9 for nibble in nibbles):
        raise CopybookError("invalid COMP-3 digit payload")
    unscaled = int("".join(str(nibble) for nibble in nibbles) or "0") * sign
    return Decimal(unscaled).scaleb(-scale)


def encode_comp3(
    value: Decimal | int | str,
    *,
    digits: int,
    scale: int = 0,
    signed: bool = True,
) -> bytes:
    decimal = Decimal(value)
    quantum = Decimal(1).scaleb(-scale)
    if decimal.quantize(quantum) != decimal:
        raise CopybookError(f"{decimal} exceeds COMP-3 scale {scale}")
    negative = decimal < 0
    if negative and not signed:
        raise CopybookError("negative value cannot be encoded in unsigned COMP-3 field")
    unscaled = int(abs(decimal).scaleb(scale))
    text = str(unscaled)
    if len(text) > digits:
        raise CopybookError(f"{decimal} exceeds COMP-3 precision {digits}")
    text = text.zfill(digits)
    nibbles = [int(char) for char in text]
    nibbles.append(0xD if negative else 0xC)
    if len(nibbles) % 2:
        nibbles.insert(0, 0)
    return bytes(
        (nibbles[index] << 4) | nibbles[index + 1]
        for index in range(0, len(nibbles), 2)
    )


def decode_binary(data: bytes, *, scale: int = 0, signed: bool = False) -> Decimal:
    unscaled = int.from_bytes(data, byteorder="big", signed=signed)
    return Decimal(unscaled).scaleb(-scale)


def encode_binary(
    value: Decimal | int | str,
    *,
    length: int,
    scale: int = 0,
    signed: bool = False,
) -> bytes:
    decimal = Decimal(value)
    quantum = Decimal(1).scaleb(-scale)
    if decimal.quantize(quantum) != decimal:
        raise CopybookError(f"{decimal} exceeds binary scale {scale}")
    unscaled = int(decimal.scaleb(scale))
    try:
        return unscaled.to_bytes(length, byteorder="big", signed=signed)
    except OverflowError as exc:
        raise CopybookError(f"{decimal} exceeds {length}-byte binary storage") from exc


def _decode_element(field: CopybookField, data: bytes, *, codec: str) -> Any:
    picture = field.picture
    if picture.kind == "text":
        return decode_ebcdic(data, codec=codec).rstrip()
    if field.usage == "DISPLAY":
        return decode_zoned(data, scale=picture.scale, signed=picture.signed)
    if field.usage == "COMP-3":
        return decode_comp3(
            data,
            digits=picture.digits,
            scale=picture.scale,
            signed=picture.signed,
        )
    if field.usage == "BINARY":
        return decode_binary(data, scale=picture.scale, signed=picture.signed)
    raise CopybookError(f"unsupported usage {field.usage}")


def _encode_element(field: CopybookField, value: Any, *, codec: str) -> bytes:
    picture = field.picture
    if picture.kind == "text":
        encoded = encode_ebcdic(str(value), codec=codec)
        space = encode_ebcdic(" ", codec=codec)
        if len(encoded) > field.length:
            raise CopybookError(f"{field.name}: text exceeds PIC X({field.length})")
        return encoded + space * (field.length - len(encoded))
    if field.usage == "DISPLAY":
        return encode_zoned(
            value,
            digits=picture.digits,
            scale=picture.scale,
            signed=picture.signed,
        )
    if field.usage == "COMP-3":
        return encode_comp3(
            value,
            digits=picture.digits,
            scale=picture.scale,
            signed=picture.signed,
        )
    if field.usage == "BINARY":
        return encode_binary(
            value,
            length=field.length,
            scale=picture.scale,
            signed=picture.signed,
        )
    raise CopybookError(f"unsupported usage {field.usage}")


def decode_record(
    schema: CopybookSchema,
    data: bytes,
    *,
    codec: str = "cp037",
) -> dict[str, Any]:
    if len(data) != schema.record_length:
        raise CopybookError(
            f"record length {len(data)} != schema length {schema.record_length}"
        )
    result: dict[str, Any] = {}
    for field in schema.fields:
        values = []
        for occurrence in range(field.occurs):
            start = field.offset + occurrence * field.length
            values.append(
                _decode_element(field, data[start : start + field.length], codec=codec)
            )
        result[field.name] = values if field.occurs != 1 else values[0]
    return result


def encode_record(
    schema: CopybookSchema,
    values: Mapping[str, Any],
    *,
    codec: str = "cp037",
) -> bytes:
    output = bytearray(schema.record_length)
    expected = {field.name for field in schema.fields}
    missing = expected - set(values)
    extra = set(values) - expected
    if missing or extra:
        raise CopybookError(
            f"record keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    for field in schema.fields:
        supplied = values[field.name]
        items = supplied if field.occurs != 1 else [supplied]
        if not isinstance(items, (list, tuple)) or len(items) != field.occurs:
            raise CopybookError(f"{field.name}: expected {field.occurs} occurrence(s)")
        for occurrence, item in enumerate(items):
            encoded = _encode_element(field, item, codec=codec)
            if len(encoded) != field.length:
                raise AssertionError("codec returned an invalid storage length")
            start = field.offset + occurrence * field.length
            output[start : start + field.length] = encoded
    return bytes(output)


def _ident(name: str) -> str:
    pieces = [piece.lower() for piece in name.replace("_", "-").split("-") if piece]
    if not pieces:
        return "field"
    value = "_".join(pieces)
    return f"f_{value}" if value[0].isdigit() else value


def _type_name(name: str) -> str:
    pieces = [piece.lower() for piece in name.replace("_", "-").split("-") if piece]
    return "".join(piece[:1].upper() + piece[1:] for piece in pieces) or "CopybookRecord"


def generate_merit(
    schema: CopybookSchema,
    *,
    module: str = "copybook_generated",
) -> str:
    """Generate a public, stable canonical representation, never a raw-memory alias."""
    lines = [f"module {_ident(module)}", ""]

    # Every helper reachable through the public record must itself be public;
    # project ABI closure deliberately rejects public aggregates that leak
    # private nominal types.
    text_lengths = sorted(
        {field.picture.chars for field in schema.fields if field.picture.kind == "text"}
    )
    for length in text_lengths:
        lines.append(
            f'pub stable("copybook-text-{length}-v1") struct CopybookText{length} {{'
        )
        for index in range(length):
            lines.append(f"    b{index}: u8;")
        lines.extend(["}", ""])

    decimal_types: dict[tuple[int, int], str] = {}
    for field in schema.fields:
        picture = field.picture
        if picture.kind == "numeric" and picture.scale:
            key = (picture.digits, picture.scale)
            if key not in decimal_types:
                type_name = f"CopybookDecimal{picture.digits}S{picture.scale}"
                decimal_types[key] = type_name
                lines.extend(
                    [
                        f"pub decimal {type_name}({picture.digits}, {picture.scale}, half_even);",
                        "",
                    ]
                )

    struct_name = _type_name(schema.name)
    lines.append(
        f'pub stable("copybook-{_ident(schema.name)}-v1") struct {struct_name} {{'
    )
    for field in schema.fields:
        picture = field.picture
        if picture.kind == "text":
            merit_type = f"CopybookText{picture.chars}"
        elif picture.scale:
            merit_type = decimal_types[(picture.digits, picture.scale)]
        else:
            merit_type = "i64" if picture.signed else "u64"

        if field.occurs == 1:
            lines.append(f"    {_ident(field.name)}: {merit_type};")
        else:
            for occurrence in range(field.occurs):
                lines.append(f"    {_ident(field.name)}_{occurrence}: {merit_type};")
    lines.extend(["}", ""])
    return "\n".join(lines)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def verify_golden(
    schema: CopybookSchema,
    vectors: Iterable[Mapping[str, Any]],
    *,
    codec: str = "cp037",
) -> None:
    for index, vector in enumerate(vectors):
        values = vector["values"]
        expected_hex = str(vector["hex"]).replace(" ", "").lower()
        encoded = encode_record(schema, values, codec=codec)
        if encoded.hex() != expected_hex:
            raise CopybookError(
                f"golden {index}: encoded {encoded.hex()} != {expected_hex}"
            )
        decoded = decode_record(schema, bytes.fromhex(expected_hex), codec=codec)
        normalized = {key: _json_value(value) for key, value in decoded.items()}
        expected = {key: _json_value(value) for key, value in values.items()}
        if normalized != expected:
            raise CopybookError(
                f"golden {index}: decoded {normalized!r} != {expected!r}"
            )


def _load_schema(path: Path) -> CopybookSchema:
    return parse_copybook(path.read_text(encoding="utf-8"), name=path.stem)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="merit-copybook",
        description="Deterministic COBOL copybook migration toolkit",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser(
        "inspect", help="parse a copybook and emit its canonical manifest"
    )
    inspect.add_argument("copybook", type=Path)
    generate = sub.add_parser(
        "generate", help="generate stable canonical Merit declarations"
    )
    generate.add_argument("copybook", type=Path)
    generate.add_argument("-m", "--module", default="copybook_generated")
    verify = sub.add_parser(
        "verify", help="verify JSON golden vectors byte-for-byte and round-trip"
    )
    verify.add_argument("copybook", type=Path)
    verify.add_argument("goldens", type=Path)
    args = parser.parse_args(argv)
    try:
        schema = _load_schema(args.copybook)
        if args.command == "inspect":
            print(json.dumps(schema.to_manifest(), indent=2, sort_keys=True))
        elif args.command == "generate":
            print(generate_merit(schema, module=args.module), end="")
        else:
            payload = json.loads(args.goldens.read_text(encoding="utf-8"))
            verify_golden(schema, payload)
            print(
                f"verified {len(payload)} golden vector(s); "
                f"record_length={schema.record_length}"
            )
        return 0
    except (CopybookError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
