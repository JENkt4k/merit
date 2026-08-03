import subprocess
from pathlib import Path

from merit.compiler import parse, Checker, Interpreter, CGenerator

ROOT = Path(__file__).resolve().parents[1]


def test_simple_examples_verify_natively(tmp_path):
    for source in sorted((ROOT / "examples" / "simple").glob("*.mrt")):
        completed = subprocess.run(
            ["merit", "verify", str(source)],
            check=True,
            text=True,
            capture_output=True,
        )
        assert "verified:" in completed.stdout


def test_print_evaluates_mutating_call_once():
    source = (ROOT / "examples" / "simple" / "account.mrt").read_text()
    program = parse(source)
    Checker(program).check()
    generated = CGenerator(program).generate()
    assert generated.count("merit_deposit(&account, 2425)") == 1


def test_new_project_builds_and_runs(tmp_path):
    project = tmp_path / "tiny-app"
    subprocess.run(["merit", "new", str(project)], check=True)
    source = project / "src" / "main.mrt"
    assert source.exists()
    completed = subprocess.run(
        ["merit", "exec", str(source)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert completed.stdout == "42\n"
