"""Adapters from Merit-native executable HIR records to canonical HIR."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
from .hir_contract import HirBinding,HirModule,HirNode,HirType,SourceSpan,canonical_hir_json
from .parity import StageObservation,observe
NativeHirRecord=tuple[int,int,int,int,int,int,int,int,int]
_KIND_LITERAL=1; _KIND_ARITHMETIC=2; _KIND_GROUP_ALIAS=3; _KIND_IDENTIFIER=4; _KIND_COMPARISON=5; _KIND_CALL=6; _KIND_FIELD=7; _KIND_ARGUMENT_SEQUENCE=8; _KIND_SYMBOL_REFERENCE=9; _KIND_CONSTRUCTOR=10; _KIND_FIELD_INITIALIZER=11
_TYPE_I64=1; _TYPE_BOOL=2; _POLICY_NONE=0; _POLICY_EXACT=1; _POLICY_CHECKED=2
_SYMBOLS={1:"+",2:"-",3:"*",4:"/",5:"==",6:"!=",7:">=",8:"<=",9:">",10:"<"}
class NativeHirContractError(ValueError): pass

def lower_native_primitive_hir_records(records:Iterable[NativeHirRecord],source:str,*,module_name="expression",type_names:Mapping[int,HirType]|None=None,constructor_fields:Mapping[str,tuple[str,...]]|None=None)->HirModule:
    materialized=tuple(tuple(int(v) for v in r) for r in records)
    if not materialized: raise NativeHirContractError("native HIR record stream is empty")
    if not module_name: raise NativeHirContractError("module name must be non-empty")
    i64=HirType("i64"); bool_type=HirType("bool"); types={1:i64,2:bool_type}
    if type_names:
        for code,type_ in type_names.items():
            if code<=0: raise NativeHirContractError("native HIR type codes must be positive")
            if code in types and types[code]!=type_: raise NativeHirContractError(f"type code {code} has conflicting definitions")
            types[code]=type_
    constructors={} if constructor_fields is None else dict(constructor_fields)
    nodes=[]; native_to_canonical={}; argument_lists={}; symbol_references={}; field_initializers={}; binding_names={}; binding_types={}
    def resolved_type(code,current):
        if code not in types: raise NativeHirContractError(f"record {current} has unsupported type code {code}")
        return types[code]
    def child_id(native_index,current):
        if native_index<0 or native_index>=current: raise NativeHirContractError(f"record {current} has non-postorder child {native_index}")
        if native_index not in native_to_canonical: raise NativeHirContractError(f"record {current} references unresolved value child {native_index}")
        return native_to_canonical[native_index]
    def argument_ids(native_index,current):
        if native_index<0 or native_index>=current: raise NativeHirContractError(f"record {current} has non-postorder argument child {native_index}")
        return argument_lists.get(native_index,(child_id(native_index,current),))
    def symbol_name(native_index,current):
        if native_index<0 or native_index>=current: raise NativeHirContractError(f"record {current} has non-postorder symbol child {native_index}")
        if native_index not in symbol_references: raise NativeHirContractError(f"record {current} references non-symbol record {native_index}")
        return symbol_references[native_index]
    def initializer_entries(native_index,current):
        if native_index<0 or native_index>=current: raise NativeHirContractError(f"record {current} has non-postorder initializer child {native_index}")
        if native_index in argument_lists:
            entries=[]
            for item in argument_lists[native_index]:
                if item not in field_initializers: raise NativeHirContractError(f"record {current} references non-initializer record {item}")
                entries.append(field_initializers[item])
            return tuple(entries)
        if native_index not in field_initializers: raise NativeHirContractError(f"record {current} references non-initializer record {native_index}")
        return (field_initializers[native_index],)
    for index,record in enumerate(materialized):
        if len(record)!=9: raise NativeHirContractError(f"record {index} does not contain nine fields")
        kind,start,length,left,right,symbol_code,type_code,policy_code,binding_id=record
        if start<0 or length<0 or start+length>len(source): raise NativeHirContractError(f"record {index} span is outside source text")
        if kind==_KIND_GROUP_ALIAS:
            if right!=-1 or symbol_code!=0 or policy_code!=0 or binding_id!=-1: raise NativeHirContractError(f"group alias {index} has invalid fields")
            native_to_canonical[index]=child_id(left,index); continue
        if kind==_KIND_SYMBOL_REFERENCE:
            if type_code!=0 or left!=-1 or right!=-1 or symbol_code!=0 or policy_code!=0 or binding_id!=-2: raise NativeHirContractError(f"symbol reference {index} has invalid fields")
            symbol=source[start:start+length]
            if not symbol: raise NativeHirContractError(f"symbol reference {index} is empty")
            symbol_references[index]=symbol; continue
        if kind==_KIND_ARGUMENT_SEQUENCE:
            if type_code!=0 or symbol_code!=0 or policy_code!=0 or binding_id!=-1: raise NativeHirContractError(f"argument sequence {index} has invalid fields")
            argument_lists[index]=argument_ids(left,index)+argument_ids(right,index); continue
        if kind==_KIND_FIELD_INITIALIZER:
            if type_code!=0 or symbol_code!=0 or policy_code!=0 or binding_id!=-1: raise NativeHirContractError(f"field initializer {index} has invalid fields")
            field_initializers[index]=(symbol_name(left,index),child_id(right,index)); continue
        if kind==_KIND_LITERAL:
            type_=resolved_type(type_code,index)
            if left!=-1 or right!=-1 or symbol_code!=0 or binding_id!=-1: raise NativeHirContractError(f"literal record {index} has invalid child/symbol fields")
            if policy_code!=1: raise NativeHirContractError(f"literal record {index} must use exact policy")
            node_id=len(nodes); nodes.append(HirNode(node_id,"literal",type_,span=SourceSpan(start,length),value=source[start:start+length],numeric_policy="exact")); native_to_canonical[index]=node_id; continue
        if kind==_KIND_IDENTIFIER:
            type_=resolved_type(type_code,index)
            if left!=-1 or right!=-1 or symbol_code!=0 or policy_code!=0: raise NativeHirContractError(f"identifier record {index} has invalid fields")
            if binding_id<0: raise NativeHirContractError(f"identifier record {index} has invalid binding ID")
            name=source[start:start+length]
            if binding_id in binding_names and binding_names[binding_id]!=name: raise NativeHirContractError(f"binding {binding_id} resolves both {binding_names[binding_id]!r} and {name!r}")
            if binding_id in binding_types and binding_types[binding_id]!=type_: raise NativeHirContractError(f"binding {binding_id} has inconsistent resolved types")
            binding_names[binding_id]=name; binding_types[binding_id]=type_; node_id=len(nodes); nodes.append(HirNode(node_id,"identifier",type_,span=SourceSpan(start,length),binding_id=binding_id,ownership="value")); native_to_canonical[index]=node_id; continue
        if kind in {_KIND_ARITHMETIC,_KIND_COMPARISON}:
            l=child_id(left,index); r=child_id(right,index); symbol=_SYMBOLS.get(symbol_code)
            if symbol is None: raise NativeHirContractError(f"binary record {index} has unknown symbol code {symbol_code}")
            if binding_id!=-1: raise NativeHirContractError(f"binary record {index} has binding ID")
            if kind==_KIND_ARITHMETIC:
                if type_code!=1 or not 1<=symbol_code<=4: raise NativeHirContractError(f"arithmetic record {index} has invalid type/symbol")
                if policy_code!=2: raise NativeHirContractError(f"arithmetic record {index} must use checked policy")
                result_type=i64; policy="checked"
            else:
                if type_code!=2 or not 5<=symbol_code<=10: raise NativeHirContractError(f"comparison record {index} has invalid type/symbol")
                if policy_code!=1: raise NativeHirContractError(f"comparison record {index} must use exact policy")
                result_type=bool_type; policy="exact"
            node_id=len(nodes); nodes.append(HirNode(node_id,"binary",result_type,children=(l,r),span=SourceSpan(start,length),symbol=symbol,numeric_policy=policy)); native_to_canonical[index]=node_id; continue
        if kind==_KIND_CALL:
            if symbol_code!=0 or policy_code!=0 or binding_id!=-1: raise NativeHirContractError(f"call record {index} has invalid fields")
            result_type=resolved_type(type_code,index); symbol=symbol_name(left,index); arguments=() if right==-1 else argument_ids(right,index); node_id=len(nodes); nodes.append(HirNode(node_id,"call",result_type,children=arguments,span=SourceSpan(start,length),symbol=symbol,ownership="value")); native_to_canonical[index]=node_id; continue
        if kind==_KIND_FIELD:
            if symbol_code!=0 or policy_code!=0 or binding_id!=-1: raise NativeHirContractError(f"field record {index} has invalid fields")
            result_type=resolved_type(type_code,index); receiver=child_id(left,index); symbol=symbol_name(right,index); node_id=len(nodes); nodes.append(HirNode(node_id,"field",result_type,children=(receiver,),span=SourceSpan(start,length),symbol=symbol,ownership="value")); native_to_canonical[index]=node_id; continue
        if kind==_KIND_CONSTRUCTOR:
            if symbol_code!=0 or policy_code!=0 or binding_id!=-1: raise NativeHirContractError(f"constructor record {index} has invalid fields")
            result_type=resolved_type(type_code,index); symbol=symbol_name(left,index); entries=() if right==-1 else initializer_entries(right,index); expected=constructors.get(symbol)
            if expected is None: raise NativeHirContractError(f"constructor {symbol!r} has no explicit field order")
            provided={}
            for name,value in entries:
                if name in provided: raise NativeHirContractError(f"constructor {symbol!r} repeats field {name!r}")
                provided[name]=value
            if set(provided)!=set(expected): raise NativeHirContractError(f"constructor {symbol!r} fields do not match explicit signature")
            children=tuple(provided[name] for name in expected); node_id=len(nodes); nodes.append(HirNode(node_id,"constructor",result_type,children=children,span=SourceSpan(start,length),symbol=symbol,ownership="value")); native_to_canonical[index]=node_id; continue
        raise NativeHirContractError(f"record {index} has unsupported kind {kind}")
    if not nodes: raise NativeHirContractError("native HIR stream contains no semantic nodes")
    if binding_names and sorted(binding_names)!=list(range(max(binding_names)+1)): raise NativeHirContractError("native binding IDs must be dense first-occurrence IDs")
    bindings=tuple(HirBinding(i,binding_names[i],binding_types[i]) for i in sorted(binding_names))
    if len(materialized)-1 not in native_to_canonical: raise NativeHirContractError("final native HIR record is not a semantic value")
    return HirModule(module_name,bindings,tuple(nodes),(native_to_canonical[len(materialized)-1],))

def primitive_hir_parity_observations(case_id,reference,native_records,source,*,type_names=None,constructor_fields=None):
    bootstrap=lower_native_primitive_hir_records(native_records,source,module_name=reference.name,type_names=type_names,constructor_fields=constructor_fields)
    return (observe(case_id,"hir","reference",canonical_hir_json(reference)),observe(case_id,"hir","bootstrap",canonical_hir_json(bootstrap)))
