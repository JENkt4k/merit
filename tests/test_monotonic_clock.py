import os
from pathlib import Path
import subprocess

import pytest

from merit.compiler import (
    BUILTIN_SIGS,
    CAPABILITY_POLICIES,
    CGenerator,
    Checker,
    CompileError,
    Interpreter,
    audit_payload,
    compile_file,
    parse,
)


CLOCK_PROGRAM = '''module clock_probe
capability clock;
fn main()->i32 {
    with capability clock {
        let before:i64=monotonic_ns();
        let after:i64=monotonic_ns();
        print(after >= before);
    }
    return 0;
}
'''


def test_monotonic_clock_has_explicit_capability_policy():
    sig = BUILTIN_SIGS['monotonic_ns']
    assert sig.params == ()
    assert sig.return_type == 'i64'
    assert sig.capability == 'clock'
    assert sig.hazard == 'monotonic_clock'
    policy = CAPABILITY_POLICIES['clock']
    assert (policy.hazard_class, policy.review, policy.scope) == (
        'monotonic_clock', 'time-read', 'lexical'
    )


def test_monotonic_clock_requires_lexical_clock_capability():
    source = '''module denied
capability clock;
fn main()->i32 { let now:i64=monotonic_ns(); print(now); return 0; }
'''
    with pytest.raises(CompileError, match=r'M2003: call to monotonic_ns requires capabilities'):
        Checker(parse(source)).check()


def test_monotonic_clock_is_audited_as_runtime_effect():
    program = parse(CLOCK_PROGRAM)
    checker = Checker(program).check()
    audit = audit_payload(program, checker)
    operations = {
        (entry['operation'], entry['capability'], entry['hazard'], entry['hazard_class'], entry['review'])
        for entry in audit['hazardous_operations']
    }
    assert ('monotonic_ns', 'clock', 'monotonic_clock', 'monotonic_clock', 'time-read') in operations
    requirements = {
        (entry['kind'], entry['operation'], entry['capability'], entry['hazard'])
        for entry in audit['capability_requirements']
    }
    assert ('builtin', 'monotonic_ns', 'clock', 'monotonic_clock') in requirements


def test_interpreter_monotonic_clock_is_nondecreasing(capsys):
    program = parse(CLOCK_PROGRAM)
    Checker(program).check()
    assert Interpreter(program).run().value == 0
    assert capsys.readouterr().out.strip() == '1'


def test_c_codegen_uses_platform_monotonic_primitives():
    program = parse(CLOCK_PROGRAM)
    Checker(program).check()
    generated = CGenerator(program).generate()
    assert 'CLOCK_MONOTONIC' in generated
    assert 'clock_gettime' in generated
    assert 'QueryPerformanceCounter' in generated
    assert 'QueryPerformanceFrequency' in generated
    assert 'merit_monotonic_ns()' in generated


def test_native_monotonic_clock_is_nondecreasing(tmp_path):
    source = tmp_path / 'clock_probe.mrt'
    source.write_text(CLOCK_PROGRAM, encoding='utf-8')
    executable = tmp_path / 'clock_probe'
    compile_file(source, executable)
    native_executable = executable.with_suffix('.exe') if os.name == 'nt' else executable
    completed = subprocess.run(
        [str(native_executable)], check=True, text=True, capture_output=True
    )
    assert completed.stdout.strip() == '1'
