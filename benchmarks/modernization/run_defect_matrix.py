from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "defect_probes_v1.json"

MERIT_SOURCES = {
    "excess-money-scale": """module defect_scale

decimal USD(18, 2, half_even);
fn main() -> i32 {
    let amount: USD = 1.001;
    return 0;
}
""",
    "invalid-account-domain": """module defect_account

bounded AccountNumber(u64, 1, 999999999999);
fn main() -> i32 {
    let account: AccountNumber = 0;
    return 0;
}
""",
    "mixed-currency-domain": """module defect_currency

decimal USD(18, 2, half_even);
decimal EUR(18, 2, half_even);
fn main() -> i32 {
    let usd: USD = 1.00;
    let eur: EUR = 1.00;
    let total: USD = usd + eur;
    return 0;
}
""",
}

JAVA_SOURCES = {
    "excess-money-scale": """import java.math.BigDecimal; final class Probe { public static void main(String[] a) { BigDecimal amount = new BigDecimal(\"1.001\"); } }\n""",
    "invalid-account-domain": """final class Probe { public static void main(String[] a) { long account = 0L; } }\n""",
    "mixed-currency-domain": """import java.math.BigDecimal; final class Probe { public static void main(String[] a) { BigDecimal usd = new BigDecimal(\"1.00\"); BigDecimal eur = new BigDecimal(\"1.00\"); BigDecimal total = usd.add(eur); } }\n""",
}

CSHARP_SOURCES = {
    "excess-money-scale": """using System; static class Probe { static void Main() { decimal amount = 1.001m; } }\n""",
    "invalid-account-domain": """using System; static class Probe { static void Main() { long account = 0L; } }\n""",
    "mixed-currency-domain": """using System; static class Probe { static void Main() { decimal usd = 1.00m; decimal eur = 1.00m; decimal total = usd + eur; } }\n""",
}

EXPECTED = {
    "merit": {probe: "compiler" for probe in MERIT_SOURCES},
    "java": {probe: "not_caught_at_compile_time" for probe in JAVA_SOURCES},
    "csharp": {probe: "not_caught_at_compile_time" for probe in CSHARP_SOURCES},
}


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def _compile_merit(source: str, work: Path) -> tuple[str, str]:
    merit = shutil.which("merit")
    if not merit:
        raise RuntimeError("defect matrix requires merit CLI")
    path = work / "probe.mrt"
    path.write_text(source, encoding="utf-8")
    result = _run([merit, "check", str(path)])
    return ("compiler" if result.returncode != 0 else "not_caught_at_compile_time", result.stderr + result.stdout)


def _compile_java(source: str, work: Path) -> tuple[str, str]:
    javac = shutil.which("javac")
    if not javac:
        raise RuntimeError("defect matrix requires javac")
    path = work / "Probe.java"
    path.write_text(source, encoding="utf-8")
    result = _run([javac, str(path)], cwd=work)
    return ("compiler" if result.returncode != 0 else "not_caught_at_compile_time", result.stderr + result.stdout)


def _compile_csharp(source: str, work: Path) -> tuple[str, str]:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError("defect matrix requires .NET 8+")
    (work / "Probe.cs").write_text(source, encoding="utf-8")
    (work / "Probe.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>disable</ImplicitUsings><Nullable>disable</Nullable></PropertyGroup></Project>\n',
        encoding="utf-8",
    )
    result = _run([dotnet, "build", "Probe.csproj", "--nologo", "-v:q"], cwd=work)
    return ("compiler" if result.returncode != 0 else "not_caught_at_compile_time", result.stderr + result.stdout)


def run() -> dict:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if spec.get("schema") != "merit-modernization-defect-probes-v1":
        raise ValueError("unsupported defect probe schema")

    rows = []
    compilers = {
        "merit": (_compile_merit, MERIT_SOURCES),
        "java": (_compile_java, JAVA_SOURCES),
        "csharp": (_compile_csharp, CSHARP_SOURCES),
    }
    for probe in spec["probes"]:
        probe_id = probe["id"]
        observed = {}
        diagnostics = {}
        for language, (compiler, sources) in compilers.items():
            with tempfile.TemporaryDirectory(prefix=f"merit-defect-{language}-") as tmp:
                stage, diagnostic = compiler(sources[probe_id], Path(tmp))
            expected = EXPECTED[language][probe_id]
            if stage != expected:
                raise AssertionError(f"{probe_id}/{language}: expected {expected}, observed {stage}: {diagnostic}")
            observed[language] = stage
            diagnostics[language] = diagnostic.strip().splitlines()[:4]
        rows.append({
            "id": probe_id,
            "invariant": probe["invariant"],
            "observed": observed,
            "diagnostic_excerpt": diagnostics,
        })

    return {
        "schema": "merit-modernization-defect-matrix-v1",
        "scope": spec["scope"],
        "interpretation": spec["interpretation"],
        "probes": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run compile-time modernization defect probes")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run()
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print(report["scope"])
        for row in report["probes"]:
            print(f"{row['id']}: merit={row['observed']['merit']} java={row['observed']['java']} csharp={row['observed']['csharp']}")
        print("scope note: this compares the benchmark baselines, not every possible custom Java/C# domain design")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
