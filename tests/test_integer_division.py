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


@pytest.mark.parametrize(
    ('type_name','left','operator','right','interpreter_error','native_error'),
    [
        ('i8','127','+','1','integer overflow in i8','i8 addition overflow'),
        ('u8','0','-','1','integer overflow in u8','u8 subtraction overflow'),
        ('i32','50000','*','50000','integer overflow in i32','i32 multiplication overflow'),
        ('u64','18446744073709551615','+','1','integer overflow in u64','u64 addition overflow'),
    ],
)
def test_primitive_arithmetic_overflow_matches_native(tmp_path,type_name,left,operator,right,interpreter_error,native_error):
    source=f'''module primitive_overflow
fn main()->i32 {{ let left:{type_name}={left}; let right:{type_name}={right}; print(left{operator}right); return 0; }}'''
    program=parse(source);Checker(program).check()
    with pytest.raises(RuntimeError,match=interpreter_error):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,f'{type_name}_overflow'))],text=True,capture_output=True)
    assert native.returncode == 70
    assert native_error in native.stderr


def test_narrow_integer_arithmetic_success_matches_native(tmp_path):
    source='module narrow_arithmetic\nfn main()->i32 { let left:i8=120; let right:i8=7; print(left+right); return 0; }'
    program=parse(source);Checker(program).check();interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'narrow_arithmetic'))],check=True,text=True,capture_output=True).stdout
    assert interpreted.getvalue() == native == '127\n'


def test_decimal_operator_multiplication_uses_declared_rounding(tmp_path):
    source='''module decimal_operator_rounding
decimal Money(6,2,half_up);
fn main()->i32 { let left:Money=1.25; let right:Money=1.25; print(left*right); return 0; }'''
    program=parse(source);Checker(program).check();interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'decimal_operator_rounding'))],check=True,text=True,capture_output=True).stdout
    assert interpreted.getvalue() == native == '1.56\n'


def test_bounded_operator_overflow_matches_native(tmp_path):
    source='''module bounded_operator_overflow
bounded Count(i32,0,10);
fn main()->i32 { let left:Count=8; let right:Count=5; print(left+right); return 0; }'''
    program=parse(source);Checker(program).check()
    with pytest.raises(RuntimeError,match='bounded overflow in Count'):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'bounded_operator_overflow'))],text=True,capture_output=True)
    assert native.returncode == 70
    assert 'bounded range violation: Count' in native.stderr


def test_checked_builtin_uses_narrow_type_overflow_policy(tmp_path):
    source='module checked_narrow_overflow\nfn main()->i32 { let left:i8=127; let right:i8=1; print(checked_add(left,right)); return 0; }'
    program=parse(source);Checker(program).check()
    with pytest.raises(RuntimeError,match='integer overflow in i8'):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'checked_narrow_overflow'))],text=True,capture_output=True)
    assert native.returncode == 70
    assert 'i8 addition overflow' in native.stderr


def test_decimal_comparison_uses_operand_type_when_stored_as_i32(tmp_path):
    source='''module decimal_comparison
decimal Money(6,2,half_even);
fn main()->i32 { let value:Money=1.25; let greater:i32=value>1.20; print(greater); return 0; }'''
    program=parse(source);Checker(program).check();interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    native=subprocess.run([str(compile_program(source,tmp_path,'decimal_comparison'))],check=True,text=True,capture_output=True).stdout
    assert interpreted.getvalue() == native == '1\n'
