from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from merit.compiler import Program, parse, _impl_function_name
from merit.diagnostics import render_exception
from .manifest import Manifest, load_manifest

IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][A-Za-z0-9_]*)\s*;\s*$", re.MULTILINE)
PUB_RE = re.compile(r"^(\s*)pub\s+(?=(?:stable\([^\n]+\)\s+)?(?:enum|trait|decimal|bounded|capability|struct|fn)\s+([A-Za-z_][A-Za-z0-9_]*))", re.MULTILINE)


class ProjectError(Exception):
    pass


@dataclass(frozen=True)
class SourceUnit:
    path: Path
    module: str
    imports: tuple[str, ...]
    program: Program
    exports: frozenset[str]


@dataclass(frozen=True)
class LoadedProject:
    manifest: Manifest
    units: tuple[SourceUnit, ...]
    program: Program


def _discover(manifest: Manifest) -> list[Path]:
    found: set[Path] = set()
    for pattern in manifest.sources:
        found.update(p.resolve() for p in manifest.root.glob(pattern) if p.is_file())
    entry = manifest.entry_path.resolve()
    if not entry.exists():
        raise ProjectError(f"entry source does not exist: {entry}")
    found.add(entry)
    return sorted(found)


def _parse_unit(path: Path) -> SourceUnit:
    source = path.read_text()
    imports = tuple(IMPORT_RE.findall(source))
    imports_source = IMPORT_RE.sub("", source)
    exports = frozenset(match.group(2) for match in PUB_RE.finditer(imports_source))
    parser_source = PUB_RE.sub(r"\1", imports_source)
    try:
        program = parse(parser_source)
    except Exception as exc:
        raise ProjectError(render_exception(exc, path, source)) from exc
    return SourceUnit(path, program.module, imports, program, exports)


def _check_graph(units: Iterable[SourceUnit], entry_module: str) -> None:
    by_name = {unit.module: unit for unit in units}
    if len(by_name) != len(tuple(units)):
        raise ProjectError("duplicate module declaration")
    for unit in by_name.values():
        missing = set(unit.imports) - set(by_name)
        if missing:
            raise ProjectError(f"module {unit.module} imports missing modules: {sorted(missing)}")
    state: dict[str, int] = {}
    trail: list[str] = []

    def visit(name: str) -> None:
        mark = state.get(name, 0)
        if mark == 2:
            return
        if mark == 1:
            start = trail.index(name)
            raise ProjectError("import cycle: " + " -> ".join(trail[start:] + [name]))
        state[name] = 1
        trail.append(name)
        for child in by_name[name].imports:
            visit(child)
        trail.pop()
        state[name] = 2

    visit(entry_module)


