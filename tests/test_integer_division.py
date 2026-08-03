import contextlib
import io
import subprocess

import pytest

from merit.compiler import Checker, Interpreter, compile_file, parse


def compile_program(source,tmp_path,name):
    path=tmp_path/f'{name}.mrt';executable=tmp_path/name
    path.write_text(source);compile_file(path,executable)
    return executable


def test_negative_integer_division_truncates_toward_zero_in_both_runtimes(tmp_path):
    source='''module signed_division
fn main()->i32 { let negative:i64=-7; let positive:i64=7; let divisor:i64=3; print(negative/divisor); print(positive/-3); print(negative/-3); return 0; }'''
    program=parse(source);Checker(program).check()
    interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'signed_division'))],check=True,text=True,capture_output=True).stdout
    assert interpreted.getvalue() == native == '-2\n-2\n2\n'


def test_integer_division_by_zero_fails_deterministically(tmp_path):
    source='module zero_division\nfn main()->i32 { let value:i64=7; let zero:i64=0; print(value/zero); return 0; }'
    program=parse(source);Checker(program).check()
    with pytest.raises(RuntimeError,match='division by zero'):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'zero_division'))],text=True,capture_output=True)
    assert native.returncode == 72
    assert 'Merit division by zero' in native.stderr


def test_integer_division_overflow_fails_deterministically(tmp_path):
    source='module division_overflow\nfn main()->i32 { let minimum:i64=-9223372036854775808; let negative_one:i64=-1; print(minimum/negative_one); return 0; }'
    program=parse(source);Checker(program).check()
    with pytest.raises(RuntimeError,match='integer overflow in i64'):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'division_overflow'))],text=True,capture_output=True)
    assert native.returncode == 70
    assert 'Merit division overflow' in native.stderr
