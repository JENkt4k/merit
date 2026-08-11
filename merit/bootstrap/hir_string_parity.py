"""Canonical reconstruction for the non-numeric string-literal HIR slice."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .hir_contract import HirModule, HirNode, HirType, SourceSpan, canonical_hir_json
from .hir_generic_parity import lower_native_generic_hir_records
from .hir_parity import NativeHirRecord
from .parity import StageObservation, observe

_KIND_STRING_LITERAL = 12
_POLICY_NONE = 0


class NativeStringHirError(ValueError):
    """Raised when a native string literal violates the additive HIR contract."""


def lower_native_complete_expression_hir_records(
    records: Sequence[NativeHirRecord],
    source: str,
    *,
    module_name: str = "expression",
    type_names: Mapping[int, HirType] | None = None,
    constructor_fields: Mapping[str, tuple[str, ...]] | None = None,
    generic_types: Mapping[str, HirType] | None = None,
) -> HirModule:
    """Reconstruct canonical HIR, including the isolated string-literal root slice.

    String literals are intentionally non-numeric: their source spelling is
    preserved verbatim, their semantic type is supplied by the checked boundary,
    and their numeric policy remains absent. The current expression grammar has
    no operators over strings, so a string record is required to be the sole
    native record until such operators acquire an explicit semantic contract.
    """

    materialized = tuple(tuple(int(value) for value in record) for record in records)
    string_records = [record for record in materialized if record[0] == _KIND_STRING_LITERAL]
    if not string_records:
        return lower_native_generic_hir_records(
            materialized,
            source,
            module_name=module_name,
            type_names=type_names,
            constructor_fields=constructor_fields,
            generic_types=generic_types,
        )
    if len(materialized) != 1 or len(string_records) != 1:
        raise NativeStringHirError("string HIR v1 currently requires an isolated literal root")

    kind, start, length, left, right, symbol, type_code, policy, binding_id = materialized[0]
    if start < 0 or length < 2 or start + length > len(source):
        raise NativeStringHirError("string literal span is outside source text")
    if left != -1 or right != -1 or symbol != 0 or binding_id != -1:
        raise NativeStringHirError("string literal has invalid child/symbol fields")
    if policy != _POLICY_NONE:
        raise NativeStringHirError("string literal must not carry a numeric policy")
    types = {} if type_names is None else dict(type_names)
    try:
        type_ = types[type_code]
    except KeyError as error:
        raise NativeStringHirError(f"unresolved string literal type code {type_code}") from error
    spelling = source[start : start + length]
    if not (spelling.startswith('"') and spelling.endswith('"')):
        raise NativeStringHirError("string literal span must preserve quoted source spelling")
    node = HirNode(0, "literal", type_, span=SourceSpan(start, length), value=spelling)
    return HirModule(module_name, (), (node,), (0,))


def string_hir_parity_observations(
    case_id: str,
    reference: HirModule,
    native_records,
    source: str,
    *,
    type_names: Mapping[int, HirType] | None = None,
) -> tuple[StageObservation, StageObservation]:
    bootstrap = lower_native_complete_expression_hir_records(
        native_records,
        source,
        module_name=reference.name,
        type_names=type_names,
    )
    return (
        observe(case_id, "hir", "reference", canonical_hir_json(reference)),
        observe(case_id, "hir", "bootstrap", canonical_hir_json(bootstrap)),
    )
