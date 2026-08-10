"""Typed-expression lowering into ``bootstrap-hir-v1``.

The bootstrap HIR boundary is deliberately explicit: callers provide resolved
binding types, function signatures, field signatures, constructor signatures,
and numeric destination types instead of asking this layer to perform inference.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .ast_contract import AstNode
from .hir_contract import HirBinding, HirModule, HirNode, HirType, SourceSpan

_ARITHMETIC_SYMBOLS = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}
_COMPARISON_SYMBOLS = {"equal": "==", "not_equal": "!=", "greater_equal": ">=", "less_equal": "<=", "greater": ">", "less": "<"}
_BOOL = HirType("bool")

class PrimitiveHirLoweringError(ValueError):
    """Raised when an AST node is outside the executable typed HIR slice."""

@dataclass(frozen=True, slots=True)
class HirFunctionSignature:
    symbol: str
    parameters: tuple[HirType, ...]
    result: HirType
    def __post_init__(self) -> None:
        if not self.symbol: raise PrimitiveHirLoweringError("function symbol must be non-empty")

@dataclass(frozen=True, slots=True)
class HirFieldSignature:
    receiver: HirType
    symbol: str
    result: HirType
    def __post_init__(self) -> None:
        if not self.symbol: raise PrimitiveHirLoweringError("field symbol must be non-empty")

@dataclass(frozen=True, slots=True)
class HirConstructorSignature:
    """Resolved aggregate constructor with declaration-order field identities."""
    symbol: str
    result: HirType
    fields: tuple[tuple[str, HirType], ...]
    def __post_init__(self) -> None:
        if not self.symbol: raise PrimitiveHirLoweringError("constructor symbol must be non-empty")
        names = [name for name, _ in self.fields]
        if any(not name for name in names): raise PrimitiveHirLoweringError("constructor field symbol must be non-empty")
        if len(set(names)) != len(names): raise PrimitiveHirLoweringError(f"duplicate constructor field in {self.symbol!r}")

def _span(node: AstNode) -> SourceSpan: return SourceSpan(node.start, node.length)
def _source_text(node: AstNode, source: str) -> str: return source[node.start:node.start + node.length]

def _validated_bindings(bindings):
    lowered=[]; by_name={}
    for binding_id,(name,type_) in enumerate(bindings):
        if not name: raise PrimitiveHirLoweringError("binding name must be non-empty")
        if name in by_name: raise PrimitiveHirLoweringError(f"duplicate resolved binding {name!r}")
        binding=HirBinding(binding_id,name,type_); lowered.append(binding); by_name[name]=binding
    return tuple(lowered),by_name

def _unique(items, label, key):
    result={}
    for item in items:
        k=key(item)
        if k in result: raise PrimitiveHirLoweringError(f"duplicate resolved {label} {k!r}")
        result[k]=item
    return result

def _argument_nodes(node):
    if node.kind != "sequence": return (node,)
    if len(node.children)!=2: raise PrimitiveHirLoweringError("argument sequence requires exactly two children")
    return _argument_nodes(node.children[0])+_argument_nodes(node.children[1])

def _initializer_nodes(node):
    return _argument_nodes(node)

def _lower_expression_hir(node, source, *, expected_type, bindings, functions, fields, constructors, module_name, allow_identifiers, allow_comparisons, allow_calls, allow_fields, allow_constructors):
    if not module_name: raise PrimitiveHirLoweringError("module name must be non-empty")
    if node.start < 0 or node.length < 0 or node.start+node.length > len(source): raise PrimitiveHirLoweringError("AST span is outside source text")
    hir_bindings, bindings_by_name=_validated_bindings(bindings)
    functions_by_symbol=_unique(functions,"function",lambda x:x.symbol)
    fields_by_key=_unique(fields,"field",lambda x:(x.receiver,x.symbol))
    constructors_by_symbol=_unique(constructors,"constructor",lambda x:x.symbol)
    nodes=[]
    def lower(current, contextual_type):
        if current.start<0 or current.length<0 or current.start+current.length>len(source): raise PrimitiveHirLoweringError("AST span is outside source text")
        if current.kind=="exact_numeric":
            if current.children: raise PrimitiveHirLoweringError("numeric literal unexpectedly has children")
            if contextual_type is None: raise PrimitiveHirLoweringError("numeric literal requires an explicit type")
            node_id=len(nodes); nodes.append(HirNode(node_id,"literal",contextual_type,span=_span(current),value=_source_text(current,source),numeric_policy="exact")); return node_id,contextual_type
        if current.kind=="identifier" and allow_identifiers:
            if current.children: raise PrimitiveHirLoweringError("identifier unexpectedly has children")
            name=_source_text(current,source); binding=bindings_by_name.get(name)
            if binding is None: raise PrimitiveHirLoweringError(f"unresolved identifier {name!r}")
            node_id=len(nodes); nodes.append(HirNode(node_id,"identifier",binding.type,span=_span(current),binding_id=binding.binding_id,ownership="value")); return node_id,binding.type
        if current.kind=="call" and allow_calls:
            if len(current.children) not in {1,2}: raise PrimitiveHirLoweringError("call requires callee and optional arguments")
            callee=current.children[0]
            if callee.kind!="identifier" or callee.children: raise PrimitiveHirLoweringError("executable HIR v1 calls require a resolved identifier callee")
            symbol=_source_text(callee,source); signature=functions_by_symbol.get(symbol)
            if signature is None: raise PrimitiveHirLoweringError(f"unresolved function {symbol!r}")
            arguments=() if len(current.children)==1 else _argument_nodes(current.children[1])
            if len(arguments)!=len(signature.parameters): raise PrimitiveHirLoweringError(f"function {symbol!r} expects {len(signature.parameters)} arguments, got {len(arguments)}")
            child_ids=[]
            for argument,parameter_type in zip(arguments,signature.parameters,strict=True):
                child_id,argument_type=lower(argument,parameter_type)
                if argument_type!=parameter_type: raise PrimitiveHirLoweringError(f"argument to {symbol!r} must be {parameter_type.name}, got {argument_type.name}")
                child_ids.append(child_id)
            node_id=len(nodes); nodes.append(HirNode(node_id,"call",signature.result,children=tuple(child_ids),span=_span(current),symbol=symbol,ownership="value")); return node_id,signature.result
        if current.kind=="constructor" and allow_constructors:
            if len(current.children) not in {1,2}: raise PrimitiveHirLoweringError("constructor requires type symbol and optional initializers")
            type_ast=current.children[0]
            if type_ast.kind!="identifier" or type_ast.children: raise PrimitiveHirLoweringError("constructor type must be an identifier")
            symbol=_source_text(type_ast,source); signature=constructors_by_symbol.get(symbol)
            if signature is None: raise PrimitiveHirLoweringError(f"unresolved constructor {symbol!r}")
            initializers=() if len(current.children)==1 else _initializer_nodes(current.children[1])
            provided={}
            for initializer in initializers:
                if initializer.kind!="field_initializer" or len(initializer.children)!=2: raise PrimitiveHirLoweringError("constructor initializer must contain field and value")
                field_ast,value_ast=initializer.children
                if field_ast.kind!="identifier" or field_ast.children: raise PrimitiveHirLoweringError("constructor field name must be an identifier")
                name=_source_text(field_ast,source)
                if name in provided: raise PrimitiveHirLoweringError(f"duplicate constructor initializer {name!r}")
                provided[name]=value_ast
            expected_names=tuple(name for name,_ in signature.fields)
            if set(provided)!=set(expected_names): raise PrimitiveHirLoweringError(f"constructor {symbol!r} requires fields {expected_names!r}")
            child_ids=[]
            for name,field_type in signature.fields:
                child_id,value_type=lower(provided[name],field_type)
                if value_type!=field_type: raise PrimitiveHirLoweringError(f"constructor field {name!r} must be {field_type.name}, got {value_type.name}")
                child_ids.append(child_id)
            node_id=len(nodes); nodes.append(HirNode(node_id,"constructor",signature.result,children=tuple(child_ids),span=_span(current),symbol=symbol,ownership="value")); return node_id,signature.result
        if current.kind=="field" and allow_fields:
            if len(current.children)!=2: raise PrimitiveHirLoweringError("field access requires receiver and field name")
            receiver_ast,field_ast=current.children
            if field_ast.kind!="identifier" or field_ast.children: raise PrimitiveHirLoweringError("field name must be an identifier")
            receiver_id,receiver_type=lower(receiver_ast,None); symbol=_source_text(field_ast,source); signature=fields_by_key.get((receiver_type,symbol))
            if signature is None: raise PrimitiveHirLoweringError(f"unresolved field {receiver_type.name}.{symbol}")
            node_id=len(nodes); nodes.append(HirNode(node_id,"field",signature.result,children=(receiver_id,),span=_span(current),symbol=symbol,ownership="value")); return node_id,signature.result
        symbol=_ARITHMETIC_SYMBOLS.get(current.kind)
        if symbol is not None:
            if len(current.children)!=2: raise PrimitiveHirLoweringError(f"{current.kind} requires exactly two AST children")
            operation_type=expected_type if contextual_type is None else contextual_type
            left,left_type=lower(current.children[0],operation_type); right,right_type=lower(current.children[1],operation_type)
            if left_type!=operation_type or right_type!=operation_type: raise PrimitiveHirLoweringError(f"{current.kind} operands must both be {operation_type.name}")
            node_id=len(nodes); nodes.append(HirNode(node_id,"binary",operation_type,children=(left,right),span=_span(current),symbol=symbol,numeric_policy="checked")); return node_id,operation_type
        symbol=_COMPARISON_SYMBOLS.get(current.kind)
        if symbol is not None and allow_comparisons:
            if len(current.children)!=2: raise PrimitiveHirLoweringError(f"{current.kind} requires exactly two AST children")
            operation_type=expected_type if contextual_type is None else contextual_type
            left,left_type=lower(current.children[0],operation_type); right,right_type=lower(current.children[1],operation_type)
            if left_type!=operation_type or right_type!=operation_type: raise PrimitiveHirLoweringError(f"{current.kind} operands must both be {operation_type.name}")
            node_id=len(nodes); nodes.append(HirNode(node_id,"binary",_BOOL,children=(left,right),span=_span(current),symbol=symbol,numeric_policy="exact")); return node_id,_BOOL
        raise PrimitiveHirLoweringError(f"AST kind {current.kind!r} is outside executable HIR v1")
    root,_=lower(node,expected_type); return HirModule(module_name,hir_bindings,tuple(nodes),(root,))

def lower_primitive_expression_hir(node,source,*,expected_type,module_name="expression"):
    return _lower_expression_hir(node,source,expected_type=expected_type,bindings=(),functions=(),fields=(),constructors=(),module_name=module_name,allow_identifiers=False,allow_comparisons=False,allow_calls=False,allow_fields=False,allow_constructors=False)
def lower_bound_expression_hir(node,source,*,expected_type,bindings,module_name="expression"):
    return _lower_expression_hir(node,source,expected_type=expected_type,bindings=bindings,functions=(),fields=(),constructors=(),module_name=module_name,allow_identifiers=True,allow_comparisons=True,allow_calls=False,allow_fields=False,allow_constructors=False)
def lower_resolved_expression_hir(node,source,*,expected_type,bindings=(),functions=(),fields=(),constructors=(),module_name="expression"):
    """Lower explicitly resolved calls, fields, and aggregate constructors."""
    return _lower_expression_hir(node,source,expected_type=expected_type,bindings=bindings,functions=functions,fields=fields,constructors=constructors,module_name=module_name,allow_identifiers=True,allow_comparisons=True,allow_calls=True,allow_fields=True,allow_constructors=True)
