import contextlib
import io
import json
import subprocess
from pathlib import Path

from merit.compiler import CGenerator, Checker, Interpreter, compile_file, parse


VALUE = 'what??! nul:\u0000 control:\u0001 quote:" slash:\\ utf8:é 😀'


def _source(value: str) -> str:
    return (
        "module c_string_encoding\n"
        f"fn main()->i32 {{ print({json.dumps(value, ensure_ascii=False)}); return 0; }}\n"
    )


def test_c_string_literals_are_emitted_as_explicit_utf8_bytes():
    program = parse(_source(VALUE))
    Checker(program).check()
    generated = CGenerator(program).generate()
    encoded = VALUE.encode("utf-8")
    literal = '"' + "".join(f"\\{byte:03o}" for byte in encoded) + '"'
    assert f"(merit_String){{{literal}, {len(encoded)}}}" in generated
    assert "??!" not in generated
    assert "\\u0000" not in generated
    assert "\\ud83d" not in generated


def test_c_string_bytes_match_interpreter_and_native(tmp_path: Path):
    source_text = _source(VALUE)
    source = tmp_path / "c_string_encoding.mrt"
    source.write_text(source_text, encoding="utf-8")
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(parse(source_text)).run()
    _, _, _, executable = compile_file(source, tmp_path / "c_string_encoding")
    native = subprocess.run(
        [str(executable)], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout
    assert native == interpreted.getvalue() == VALUE + "\n"