def _walk_expr(expr):
    if not isinstance(expr, tuple):
        return
    yield expr
    for value in expr[1:]:
        if isinstance(value, tuple):
            yield from _walk_expr(value)
        elif isinstance(value, list):
            for item in value:
                yield from _walk_expr(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from _walk_expr(item)


def _walk_statements(body):
    for statement in body:
        yield statement
        tag = statement[0]
        if tag in ("with_cap", "while"):
            yield from _walk_statements(statement[-1])
        elif tag == "if":
            yield from _walk_statements(statement[2]); yield from _walk_statements(statement[3])
        elif tag == "match":
            for arm in statement[2]: yield from _walk_statements(arm[2])


def _check_visibility(units: tuple[SourceUnit, ...]) -> None:
    owner: dict[str, SourceUnit] = {}
    variants: dict[str, SourceUnit] = {}
    for unit in units:
        symbols = set(unit.program.decimals) | set(unit.program.bounded) | set(unit.program.structs) | set(unit.program.enums) | set(unit.program.traits)
        symbols |= {f["name"] for f in unit.program.functions}
        for symbol in symbols: owner[symbol] = unit
        for enum in unit.program.enums.values():
            for variant in enum.variants: variants[variant.name] = unit
    builtins = {"checked_add", "checked_sub", "checked_mul", "decimal_div", "old"}
    primitive = {"void", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
    for unit in units:
        allowed_modules = set(unit.imports) | {unit.module}
        def require(symbol: str, context: str) -> None:
            target = owner.get(symbol) or variants.get(symbol)
            if target is None or target.module == unit.module: return
            if target.module not in allowed_modules:
                raise ProjectError(f"module {unit.module} uses {symbol} from unimported module {target.module} ({context})")
            exported_symbol = symbol
            if symbol in variants:
                exported_symbol = next(e.name for e in target.program.enums.values() if any(v.name == symbol for v in e.variants))
            if exported_symbol not in target.exports:
                raise ProjectError(f"module {unit.module} uses private symbol {exported_symbol} from {target.module} ({context})")
        for struct in unit.program.structs.values():
            for field in struct.fields:
                if field.type_name not in primitive: require(field.type_name, f"field {struct.name}.{field.name}")
        for enum in unit.program.enums.values():
            for variant in enum.variants:
                if variant.payload_type and variant.payload_type not in primitive: require(variant.payload_type, f"variant {enum.name}.{variant.name}")
        for function in unit.program.functions:
            for _, type_name, _ in function["params"]:
                if type_name not in primitive: require(type_name, f"function {function['name']}")
            if function["return"] not in primitive: require(function["return"], f"function {function['name']}")
            for statement in _walk_statements(function["body"]):
                if statement[0] in ("let", "try_let") and statement[2] not in primitive: require(statement[2], f"binding {statement[1]}")
                exprs=[]
                for value in statement[1:]:
                    if isinstance(value, tuple): exprs.append(value)
                for expr in exprs:
                    for node in _walk_expr(expr):
                        if node[0] == "call" and node[1] not in builtins: require(node[1], f"call in {function['name']}")
                        elif node[0] == "struct_init": require(node[1], f"construction in {function['name']}")


def _merge(manifest: Manifest, units: tuple[SourceUnit, ...], entry_module: str) -> Program:
    decimals = {}
    bounded = {}
    capabilities = set()
    structs = {}
    enums = {}
    traits = {}
    impls = []
    functions = []
    seen_functions: dict[str, Path] = {}
    for unit in units:
        for collection, incoming, kind in (
            (decimals, unit.program.decimals, "type"),
            (bounded, unit.program.bounded, "type"),
            (structs, unit.program.structs, "type"),
            (enums, unit.program.enums, "type"),
            (traits, unit.program.traits, "trait"),
        ):
            for name, value in incoming.items():
                if name in decimals or name in bounded or name in structs or name in enums or name in traits:
                    raise ProjectError(f"duplicate {kind} symbol {name} in {unit.path}")
                collection[name] = value
        capabilities.update(unit.program.capabilities)
        impls.extend(unit.program.impls)
        for function in unit.program.functions:
            name = function["name"]
            if name.startswith("impl__"):
                continue
            if name == "main" and unit.module != entry_module:
                raise ProjectError(f"only entry module may define main; found in {unit.path}")
            if name in seen_functions:
                raise ProjectError(f"duplicate function {name}: {seen_functions[name]} and {unit.path}")
            seen_functions[name] = unit.path
            functions.append(function)
    for impl in impls:
        for method in impl.methods:
            generated = dict(method)
            generated["name"] = _impl_function_name(impl.trait_name, impl.target_type, method["name"])
            if generated["name"] not in seen_functions:
                seen_functions[generated["name"]] = manifest.root
                functions.append(generated)
    return Program(manifest.name, decimals, bounded, capabilities, structs, functions, enums, traits, impls)


def load_project(manifest_path: Path) -> LoadedProject:
    manifest = load_manifest(manifest_path)
    paths = _discover(manifest)
    units = tuple(_parse_unit(path) for path in paths)
    entry = next((u for u in units if u.path.resolve() == manifest.entry_path.resolve()), None)
    if entry is None:
        raise ProjectError("entry module was not loaded")
    _check_graph(units, entry.module)
    _check_visibility(units)
    merged = _merge(manifest, units, entry.module)
    return LoadedProject(manifest, units, merged)
