from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from merit.bootstrap.replacement_build import ReplacementBuildError
from merit.compiler import CompileError, LayoutEngine, audit_payload
from merit.diagnostics import diagnostic_from_exception, render_exception

from .build import build, build_shared, check, interpret
from .loader import ProjectError, load_project
from .replacement import build_replacement_project


def _manifest(value: str) -> Path:
    path = Path(value)
    return path / "Merit.toml" if path.is_dir() else path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="merit-project")
    parser.add_argument("command", choices=("check", "build", "build-shared", "run", "verify", "graph", "layout", "audit"))
    parser.add_argument("path", nargs="?", default="Merit.toml")
    parser.add_argument("-o", "--output")
    parser.add_argument(
        "--compiler",
        choices=("reference", "replacement"),
        default="reference",
        help="production compiler path; replacement mode consumes only native-resolved artifacts and never falls back",
    )
    parser.add_argument("--diagnostic-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        project = load_project(_manifest(args.path))
        if args.command == "graph":
            for unit in project.units:
                imports = ", ".join(unit.imports) or "(none)"
                print(f"{unit.module}: {imports}")
            return 0
        if args.command == "layout":
            print(json.dumps(LayoutEngine(project.program).all(), indent=2))
            return 0
        if args.command == "audit":
            checker = check(project)
            print(json.dumps(audit_payload(project.program, checker), indent=2))
            return 0
        if args.command == "check":
            checker = check(project)
            print(f"checked {len(project.units)} modules, {len(project.program.functions)} functions")
            print(f"capability sites: {len(checker.audit_sites)}")
            return 0
        output = Path(args.output) if args.output else project.manifest.root / "build" / project.manifest.name
        if args.compiler == "replacement" and args.command in {"build", "run"}:
            replacement = build_replacement_project(project, output)
            if args.command == "build":
                print(replacement.executable)
                return 0
            return subprocess.run([str(replacement.executable)]).returncode
        if args.compiler == "replacement":
            raise ReplacementBuildError(
                f"--compiler replacement does not support {args.command!r}; refusing to use the reference compiler"
            )
        if args.command == "build":
            _, _, executable = build(project, output)
            print(executable)
            return 0
        if args.command == "build-shared":
            _, _, library = build_shared(project, output)
            print(library)
            return 0
        if args.command == "run":
            _, _, executable = build(project, output)
            return subprocess.run([str(executable)]).returncode
        expected = interpret(project)
        _, _, executable = build(project, output)
        actual = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
        if actual != expected:
            print("interpreter/native mismatch", file=sys.stderr)
            print("--- interpreter ---", file=sys.stderr)
            print(expected, file=sys.stderr, end="")
            print("--- native ---", file=sys.stderr)
            print(actual, file=sys.stderr, end="")
            return 1
        print(f"verified {len(project.units)} modules; output matches ({len(actual)} bytes)")
        return 0
    except CompileError as exc:
        span = getattr(exc, "span", None)
        source_path = Path(span.source_name) if span is not None and span.source_name else _manifest(args.path)
        source = source_path.read_text() if source_path.is_file() else ""
        if args.diagnostic_format == "json":
            print(json.dumps(diagnostic_from_exception(exc,source_path,source).to_dict()),file=sys.stderr)
        else:
            print(render_exception(exc, source_path, source), file=sys.stderr)
        return 1
    except (ProjectError, ReplacementBuildError, ValueError, subprocess.CalledProcessError) as exc:
        if args.diagnostic_format == "json":
            span=getattr(exc,"span",None)
            diagnostic_path=Path(span.source_name) if span is not None and getattr(span,"source_name",None) else _manifest(args.path)
            source=diagnostic_path.read_text() if diagnostic_path.is_file() else ""
            print(json.dumps(diagnostic_from_exception(exc,diagnostic_path,source).to_dict()),file=sys.stderr)
        else:
            print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
