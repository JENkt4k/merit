"""Deterministic lowering from ``bootstrap-hir-v1`` to ``bootstrap-mir-v1``.

This is the first executable bridge between the versioned semantic and
operational contracts.  It intentionally supports a small, explicit core and
rejects unsupported HIR rather than inventing backend semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

from merit.bootstrap.hir_contract import HirModule, HirNode, HirType
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
    SourceSpan,
)


class HirToMirError(ValueError):
    """Raised when checked HIR cannot be represented by the core lowerer."""


_VALUE_KINDS = frozenset({
    "literal", "identifier", "binary", "conversion", "call", "constructor",
    "move", "borrow",
})
_STATEMENT_KINDS = frozenset({
    "let", "assign", "drop", "contract_check", "capability_scope", "return",
})


def _mir_type(type_: HirType) -> MirType:
    return MirType(type_.name, tuple(_mir_type(argument) for argument in type_.arguments))


def _span(node: HirNode) -> SourceSpan | None:
    if node.span is None:
        return None
    return SourceSpan(node.span.start, node.span.length)


@dataclass
class _FunctionLowerer:
    module: HirModule
    function: HirNode

    def __post_init__(self) -> None:
        self.by_id = {node.node_id: node for node in self.module.nodes}
        self.binding_locals: dict[int, int] = {}
        self.value_locals: dict[int, int] = {}
        self.locals: list[MirLocal] = []
        self.instructions: list[MirInstruction] = []
        self.next_local = 0
        self.next_instruction = 0
        self.terminator: MirTerminator | None = None

        for binding in sorted(self.module.bindings, key=lambda item: item.binding_id):
            local_id = self._new_local(
                binding.name,
                _mir_type(binding.type),
                mutable=binding.mutable,
                ownership=binding.ownership,
                source_binding_id=binding.binding_id,
            )
            self.binding_locals[binding.binding_id] = local_id

    def _new_local(
        self,
        name: str,
        type_: MirType,
        *,
        mutable: bool = False,
        ownership: str = "value",
        source_binding_id: int | None = None,
    ) -> int:
        local_id = self.next_local
        self.next_local += 1
        self.locals.append(MirLocal(
            local_id,
            name,
            type_,
            mutable,
            ownership,
            source_binding_id,
        ))
        return local_id

    def _temporary(self, node: HirNode) -> int:
        existing = self.value_locals.get(node.node_id)
        if existing is not None:
            return existing
        local_id = self._new_local(
            f"_t{node.node_id}",
            _mir_type(node.type),
            ownership=node.ownership if node.ownership != "none" else "value",
        )
        self.value_locals[node.node_id] = local_id
        return local_id

    def _emit(
        self,
        node: HirNode,
        kind: str,
        *,
        result: int | None = None,
        operands: tuple[int, ...] = (),
        symbol: str | None = None,
        value: object | None = None,
        ownership: str | None = None,
        numeric_policy: str = "none",
        conversion_policy: str = "none",
        contract_kind: str = "none",
        capabilities: tuple[str, ...] = (),
    ) -> None:
        self.instructions.append(MirInstruction(
            self.next_instruction,
            kind,
            result,
            operands,
            symbol,
            value,
            _span(node),
            node.ownership if ownership is None else ownership,
            numeric_policy,
            conversion_policy,
            contract_kind,
            capabilities,
        ))
        self.next_instruction += 1

    def _child(self, node: HirNode, index: int) -> HirNode:
        try:
            return self.by_id[node.children[index]]
        except IndexError as error:
            raise HirToMirError(
                f"HIR {node.kind} node {node.node_id} is missing child {index}"
            ) from error

    def lower_value(self, node: HirNode) -> int:
        cached = self.value_locals.get(node.node_id)
        if cached is not None:
            return cached
        if node.kind not in _VALUE_KINDS:
            raise HirToMirError(
                f"HIR node {node.node_id} kind {node.kind!r} is not a supported value"
            )

        if node.kind == "identifier":
            if node.binding_id is None or node.binding_id not in self.binding_locals:
                raise HirToMirError(f"identifier node {node.node_id} has no resolved binding")
            local_id = self.binding_locals[node.binding_id]
            self.value_locals[node.node_id] = local_id
            return local_id

        result = self._temporary(node)
        if node.kind == "literal":
            self._emit(node, "const", result=result, value=node.value, ownership="value")
        elif node.kind == "binary":
            if len(node.children) != 2:
                raise HirToMirError(f"binary node {node.node_id} requires two operands")
            left = self.lower_value(self._child(node, 0))
            right = self.lower_value(self._child(node, 1))
            self._emit(
                node,
                "binary",
                result=result,
                operands=(left, right),
                symbol=node.symbol,
                numeric_policy=node.numeric_policy,
            )
        elif node.kind == "conversion":
            if len(node.children) != 1:
                raise HirToMirError(f"conversion node {node.node_id} requires one operand")
            operand = self.lower_value(self._child(node, 0))
            self._emit(
                node,
                "convert",
                result=result,
                operands=(operand,),
                conversion_policy=node.conversion_policy,
            )
        elif node.kind == "call":
            operands = tuple(self.lower_value(self.by_id[child]) for child in node.children)
            if not node.symbol:
                raise HirToMirError(f"call node {node.node_id} requires a resolved symbol")
            self._emit(node, "call", result=result, operands=operands, symbol=node.symbol)
        elif node.kind == "constructor":
            operands = tuple(self.lower_value(self.by_id[child]) for child in node.children)
            if not node.symbol:
                raise HirToMirError(f"constructor node {node.node_id} requires a type symbol")
            self._emit(node, "construct", result=result, operands=operands, symbol=node.symbol)
        elif node.kind in {"move", "borrow"}:
            if len(node.children) != 1:
                raise HirToMirError(f"{node.kind} node {node.node_id} requires one operand")
            operand = self.lower_value(self._child(node, 0))
            self._emit(node, node.kind, result=result, operands=(operand,))
        return result

    def lower_statement(self, node: HirNode) -> None:
        if node.kind not in _STATEMENT_KINDS:
            raise HirToMirError(
                f"HIR node {node.node_id} kind {node.kind!r} is not a supported statement"
            )
        if self.terminator is not None:
            raise HirToMirError(f"statement node {node.node_id} appears after a terminator")

        if node.kind in {"let", "assign"}:
            if node.binding_id is None or node.binding_id not in self.binding_locals:
                raise HirToMirError(f"{node.kind} node {node.node_id} has no resolved binding")
            if len(node.children) != 1:
                raise HirToMirError(f"{node.kind} node {node.node_id} requires one value")
            source = self.lower_value(self._child(node, 0))
            destination = self.binding_locals[node.binding_id]
            self._emit(node, "copy", result=destination, operands=(source,))
        elif node.kind == "drop":
            if node.binding_id is None or node.binding_id not in self.binding_locals:
                raise HirToMirError(f"drop node {node.node_id} has no resolved binding")
            self._emit(node, "drop", operands=(self.binding_locals[node.binding_id],))
        elif node.kind == "contract_check":
            if len(node.children) != 1:
                raise HirToMirError(f"contract node {node.node_id} requires one condition")
            condition = self.lower_value(self._child(node, 0))
            contract_kind = node.symbol or "invariant"
            self._emit(
                node,
                "contract_check",
                operands=(condition,),
                contract_kind=contract_kind,
            )
        elif node.kind == "capability_scope":
            self._emit(node, "capability_check", capabilities=node.capabilities)
            for child_id in node.children:
                child = self.by_id[child_id]
                if child.kind in _STATEMENT_KINDS:
                    self.lower_statement(child)
                else:
                    self.lower_value(child)
        elif node.kind == "return":
            if len(node.children) > 1:
                raise HirToMirError(f"return node {node.node_id} accepts at most one value")
            operands = ()
            if node.children:
                operands = (self.lower_value(self._child(node, 0)),)
            self.terminator = MirTerminator("return", operands=operands, span=_span(node))

    def lower(self) -> MirFunction:
        if self.function.kind != "function":
            raise HirToMirError(f"root node {self.function.node_id} is not a function")
        if not self.function.symbol:
            raise HirToMirError(f"function node {self.function.node_id} requires a symbol")

        for child_id in self.function.children:
            child = self.by_id[child_id]
            if child.kind in _STATEMENT_KINDS:
                self.lower_statement(child)
            elif child.kind in _VALUE_KINDS:
                self.lower_value(child)
            else:
                raise HirToMirError(
                    f"function {self.function.symbol} contains unsupported HIR kind {child.kind!r}"
                )

        if self.terminator is None:
            self.terminator = MirTerminator("return")
        block = MirBlock(0, tuple(self.instructions), self.terminator)
        return MirFunction(
            self.function.symbol,
            _mir_type(self.function.type),
            tuple(self.locals),
            (block,),
            0,
            self.function.capabilities,
        )


def lower_hir_to_mir(module: HirModule) -> MirModule:
    """Lower all function roots in a checked HIR module into canonical MIR.

    Roots must be function nodes.  The supported core is intentionally strict;
    unsupported control flow and aggregate operations fail with deterministic
    ``HirToMirError`` messages rather than being approximated.
    """

    by_id = {node.node_id: node for node in module.nodes}
    functions: list[MirFunction] = []
    for root_id in module.roots:
        root = by_id[root_id]
        functions.append(_FunctionLowerer(module, root).lower())
    return MirModule(module.name, tuple(functions))
