"""Freeze representative runnable Alpha.2 C/header bytes during RM1."""

import hashlib

import pytest

from merit.compiler import CGenerator, Checker, parse


@pytest.mark.parametrize(("source", "c_sha256", "header_sha256"), [
    (
        "module demo\nfn main()->i32 { let x:i32=1; print(x); return 0; }",
        "036b74abfc90e9469f30d98230d0464b54987556fd01d816ce718d1eefc61b88",
        "9480a148481c29215eb26c4485a229ba44a60b92f18da5665acc4bb016e2e0dc",
    ),
    (
        "module demo\nstruct Box { value:i32; } destructor Box { print(9); }\n"
        "fn main()->i32 { let x:Box=Box {value:1}; print(x.value); return 0; }",
        "6d950c65d4b866d6ed606cab45368ccdc6199319aaeff2fc186ef943fbfded6d",
        "78dbdb5c267b56514cbe788b0bdc793065e92314ba5a6427fcc2fa072a232f8b",
    ),
    (
        "module demo\nfn expose(borrow x:i32)->borrow i32 { return x; }\n"
        "fn main()->i32 { return 0; }",
        "653535cab2531293aa4582ffdde97e25a41c5b7ff873cf31febf9ca6f4fa79e8",
        "dcdd5748f38a42d555c2f715aa5233537ade77a7758e81313b902ef7ad27210b",
    ),
])
def test_old_program_artifact_bytes(source, c_sha256, header_sha256):
    program = parse(source)
    Checker(program).check()
    generator = CGenerator(program)
    assert hashlib.sha256(generator.generate().encode()).hexdigest() == c_sha256
    assert hashlib.sha256(generator.header().encode()).hexdigest() == header_sha256
