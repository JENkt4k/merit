"""Canonical reconstruction helpers for single-type generic bootstrap calls."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from .hir_contract import HirModule, HirType, canonical_hir_json
from .hir_parity import NativeHirRecord, lower_native_primitive_hir_records
from .parity import StageObservation, observe


class NativeGenericHirError(ValueError):
    """Raised when a native generic application span is not deterministic."""


def _split_single_generic_symbol(symbol: str) -> tuple[str, str] | None:
    opening = symbol.find("<")
    if opening < 1 or not symbol.endswith(">"):
        return None
    base = symbol[:opening]
    argument = symbol[opening + 1 : -1].strip()
    if not base or not argument or "<" in argument or ">" in argument or "," in argument:
        raise NativeGenericHirError(
            f"unsupported generic application symbol {symbol!r}"
        )
    return base, argument


def lower_native_generic_hir_records(
    records: tuple[NativeHirRecord, ...] | list[NativeHirRecord],
    source: str,
    *,
    module_name: str = "expression",
    type_names: Mapping[int, HirType] | None = None,
    constructor_fields: Mapping[str, tuple[str, ...]] | None = None,
    generic_types: Mapping[str, HirType] | None = None,
) -> HirModule:
    """Lower native HIR and attach resolved type arguments to generic calls.

    The flat native contract reuses structural symbol-reference records for the
    current single-type generic application grammar. A call whose symbol span is
    ``name<Type>`` is normalized to symbol ``name`` plus one canonical HIR type
    argument. Ordinary calls remain byte-for-byte equivalent to the base adapter.
    """

    module = lower_native_primitive_hir_records(
        records,
        source,
        module_name=module_name,
        type_names=type_names,
        constructor_fields=constructor_fields,
    )
    known_types = {} if generic_types is None else dict(generic_types)
    changed = False
    nodes = []
    for node in module.nodes:
        if node.kind != "call" or node.symbol is None:
            nodes.append(node)
            continue
        generic = _split_single_generic_symbol(node.symbol)
        if generic is None:
            nodes.append(node)
            continue
        symbol, type_name = generic
        type_argument = known_types.get(type_name)
        if type_argument is None:
            raise NativeGenericHirError(
                f"unresolved generic type argument {type_name!r}"
            )
        nodes.append(
            replace(
                node,
                symbol=symbol,
                generic_arguments=(type_argument,),
            )
        )
        changed = True
    if not changed:
        return module
    return HirModule(module.name, module.bindings, tuple(nodes), module.roots)


def generic_hir_parity_observations(
    case_id: str,
    reference: HirModule,
    native_records,
    source: str,
    *,
    type_names: Mapping[int, HirType] | None = None,
    constructor_fields: Mapping[str, tuple[str, ...]] | None = None,
    generic_types: Mapping[str, HirType] | None = None,
) -> tuple[StageObservation, StageObservation]:
    bootstrap = lower_native_generic_hir_records(
        native_records,
        source,
        module_name=reference.name,
        type_names=type_names,
        constructor_fields=constructor_fields,
        generic_types=generic_types,
    )
    return (
        observe(case_id, "hir", "reference", canonical_hir_json(reference)),
        observe(case_id, "hir", "bootstrap", canonical_hir_json(bootstrap)),
    )
