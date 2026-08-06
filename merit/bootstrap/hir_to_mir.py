"""Deterministic lowering from ``bootstrap-hir-v1`` to ``bootstrap-mir-v1``.

The bridge supports ordered straight-line operations and structured ``if``,
``while``, and integer/default ``match`` control flow. Unsupported HIR is
rejected rather than approximated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    """Raised when checked HIR cannot be represented by the lowerer."""


_VALUE_KINDS = frozenset({
    "literal", "identifier", "binary", "conversion", "call", "constructor",
    "move", "borrow",
})
_SIMPLE_STATEMENT_KINDS = frozenset({
    "let", "assign", "drop", "contract_check", "capability_scope", "return",
})
_CONTROL_KINDS = frozenset({"if", "while", "match"})
_STATEMENT_KINDS = _SIMPLE_STATEMENT_KINDS | _CONTROL_KINDS | {"block"}


def _mir_type(type_: HirType) -> MirType:
    return MirType(type_.name, tuple(_mir_type(argument) for argument in type_.arguments))


def _span(node: HirNode) -> SourceSpan | None:
    if node.span is None:
        return None
    return SourceSpan(node.span.start, node.span.length)


@dataclass
class _BlockBuilder:
    block_id: int
    instructions: list[MirInstruction] = field(default_factory=list)
    terminator: MirTerminator | None = None


@dataclass
class _FunctionLowerer:
    module: HirModule
    function: HirNode

    def __post_init__(self) -> None:
        self.by_id = {node.node_id: node for node in self.module.nodes}
        self.binding_locals: dict[int, int] = {}
        self.value_locals: dict[int, int] = {}
        self.locals: list[MirLocal] = []
        self.blocks: list[_BlockBuilder] = []
        self.next_local = 0
        self.next_instruction = 0
        self.current = self._new_block()

        for binding in sorted(self.module.bindings, key=lambda item: item.binding_id):
            local_id = self._new_local(
                binding.name,
                _mir_type(binding.type),
                mutable=binding.mutable,
                ownership=binding.ownership,
                source_binding_id=binding.binding_id,
            )
            self.binding_locals[binding.binding_id] = local_id

    def _new_block(self) -> _BlockBuilder:
        block = _BlockBuilder(len(self.blocks))
        self.blocks.append(block)
        return block

    def _switch_to(self, block: _BlockBuilder) -> None:
        self.current = block

    def _terminate(self, terminator: MirTerminator) -> None:
        if self.current.terminator is not None:
            raise HirToMirError(f"MIR block {self.current.block_id} already has a terminator")
        self.current.terminator = terminator

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
        if self.current.terminator is not None:
            raise HirToMirError(
                f"instruction for HIR node {node.node_id} appears after a terminator"
            )
        self.current.instructions.append(MirInstruction(
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

    def _lower_sequence(self, node_ids: tuple[int, ...]) -> None:
        for node_id in node_ids:
            if self.current.terminator is not None:
                raise HirToMirError(f"statement node {node_id} appears after a terminator")
            node = self.by_id[node_id]
            if node.kind in _STATEMENT_KINDS:
                self.lower_statement(node)
            elif node.kind in _VALUE_KINDS:
                self.lower_value(node)
            else:
                raise HirToMirError(
                    f"function {self.function.symbol} contains unsupported HIR kind {node.kind!r}"
                )

    def _lower_block(self, node: HirNode) -> None:
        if node.kind != "block":
            raise HirToMirError(f"expected block node, found {node.kind!r}")
        self._lower_sequence(node.children)

    def _lower_if(self, node: HirNode) -> None:
        if len(node.children) not in {2, 3}:
            raise HirToMirError(
                f"if node {node.node_id} requires condition, then block, and optional else block"
            )
        condition = self.lower_value(self._child(node, 0))
        then_node = self._child(node, 1)
        else_node = self._child(node, 2) if len(node.children) == 3 else None
        if then_node.kind != "block" or (else_node is not None and else_node.kind != "block"):
            raise HirToMirError(f"if node {node.node_id} branches must be block nodes")

        then_block = self._new_block()
        else_block = self._new_block()
        join_block = self._new_block()
        self._terminate(MirTerminator(
            "branch",
            operands=(condition,),
            targets=(then_block.block_id, else_block.block_id),
            span=_span(node),
        ))

        self._switch_to(then_block)
        self._lower_block(then_node)
        if self.current.terminator is None:
            self._terminate(MirTerminator("jump", targets=(join_block.block_id,)))

        self._switch_to(else_block)
        if else_node is not None:
            self._lower_block(else_node)
        if self.current.terminator is None:
            self._terminate(MirTerminator("jump", targets=(join_block.block_id,)))

        self._switch_to(join_block)

    def _lower_while(self, node: HirNode) -> None:
        if len(node.children) != 2:
            raise HirToMirError(f"while node {node.node_id} requires condition and body block")
        condition_node = self._child(node, 0)
        body_node = self._child(node, 1)
        if body_node.kind != "block":
            raise HirToMirError(f"while node {node.node_id} body must be a block node")

        condition_block = self._new_block()
        body_block = self._new_block()
        exit_block = self._new_block()
        self._terminate(MirTerminator("jump", targets=(condition_block.block_id,)))

        self._switch_to(condition_block)
        self.value_locals.pop(condition_node.node_id, None)
        condition = self.lower_value(condition_node)
        self._terminate(MirTerminator(
            "branch",
            operands=(condition,),
            targets=(body_block.block_id, exit_block.block_id),
            span=_span(node),
        ))

        self._switch_to(body_block)
        self._lower_block(body_node)
        if self.current.terminator is None:
            self._terminate(MirTerminator("jump", targets=(condition_block.block_id,)))

        self._switch_to(exit_block)

    def _lower_match(self, node: HirNode) -> None:
        if len(node.children) < 2:
            raise HirToMirError(f"match node {node.node_id} requires a value and at least one arm")
        value = self.lower_value(self._child(node, 0))
        arms = [self.by_id[child] for child in node.children[1:]]
        if any(arm.kind != "match_arm" for arm in arms):
            raise HirToMirError(
                f"match node {node.node_id} children after the value must be match arms"
            )

        cases: list[int] = []
        case_arms: list[HirNode] = []
        default_arm: HirNode | None = None
        for arm in arms:
            if len(arm.children) != 1 or self._child(arm, 0).kind != "block":
                raise HirToMirError(f"match arm {arm.node_id} requires exactly one block")
            if arm.value is None:
                if default_arm is not None:
                    raise HirToMirError(f"match node {node.node_id} has multiple default arms")
                default_arm = arm
            elif isinstance(arm.value, int):
                cases.append(arm.value)
                case_arms.append(arm)
            else:
                raise HirToMirError(
                    f"match arm {arm.node_id} case value must be an integer or null"
                )
        if default_arm is None:
            raise HirToMirError(f"match node {node.node_id} requires a default arm")
        if len(set(cases)) != len(cases):
            raise HirToMirError(f"match node {node.node_id} has duplicate case values")

        arm_blocks = [self._new_block() for _ in case_arms]
        default_block = self._new_block()
        join_block = self._new_block()
        targets = tuple(block.block_id for block in arm_blocks) + (default_block.block_id,)
        self._terminate(MirTerminator(
            "switch",
            operands=(value,),
            targets=targets,
            cases=tuple(cases),
            span=_span(node),
        ))

        for arm, block in zip(case_arms, arm_blocks):
            self._switch_to(block)
            self._lower_block(self._child(arm, 0))
            if self.current.terminator is None:
                self._terminate(MirTerminator("jump", targets=(join_block.block_id,)))

        self._switch_to(default_block)
        self._lower_block(self._child(default_arm, 0))
        if self.current.terminator is None:
            self._terminate(MirTerminator("jump", targets=(join_block.block_id,)))

        self._switch_to(join_block)

    def lower_statement(self, node: HirNode) -> None:
        if node.kind not in _STATEMENT_KINDS:
            raise HirToMirError(
                f"HIR node {node.node_id} kind {node.kind!r} is not a supported statement"
            )
        if self.current.terminator is not None:
            raise HirToMirError(f"statement node {node.node_id} appears after a terminator")

        if node.kind == "block":
            self._lower_block(node)
        elif node.kind == "if":
            self._lower_if(node)
        elif node.kind == "while":
            self._lower_while(node)
        elif node.kind == "match":
            self._lower_match(node)
        elif node.kind in {"let", "assign"}:
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
            self._emit(
                node,
                "contract_check",
                operands=(condition,),
                contract_kind=node.symbol or "invariant",
            )
        elif node.kind == "capability_scope":
            self._emit(node, "capability_check", capabilities=node.capabilities)
            self._lower_sequence(node.children)
        elif node.kind == "return":
            if len(node.children) > 1:
                raise HirToMirError(f"return node {node.node_id} accepts at most one value")
            operands = ()
            if node.children:
                operands = (self.lower_value(self._child(node, 0)),)
            self._terminate(MirTerminator("return", operands=operands, span=_span(node)))

    def lower(self) -> MirFunction:
        if self.function.kind != "function":
            raise HirToMirError(f"root node {self.function.node_id} is not a function")
        if not self.function.symbol:
            raise HirToMirError(f"function node {self.function.node_id} requires a symbol")

        self._lower_sequence(self.function.children)
        if self.current.terminator is None:
            self._terminate(MirTerminator("return"))

        blocks = tuple(
            MirBlock(
                block.block_id,
                tuple(block.instructions),
                block.terminator or MirTerminator("unreachable"),
            )
            for block in self.blocks
        )
        return MirFunction(
            self.function.symbol,
            _mir_type(self.function.type),
            tuple(self.locals),
            blocks,
            0,
            self.function.capabilities,
        )


def lower_hir_to_mir(module: HirModule) -> MirModule:
    """Lower all function roots in checked HIR into canonical MIR."""

    by_id = {node.node_id: node for node in module.nodes}
    functions = [
        _FunctionLowerer(module, by_id[root_id]).lower()
        for root_id in module.roots
    ]
    return MirModule(module.name, tuple(functions))
