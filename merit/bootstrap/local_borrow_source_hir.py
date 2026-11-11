"""Fail-closed, checked-source HIR lowering for straight-line RM1 probes.

This is an oracle-side representation producer. It does not authorize the
replacement driver to accept local references.
"""

from __future__ import annotations

from merit.compiler import Checker, parse

from .hir_contract import (
    LOCAL_LOAN_HIR_SCHEMA, HirBinding, HirLocalLoan, HirModule, HirNode,
    HirType, SourceSpan,
)


class LocalBorrowSourceHirError(ValueError):
    """Checked source exceeds this bounded representation producer."""


def lower_checked_local_borrow_source_hir(source: str, function_name: str = "main") -> HirModule:
    """Produce canonical v2 HIR from a checked straight-line source function.

    The supported subset is intentionally explicit: integer literals, local
    bindings, direct one-argument calls, and a value return. Other accepted
    source forms must wait for complete source lowering.
    """
    program = parse(source)
    Checker(program).check()
    function = next((item for item in program.functions if item.name == function_name), None)
    if function is None or function.params or function.pre or function.post or function.requires_caps:
        raise LocalBorrowSourceHirError("unsupported RM1 source function contract")
    if function.return_mode != "value":
        raise LocalBorrowSourceHirError("borrowed returns cannot enter local-loan HIR")
    if function.return_type != "i32":
        raise LocalBorrowSourceHirError("unsupported RM1 source return type")

    line_starts = [0]
    for index, character in enumerate(source):
        if character == "\n":
            line_starts.append(index + 1)

    def span(raw) -> SourceSpan:
        position = program.span(raw)
        if position is None or position.line > len(line_starts) or position.end_line > len(line_starts):
            raise LocalBorrowSourceHirError("missing source span")
        start = line_starts[position.line - 1] + position.column - 1
        end = line_starts[position.end_line - 1] + position.end_column - 1
        return SourceSpan(start, end - start)

    bindings: list[HirBinding] = []
    binding_types: dict[int, HirType] = {}
    nodes: list[HirNode] = []
    loans: list[HirLocalLoan] = []

    def emit(kind: str, type_: HirType, raw, **fields) -> int:
        node_id = len(nodes)
        nodes.append(HirNode(node_id, kind, type_, span=span(raw), **fields))
        return node_id

    def value(raw) -> int:
        node = program.node(raw)
        if node.kind == "number" and node.atom_value.isdigit():
            return emit("literal", HirType("i32"), raw, value=int(node.atom_value))
        if node.kind == "var" and raw.binding_id is not None:
            type_ = binding_types.get(raw.binding_id.serial)
            if type_ is not None:
                return emit("identifier", type_, raw, binding_id=raw.binding_id.serial)
        if node.kind == "call" and len(node.arguments) == 1:
            callee = next((item for item in program.functions if item.name == node.callee_name), None)
            if (callee is not None and callee.return_mode == "value"
                and callee.return_type == "i32" and len(callee.params) == 1
                and callee.params[0].mode == "borrow"):
                argument = value(node.arguments[0])
                if nodes[argument].type.name != callee.params[0].type_name:
                    raise LocalBorrowSourceHirError("borrowed call argument type is not represented")
                return emit("call", HirType("i32"), raw,
                            children=(argument,), symbol=node.callee_name)
        raise LocalBorrowSourceHirError(f"unsupported RM1 source expression: {node.kind}")

    statements: list[int] = []
    for raw in function.body:
        node = program.node(raw)
        if node.kind in {"let", "local_borrow"}:
            binding = raw.binding_id
            if binding is None:
                raise LocalBorrowSourceHirError("unresolved local binding")
            type_ = HirType(node.declared_type)
            if type_.name != "i32":
                raise LocalBorrowSourceHirError("unsupported RM1 source binding type")
            binding_types[binding.serial] = type_
            mode = "local_reference" if node.kind == "local_borrow" else "value"
            bindings.append(HirBinding(binding.serial, binding.name, type_,
                                       node.mutable if node.kind == "let" else False,
                                       mode, span(raw)))
            if node.kind == "local_borrow":
                origin = node.initializer
                if origin.binding_id is None or origin.binding_id.serial not in binding_types:
                    raise LocalBorrowSourceHirError("unresolved local loan origin")
                origin_id = value(origin)
                borrowed = emit("borrow", type_, origin, children=(origin_id,),
                                binding_id=origin.binding_id.serial, ownership="local_reference")
                loans.append(HirLocalLoan(binding.serial, origin.binding_id.serial, span(raw)))
                initializer = borrowed
            else:
                initializer = value(node.initializer)
            statements.append(emit("let", type_, raw, children=(initializer,),
                                   binding_id=binding.serial, ownership=mode))
        elif node.kind == "expr":
            statements.append(value(node.expression))
        elif node.kind == "print":
            printed = value(node.expression)
            statements.append(emit("print", HirType("unit"), raw, children=(printed,)))
        elif node.kind == "assign":
            target = node.assignment_target
            if program.node(target).kind != "var" or target.binding_id is None:
                raise LocalBorrowSourceHirError("unsupported RM1 assignment place")
            type_ = binding_types.get(target.binding_id.serial)
            if type_ != HirType("i32"):
                raise LocalBorrowSourceHirError("unsupported RM1 assignment type")
            initializer = value(node.assigned_value)
            statements.append(emit("assign", type_, raw, children=(initializer,),
                                   binding_id=target.binding_id.serial))
        elif node.kind == "drop":
            binding = raw.binding_id
            if binding is None or binding.serial not in binding_types:
                raise LocalBorrowSourceHirError("unresolved RM1 drop binding")
            statements.append(emit("drop", binding_types[binding.serial], raw,
                                   binding_id=binding.serial))
        elif node.kind == "return":
            result = value(node.expression)
            statements.append(emit("return", HirType(function.return_type), raw,
                                   children=(result,)))
        else:
            raise LocalBorrowSourceHirError(f"unsupported RM1 source statement: {node.kind}")
    if not loans:
        raise LocalBorrowSourceHirError("source function has no local loan")
    return_type = HirType(function.return_type)
    root = emit("function", return_type, function, children=tuple(statements), symbol=function.name)
    return HirModule(program.module, tuple(bindings), tuple(nodes), (root,),
                     LOCAL_LOAN_HIR_SCHEMA, tuple(sorted(loans, key=lambda item: item.reference_binding_id)))
