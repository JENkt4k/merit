import contextlib
import io
import subprocess

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, compile_file, mir, parse


ORDER_MATRIX = '''module ordered_expression_matrix
stable("counter-v1") struct Counter { value:i32; }
struct Pair { left:i32; right:i32; }
fn tick(borrow_mut counter:Counter,delta:i32)->i32 { counter.value=counter.value+delta; return counter.value; }
fn combine(left:i32,right:i32)->i32 { return left*100+right; }
fn mark(borrow_mut counter:Counter,value:String)->String { counter.value=counter.value+1; return value; }
fn index(borrow_mut counter:Counter)->i64 { counter.value=counter.value*10; return 0; }
fn advance(borrow_mut counter:Counter)->i32 { counter.value=counter.value+1; return counter.value<3; }
fn main()->i32 {
    var counter:Counter=Counter{value:0};
    print(combine(tick(counter,1),tick(counter,10)));
    counter.value=0;
    let pair:Pair=Pair{left:tick(counter,2),right:tick(counter,20)};
    print(pair.left); print(pair.right);
    counter.value=0;
    print(tick(counter,3)*100+tick(counter,30));
    counter.value=0;
    print(string_byte(mark(counter,"A"),index(counter))); print(counter.value);
    counter.value=0;
    while advance(counter) { print(counter.value); }
    print(counter.value);
    return 0;
}'''


def test_nested_expressions_evaluate_once_left_to_right_in_both_backends(tmp_path):
    program=parse(ORDER_MATRIX);Checker(program).check()
    interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    source=tmp_path/'ordered.mrt';source.write_text(ORDER_MATRIX)
    _,c_path,_,executable=compile_file(source,tmp_path/'ordered')
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    expected='111\n2\n22\n333\n65\n10\n1\n2\n3\n'
    assert interpreted.getvalue() == native == expected
    generated=c_path.read_text()
    assert generated.count('= merit_tick(') == 6
    assert 'while (1) {' in generated
    assert generated.index('= merit_mark(') < generated.index('= merit_index(')


def test_mir_declares_portable_expression_evaluation_order():
    program=parse(ORDER_MATRIX);Checker(program).check();lowered=mir(program)
    assert lowered['expression_evaluation_order'] == 'left_to_right'
    assert all(function['expression_evaluation_order']=='left_to_right' for function in lowered['functions'])


def test_ordered_lowering_does_not_weaken_conflicting_loan_rejection():
    source='''module ordered_loan_conflict
stable("counter-v1") struct Counter { value:i32; }
fn consume(borrow_mut left:Counter,borrow_mut right:Counter)->i32 { return left.value+right.value; }
fn main()->i32 { var counter:Counter=Counter{value:0}; return consume(counter,counter); }'''
    with pytest.raises(CompileError,match='M5003: conflicting loans of counter'):
        Checker(parse(source)).check()
