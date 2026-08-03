from pathlib import Path
import pytest

from merit.compiler import Checker, CompileError, Interpreter, CGenerator, parse
from merit.project.build import check, interpret, build
from merit.project.loader import load_project

ROOT = Path(__file__).parents[1]
PROJECT = ROOT / "examples/projects/binary_packet"


def test_byte_slice_and_vector_typecheck():
    source = '''
module systems
capability allocate;
fn main() -> i32 {
  with capability allocate {
    let a: Allocator = system_allocator();
    var b: Buffer = buffer_from_string(a, "abc");
    let s: ByteSlice = buffer_slice(b, 1, 2);
    var v: I64Vec = i64vec_new(a, 1);
    i64vec_push(v, slice_get(s, 0));
    print(i64vec_get(v, 0));
    drop(v);
    drop(b);
  }
  return 0;
}
'''
    program = parse(source)
    Checker(program).check()
    assert 'merit_ByteSlice' in CGenerator(program).generate()
    assert 'merit_I64Vec' in CGenerator(program).generate()


def test_vector_move_is_enforced():
    source = '''
module moved
capability allocate;
fn take(v: I64Vec) -> i32 { return 0; }
fn main() -> i32 {
  with capability allocate {
    let a: Allocator = system_allocator();
    var v: I64Vec = i64vec_new(a, 0);
    take(v);
    print(i64vec_len(v));
  }
  return 0;
}
'''
    with pytest.raises(CompileError, match='moved'):
        Checker(parse(source)).check()


def test_slice_requires_addressable_buffer():
    source = '''
module badslice
capability allocate;
fn main() -> i32 {
  with capability allocate {
    let a: Allocator = system_allocator();
    let s: ByteSlice = buffer_slice(buffer_new(a, 2), 0, 1);
    print(slice_len(s));
  }
  return 0;
}
'''
    with pytest.raises(CompileError, match='addressable'):
        Checker(parse(source)).check()


def test_binary_packet_project_interpreter_and_native(tmp_path, capsys):
    loaded = load_project(PROJECT / 'Merit.toml')
    check(loaded)
    assert loaded.program.module == 'binary_packet'
    output = interpret(loaded)
    assert output == '258\n60\n2\n258\n60\n'
    c_path, h_path, executable = build(loaded, tmp_path / 'packet')
    import subprocess
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    assert native.stdout == '258\n60\n2\n258\n60\n'
