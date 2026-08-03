from __future__ import annotations

import argparse, contextlib, dataclasses, hashlib, io, json, os, re, subprocess, sys, tempfile
from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_DOWN, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any
from lark import Lark, Transformer, v_args
from lark.exceptions import VisitError

GRAMMAR=r'''
start: module_decl declaration*
module_decl: "module" CNAME
?declaration: enum_decl | trait_decl | impl_decl | decimal_decl | bounded_decl | capability_decl | struct_decl | destructor_decl | function_decl
enum_decl: "enum" CNAME "{" enum_variant ("," enum_variant)* [","] "}"
enum_variant: CNAME ["(" type_ref ")"]
trait_decl: "trait" CNAME "{" trait_method* "}"
trait_method: "fn" CNAME "(" [params] ")" "->" type_ref ";"
impl_decl: "impl" CNAME "for" type_ref "{" impl_method* "}"
impl_method: function_decl
decimal_decl: "decimal" CNAME "(" INT "," INT "," CNAME ")" ";"
bounded_decl: "bounded" CNAME "(" BASE_INT "," SIGNED_NUMBER "," SIGNED_NUMBER ")" ";"
capability_decl: "capability" CNAME ";"
struct_decl: ["stable" "(" ESCAPED_STRING ")"] "struct" CNAME "{" field_decl* "}"
destructor_decl: "destructor" CNAME block
field_decl: CNAME ":" type_ref ";"
function_decl: "fn" CNAME "(" [params] ")" "->" return_ref effects? requires_caps? contract* block
return_ref: "borrow_mut" type_ref -> return_borrow_mut
          | "borrow" type_ref -> return_borrow
          | type_ref -> return_value
params: param ("," param)*
param: "borrow_mut" CNAME ":" type_ref -> param_borrow_mut
     | "borrow" CNAME ":" type_ref -> param_borrow
     | CNAME ":" type_ref -> param_value
effects: "effects" "[" [name_list] "]"
requires_caps: "requires_caps" "[" [name_list] "]"
contract: "requires" expr ";" -> precontract
        | "ensures" expr ";"  -> postcontract
name_list: CNAME ("," CNAME)*
type_ref: CNAME | BASE_INT | "void"
block: "{" statement* "}"
?statement: let_stmt | var_stmt | try_let_stmt | replace_stmt | assign_stmt | return_stmt | print_stmt | expr_stmt | drop_stmt | with_capability | if_stmt | while_stmt | match_stmt
let_stmt: "let" CNAME ":" type_ref "=" expr ";"
var_stmt: "var" CNAME ":" type_ref "=" expr ";"
try_let_stmt: "let" CNAME ":" type_ref "=" "try" expr ";"
assign_stmt: postfix "=" expr ";"
replace_stmt: "replace" "(" postfix "," expr ")" ";"
return_stmt: "return" expr ";"
print_stmt: "print" "(" expr ")" ";"
expr_stmt: expr ";"
drop_stmt: "drop" "(" CNAME ")" ";"
with_capability: "with" "capability" CNAME block
if_stmt: "if" expr block ["else" block]
while_stmt: "while" expr block
match_stmt: "match" "(" expr ")" "{" match_arm+ "}"
match_arm: CNAME ["(" CNAME ")"] "=>" block
?expr: comparison
?comparison: sum (COMP_OP sum)?
?sum: product (ADD_OP product)*
?product: postfix (MUL_OP postfix)*
?postfix: atom ("." CNAME)* -> postfix
?atom: ESCAPED_STRING -> string
     | SIGNED_NUMBER -> number
     | CNAME "{" [field_inits] "}" -> struct_init
     | GENERIC_CALL_HEAD "(" [args] ")" -> generic_call
     | CNAME "(" [args] ")" -> call
     | CNAME -> variable
     | "(" expr ")"
field_inits: field_init ("," field_init)*
field_init: CNAME ":" expr
args: expr ("," expr)*
ADD_OP: "+"|"-"
MUL_OP: "*"|"/"
COMP_OP: "=="|"!="|">="|"<="|">"|"<"
BASE_INT: "i8"|"i16"|"i32"|"i64"|"u8"|"u16"|"u32"|"u64"
GENERIC_CALL_HEAD.2: /[A-Za-z_]\w*<\s*(?:[A-Za-z_]\w*|i8|i16|i32|i64|u8|u16|u32|u64|void)\s*>/
%import common.CNAME
%import common.INT
%import common.SIGNED_NUMBER
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
%ignore /\/\/[^\n]*/
'''
PARSER=Lark(GRAMMAR,parser='lalr',propagate_positions=True)

@dataclasses.dataclass(frozen=True)
class DecimalType: name:str; precision:int; scale:int; rounding:str
@dataclasses.dataclass(frozen=True)
class BoundedType: name:str; base:str; minimum:int; maximum:int
@dataclasses.dataclass(frozen=True)
class EnumVariant: name:str; payload_type:str|None=None
@dataclasses.dataclass(frozen=True)
class EnumType: name:str; variants:tuple[EnumVariant,...]
FS_BUILTIN_ENUMS={
    'FsError':EnumType('FsError',(EnumVariant('FsNotFound'),EnumVariant('FsPermissionDenied'),EnumVariant('FsIoError'))),
    'FileReadResult':EnumType('FileReadResult',(EnumVariant('ReadOk','Buffer'),EnumVariant('ReadErr','FsError'))),
    'FileWriteResult':EnumType('FileWriteResult',(EnumVariant('WriteOk','i64'),EnumVariant('WriteErr','FsError'))),
}
@dataclasses.dataclass(frozen=True)
class Parameter:
    name:str; type_name:str; mode:str='value'
@dataclasses.dataclass(frozen=True)
class TraitMethod: name:str; params:tuple[Parameter,...]; return_type:str
@dataclasses.dataclass(frozen=True)
class TraitType: name:str; methods:tuple[TraitMethod,...]
@dataclasses.dataclass(frozen=True)
class TraitImpl: trait_name:str; target_type:str; methods:tuple[dict[str,Any],...]
@dataclasses.dataclass(frozen=True)
class Field: name:str; type_name:str
@dataclasses.dataclass(frozen=True)
class StructType: name:str; fields:tuple[Field,...]; stable_abi:str|None
@dataclasses.dataclass(frozen=True)
class SourceSpan:
    line:int; column:int; end_line:int; end_column:int; source_name:str|None=None
@dataclasses.dataclass(frozen=True)
class NodeProvenance:
    primary:SourceSpan|None=None; related:SourceSpan|None=None
@dataclasses.dataclass(frozen=True)
class MatchArm:
    variant:str; binding:str|None; body:list
@dataclasses.dataclass(frozen=True)
class DeclarationEntry:
    kind:str; value:Any
@dataclasses.dataclass(frozen=True)
class FieldInitializer:
    name:str; value:SemanticNode
@dataclasses.dataclass(frozen=True)
class FunctionClause:
    kind:str; value:Any
@dataclasses.dataclass(frozen=True)
class ReturnSpec:
    type_name:str; mode:str='value'
@dataclasses.dataclass(frozen=True)
class DestructorDecl:
    type_name:str; body:list; provenance:NodeProvenance=dataclasses.field(default_factory=NodeProvenance,compare=False)
class SemanticNode:
    __slots__=('kind','operands','provenance')
    def __init__(self,kind,*operands):
        object.__setattr__(self,'kind',kind)
        object.__setattr__(self,'operands',tuple(operands))
        object.__setattr__(self,'provenance',NodeProvenance())
    def __repr__(self):return repr((self.kind,*self.operands))
    def __setattr__(self,name,value):raise AttributeError('semantic nodes are immutable')
@dataclasses.dataclass
class FunctionDecl(Mapping):
    name:str;params:list;return_type:str;effects:list;requires_caps:list;pre:list;post:list;body:list;return_mode:str='value';provenance:NodeProvenance=dataclasses.field(default_factory=NodeProvenance,compare=False)
    KEYS=('name','params','return','effects','requires_caps','pre','post','body')
    def __getitem__(self,key):return getattr(self,'return_type' if key=='return' else key)
    def __iter__(self):return iter(self.KEYS)
    def __len__(self):return len(self.KEYS)
    def to_dict(self,serializer=None):
        convert=serializer or (lambda value:value)
        return {**{key:convert(self[key]) for key in self.KEYS},'return_mode':self.return_mode}
    @classmethod
    def from_mapping(cls,value):return cls(*(value[key] for key in cls.KEYS),return_mode=getattr(value,'return_mode','value'))
class AtomNode(SemanticNode):pass
class StringNode(AtomNode):pass
class NumberNode(AtomNode):pass
class VariableNode(AtomNode):pass
class FieldNode(SemanticNode):pass
class ConstructorNode(SemanticNode):pass
class StructInitNode(ConstructorNode):pass
class CallNode(SemanticNode):pass
class DirectCallNode(CallNode):pass
class GenericCallNode(CallNode):pass
class BinaryNode(SemanticNode):pass
class BindingNode(SemanticNode):pass
class LetNode(BindingNode):pass
class TryLetNode(BindingNode):pass
class AssignmentNode(SemanticNode):pass
class AssignNode(AssignmentNode):pass
class ReplaceNode(AssignmentNode):pass
class EffectStatementNode(SemanticNode):pass
class ReturnNode(EffectStatementNode):pass
class PrintNode(EffectStatementNode):pass
class ExpressionStatementNode(EffectStatementNode):pass
class DropNode(EffectStatementNode):pass
class ControlFlowNode(SemanticNode):pass
class CapabilityNode(ControlFlowNode):pass
class IfNode(ControlFlowNode):pass
class WhileNode(ControlFlowNode):pass
class MatchNode(ControlFlowNode):pass
SEMANTIC_STORAGE_TYPES={
    'string':StringNode,'number':NumberNode,'var':VariableNode,'field':FieldNode,
    'struct_init':StructInitNode,'call':DirectCallNode,'generic_call':GenericCallNode,'binop':BinaryNode,
    'let':LetNode,'try_let':TryLetNode,'assign':AssignNode,'replace':ReplaceNode,
    'return':ReturnNode,'print':PrintNode,'expr':ExpressionStatementNode,'drop':DropNode,
    'with_cap':CapabilityNode,'if':IfNode,'while':WhileNode,'match':MatchNode,
}
@dataclasses.dataclass(frozen=True)
class SemanticNodeView:
    raw:SemanticNode; span:SourceSpan|None=None; related_span:SourceSpan|None=None
    @property
    def kind(self)->str:return self.raw.kind
    @property
    def operands(self)->tuple:return self.raw.operands
    def operand(self,index:int):return self.raw.operands[index]
    def require(self,*kinds):
        if self.kind not in kinds:raise ValueError(f'{self.kind} node does not support this accessor')
    @property
    def binding_name(self):self.require('let','try_let','drop');return self.operand(0)
    @property
    def declared_type(self):self.require('let','try_let');return self.operand(1)
    @property
    def initializer(self):self.require('let','try_let');return self.operand(2)
    @property
    def mutable(self):self.require('let');return self.operand(3)
    @property
    def assignment_target(self):self.require('assign','replace');return self.operand(0)
    @property
    def assigned_value(self):self.require('assign','replace');return self.operand(1)
    @property
    def expression(self):self.require('return','print','expr','match');return self.operand(0)
    @property
    def callee_name(self):self.require('call','generic_call');return self.operand(0)
    @property
    def type_argument(self):self.require('generic_call');return self.operand(1)
    @property
    def arguments(self):self.require('call','generic_call');return self.operand(1 if self.kind=='call' else 2)
    @property
    def field_base(self):self.require('field');return self.operand(0)
    @property
    def field_name(self):self.require('field');return self.operand(1)
    @property
    def constructed_type(self):self.require('struct_init');return self.operand(0)
    @property
    def field_values(self):self.require('struct_init');return self.operand(1)
    @property
    def atom_value(self):self.require('string','number','var');return self.operand(0)
    @property
    def operator(self):self.require('binop');return self.operand(0)
    @property
    def left(self):self.require('binop');return self.operand(1)
    @property
    def right(self):self.require('binop');return self.operand(2)
    @property
    def condition(self):self.require('if','while');return self.operand(0)
    @property
    def then_body(self):self.require('if');return self.operand(1)
    @property
    def else_body(self):self.require('if');return self.operand(2)
    @property
    def nested_body(self):self.require('with_cap','while');return self.operand(1)
    @property
    def capability_name(self):self.require('with_cap');return self.operand(0)
    @property
    def match_arms(self):self.require('match');return self.operand(1)
@dataclasses.dataclass
class Program:
    module:str; decimals:dict[str,DecimalType]; bounded:dict[str,BoundedType]; capabilities:set[str]; structs:dict[str,StructType]; functions:list[dict[str,Any]]; enums:dict[str,EnumType]=dataclasses.field(default_factory=dict); traits:dict[str,TraitType]=dataclasses.field(default_factory=dict); impls:list[TraitImpl]=dataclasses.field(default_factory=list); exports:set[str]=dataclasses.field(default_factory=set); destructors:dict[str,DestructorDecl]=dataclasses.field(default_factory=dict)
    def provenance(self,node):
        embedded=getattr(node,'provenance',None)
        return embedded if embedded is not None else NodeProvenance()
    def span(self,node):return self.provenance(node).primary
    def node(self,raw):
        if not isinstance(raw,SemanticNode):return None
        provenance=self.provenance(raw)
        return SemanticNodeView(raw,provenance.primary,provenance.related)

def _impl_function_name(trait_name: str, target_type: str, method_name: str) -> str:
    return 'impl__' + trait_name + '__' + target_type + '__' + method_name

class ASTBuilder(Transformer):
    def __init__(self,source_name=None,line_map=None,related_line_map=None):super().__init__();self.source_name=source_name;self.line_map=line_map or {};self.related_line_map=related_line_map or {}
    def mark(self,node,meta):
        line=self.line_map.get(meta.line,meta.line);end_line=self.line_map.get(meta.end_line,meta.end_line)
        primary=SourceSpan(line,meta.column,end_line,meta.end_column,self.source_name)
        related_span=None
        if meta.line in self.related_line_map:
            related=self.related_line_map[meta.line]
            related_span=SourceSpan(related[0],related[1],related[0],related[2],self.source_name)
        if isinstance(node,(SemanticNode,FunctionDecl)) or dataclasses.is_dataclass(node):object.__setattr__(node,'provenance',NodeProvenance(primary,related_span))
        return node
    def semantic(self,kind,*operands):return SEMANTIC_STORAGE_TYPES[kind](kind,*operands)
    def module_decl(self,x): return str(x[0])
    @v_args(meta=True)
    def enum_variant(self,meta,x): return self.mark(EnumVariant(str(x[0]), x[1] if len(x)>1 else None),meta)
    @v_args(meta=True)
    def enum_decl(self,meta,x): return DeclarationEntry('enum', self.mark(EnumType(str(x[0]), tuple(x[1:])),meta))
    @v_args(meta=True)
    def trait_method(self,meta,x):
        name=str(x[0]); i=1; params=[]
        if i<len(x) and x[i] is None:i+=1
        elif i<len(x) and isinstance(x[i],list):params=x[i];i+=1
        return self.mark(TraitMethod(name, tuple(params), x[i]),meta)
    @v_args(meta=True)
    def trait_decl(self,meta,x): return DeclarationEntry('trait', self.mark(TraitType(str(x[0]), tuple(x[1:])),meta))
    def impl_method(self,x): return x[0].value
    @v_args(meta=True)
    def impl_decl(self,meta,x): return DeclarationEntry('impl', self.mark(TraitImpl(str(x[0]), x[1], tuple(x[2:])),meta))
    @v_args(meta=True)
    def decimal_decl(self,meta,x): return DeclarationEntry('decimal',self.mark(DecimalType(str(x[0]),int(x[1]),int(x[2]),str(x[3])),meta))
    @v_args(meta=True)
    def bounded_decl(self,meta,x): return DeclarationEntry('bounded',self.mark(BoundedType(str(x[0]),str(x[1]),int(Decimal(str(x[2]))),int(Decimal(str(x[3])))),meta))
    def capability_decl(self,x): return DeclarationEntry('capability',str(x[0]))
    def type_ref(self,x): return str(x[0]) if x else 'void'
    def return_borrow_mut(self,x): return ReturnSpec(x[0],'borrow_mut')
    def return_borrow(self,x): return ReturnSpec(x[0],'borrow')
    def return_value(self,x): return ReturnSpec(x[0])
    @v_args(meta=True)
    def field_decl(self,meta,x): return self.mark(Field(str(x[0]),x[1]),meta)
    @v_args(meta=True)
    def struct_decl(self,meta,x):
        x=[v for v in x if v is not None]
        abi=None; i=0
        if x and str(x[0]).startswith('"'): abi=str(x[0])[1:-1]; i=1
        name=str(x[i]); return DeclarationEntry('struct',self.mark(StructType(name,tuple(x[i+1:]),abi),meta))
    @v_args(meta=True)
    def destructor_decl(self,meta,x): return DeclarationEntry('destructor',self.mark(DestructorDecl(str(x[0]),x[1]),meta))
    def param_borrow_mut(self,x): return Parameter(str(x[0]),x[1],'borrow_mut')
    def param_borrow(self,x): return Parameter(str(x[0]),x[1],'borrow')
    def param_value(self,x): return Parameter(str(x[0]),x[1],'value')
    def params(self,x): return list(x)
    def name_list(self,x): return [str(v) for v in x]
    def effects(self,x): return FunctionClause('effects',x[0] if x else [])
    def requires_caps(self,x): return FunctionClause('requires_caps',x[0] if x else [])
    def precontract(self,x): return FunctionClause('pre',x[0])
    def postcontract(self,x): return FunctionClause('post',x[0])
    @v_args(meta=True)
    def string(self,meta,x): return self.mark(self.semantic('string',json.loads(str(x[0]))),meta)
    @v_args(meta=True)
    def number(self,meta,x): return self.mark(self.semantic('number',str(x[0])),meta)
    @v_args(meta=True)
    def variable(self,meta,x): return self.mark(self.semantic('var',str(x[0])),meta)
    def args(self,x): return list(x)
    def field_init(self,x): return FieldInitializer(str(x[0]),x[1])
    def field_inits(self,x): return list(x)
    @v_args(meta=True)
    def struct_init(self,meta,x): return self.mark(self.semantic('struct_init',str(x[0]),{field.name:field.value for field in x[1]} if len(x)>1 else {}),meta)
    @v_args(meta=True)
    def call(self,meta,x): return self.mark(self.semantic('call',str(x[0]),x[1] if len(x)>1 and x[1] is not None else []),meta)
    @v_args(meta=True)
    def generic_call(self,meta,x):
        head=str(x[0])
        match=re.fullmatch(r'([A-Za-z_]\w*)<\s*([A-Za-z_]\w*|i8|i16|i32|i64|u8|u16|u32|u64|void)\s*>',head)
        return self.mark(self.semantic('generic_call',match.group(1),match.group(2),x[1] if len(x)>1 and x[1] is not None else []),meta)
    @v_args(meta=True)
    def postfix(self,meta,x):
        node=x[0]
        for f in x[1:]: node=self.semantic('field',node,str(f))
        return self.mark(node,meta)
    @v_args(meta=True)
    def comparison(self,meta,x): return self.mark(x[0] if len(x)==1 else self.semantic('binop',str(x[1]),x[0],x[2]),meta)
    @v_args(meta=True)
    def sum(self,meta,x):
        n=x[0]
        for i in range(1,len(x),2): n=self.semantic('binop',str(x[i]),n,x[i+1])
        return self.mark(n,meta)
    @v_args(meta=True)
    def product(self,meta,x):
        n=x[0]
        for i in range(1,len(x),2): n=self.semantic('binop',str(x[i]),n,x[i+1])
        return self.mark(n,meta)
    @v_args(meta=True)
    def let_stmt(self,meta,x): return self.mark(self.semantic('let',str(x[0]),x[1],x[2],False),meta)
    @v_args(meta=True)
    def var_stmt(self,meta,x): return self.mark(self.semantic('let',str(x[0]),x[1],x[2],True),meta)
    @v_args(meta=True)
    def try_let_stmt(self,meta,x): return self.mark(self.semantic('try_let',str(x[0]),x[1],x[2]),meta)
    @v_args(meta=True)
    def assign_stmt(self,meta,x): return self.mark(self.semantic('assign',x[0],x[1]),meta)
    @v_args(meta=True)
    def replace_stmt(self,meta,x): return self.mark(self.semantic('replace',x[0],x[1]),meta)
    @v_args(meta=True)
    def return_stmt(self,meta,x): return self.mark(self.semantic('return',x[0]),meta)
    @v_args(meta=True)
    def print_stmt(self,meta,x): return self.mark(self.semantic('print',x[0]),meta)
    @v_args(meta=True)
    def expr_stmt(self,meta,x): return self.mark(self.semantic('expr',x[0]),meta)
    @v_args(meta=True)
    def drop_stmt(self,meta,x): return self.mark(self.semantic('drop',str(x[0])),meta)
    def block(self,x): return list(x)
    @v_args(meta=True)
    def with_capability(self,meta,x): return self.mark(self.semantic('with_cap',str(x[0]),x[1]),meta)
    @v_args(meta=True)
    def if_stmt(self,meta,x): return self.mark(self.semantic('if',x[0],x[1],x[2] if len(x)>2 and x[2] is not None else []),meta)
    @v_args(meta=True)
    def while_stmt(self,meta,x): return self.mark(self.semantic('while',x[0],x[1]),meta)
    def match_arm(self,x): return MatchArm(str(x[0]), str(x[1]) if len(x)==3 and x[1] is not None else None, x[-1])
    @v_args(meta=True)
    def match_stmt(self,meta,x): return self.mark(self.semantic('match',x[0],list(x[1:])),meta)
    @v_args(meta=True)
    def function_decl(self,meta,x):
        name=str(x[0]); i=1; params=[]
        if i<len(x) and x[i] is None:i+=1
        elif i<len(x) and isinstance(x[i],list):params=x[i];i+=1
        ret=x[i];i+=1; effects=[]; caps=[]; pre=[]; post=[]
        while i<len(x)-1:
            clause=x[i]
            if clause.kind=='effects':effects=clause.value
            elif clause.kind=='requires_caps':caps=clause.value
            elif clause.kind=='pre':pre.append(clause.value)
            elif clause.kind=='post':post.append(clause.value)
            i+=1
        return DeclarationEntry('function',self.mark(FunctionDecl(name,params,ret.type_name,effects,caps,pre,post,x[-1],return_mode=ret.mode),meta))
    def start(self,x):
        ds={};bs={};cs=set();ss={};es=dict(FS_BUILTIN_ENUMS);ts={};fs=[];ims=[];destructors={};symbols={name:'builtin' for name in FS_BUILTIN_ENUMS}
        def add_symbol(kind,name,node):
            if name in symbols: raise CompileError(f'M0002: duplicate top-level symbol {name}',getattr(node,'provenance',NodeProvenance()).primary)
            symbols[name]=kind
        for declaration in x[1:]:
            k=declaration.kind;v=declaration.value
            if k in ('decimal','bounded','struct','enum','trait'):
                add_symbol(k,v.name,v)
            elif k=='function':
                add_symbol(k,v['name'],v)
            elif k=='destructor' and v.type_name in destructors:raise CompileError(f'M5500: duplicate destructor for {v.type_name}',v.provenance.primary)
            {'decimal':lambda:ds.__setitem__(v.name,v),'bounded':lambda:bs.__setitem__(v.name,v),'capability':lambda:cs.add(v),'struct':lambda:ss.__setitem__(v.name,v),'enum':lambda:es.__setitem__(v.name,v),'trait':lambda:ts.__setitem__(v.name,v),'impl':lambda:ims.append(v),'function':lambda:fs.append(v),'destructor':lambda:destructors.__setitem__(v.type_name,v)}[k]()
        for impl in ims:
            for method in impl.methods:
                generated=FunctionDecl.from_mapping(method);generated.provenance=getattr(method,'provenance',NodeProvenance());generated.name=_impl_function_name(impl.trait_name,impl.target_type,method.name)
                if generated['name'] in symbols: raise CompileError(f'M0002: duplicate top-level symbol {generated["name"]}')
                fs.append(generated)
        return Program(x[0],ds,bs,cs,ss,fs,es,ts,ims,destructors=destructors)

def _split_generic_args(text: str) -> list[str]:
    args=[]; depth=0; start=0
    for i,ch in enumerate(text):
        if ch=='<': depth+=1
        elif ch=='>': depth-=1
        elif ch==',' and depth==0:
            args.append(text[start:i].strip()); start=i+1
    args.append(text[start:].strip())
    return [a for a in args if a]

def _mangle_generic(name: str, args: list[str]) -> str:
    def clean(x: str) -> str:
        return re.sub(r'[^A-Za-z0-9_]', '_', x)
    return name + '__' + '__'.join(clean(a) for a in args)

def _replace_builtin_vec_types(source: str) -> str:
    changed=True
    while changed:
        changed=False
        def repl(m):
            nonlocal changed
            changed=True
            return _mangle_generic('Vec',[m.group(1).strip()])
        source=re.sub(r'\bVec<([^<>]+)>', repl, source)
    return source

def _extract_generic_templates(source: str):
    templates={}; spans=[]
    header=re.compile(r'\b(enum|struct|fn)\s+([A-Za-z_]\w*)\s*<([^>{}]+)>')
    pos=0
    while True:
        m=header.search(source,pos)
        if not m: break
        brace=source.find('{',m.end())
        if brace<0: break
        depth=0; end=None
        for i in range(brace,len(source)):
            if source[i]=='{': depth+=1
            elif source[i]=='}':
                depth-=1
                if depth==0: end=i+1; break
        if end is None: raise CompileError(f'M7000: unterminated generic {m.group(1)} {m.group(2)}')
        params=[]; bounds={}
        for raw in _split_generic_args(m.group(3)):
            pieces=raw.split(':',1); param=pieces[0].strip(); params.append(param)
            bounds[param]=[x.strip() for x in pieces[1].split('+')] if len(pieces)>1 else []
        templates[m.group(2)]={'kind':m.group(1),'name':m.group(2),'params':params,'bounds':bounds,'text':source[m.start():end],'line':source.count('\n',0,m.start())+1}
        spans.append((m.start(),end)); pos=end
    for a,b in reversed(spans): source=source[:a]+''.join('\n' if ch=='\n' else ' ' for ch in source[a:b])+source[b:]
    return source,templates

def _replace_applications(text: str, templates: dict, requested: set[tuple[str,tuple[str,...]]], request_lines=None, base_line=1) -> str:
    # Qualified enum variants are rewritten before ordinary applications.
    changed=True
    while changed:
        changed=False
        for name in templates:
            pat=re.compile(r'\b'+re.escape(name)+r'<([^<>]+)>::([A-Za-z_]\w*)')
            def qrepl(m):
                nonlocal changed
                args=_split_generic_args(m.group(1)); key=(name,tuple(args));requested.add(key);changed=True
                if request_lines is not None:
                    line=base_line+text.count('\n',0,m.start());line_start=text.rfind('\n',0,m.start())+1
                    request_lines.setdefault(key,(line,m.start()-line_start+1,m.end()-line_start+1))
                return _mangle_generic(name,args)+'__'+m.group(2)
            text=pat.sub(qrepl,text)
        for name in templates:
            pat=re.compile(r'\b'+re.escape(name)+r'<([^<>]+)>')
            def repl(m):
                nonlocal changed
                args=_split_generic_args(m.group(1));key=(name,tuple(args));requested.add(key);changed=True
                if request_lines is not None:
                    line=base_line+text.count('\n',0,m.start());line_start=text.rfind('\n',0,m.start())+1
                    request_lines.setdefault(key,(line,m.start()-line_start+1,m.end()-line_start+1))
                return _mangle_generic(name,args)
            text=pat.sub(repl,text)
    return text

def _extract_trait_impl_registry(source: str) -> set[tuple[str,str]]:
    return {(m.group(1),m.group(2)) for m in re.finditer(r'\bimpl\s+([A-Za-z_]\w*)\s+for\s+([A-Za-z_]\w*)\s*\{', source)}

def _extract_trait_methods(source: str) -> dict[str,set[str]]:
    methods={}; header=re.compile(r'\btrait\s+([A-Za-z_]\w*)\s*\{'); pos=0
    while True:
        m=header.search(source,pos)
        if not m: break
        depth=0; end=None
        for i in range(m.end()-1,len(source)):
            if source[i]=='{': depth+=1
            elif source[i]=='}':
                depth-=1
                if depth==0: end=i+1; break
        if end is None: raise CompileError(f'M7102: unterminated trait {m.group(1)}')
        body=source[m.end():end-1]
        methods[m.group(1)]={x.group(1) for x in re.finditer(r'\bfn\s+([A-Za-z_]\w*)\s*\(', body)}
        pos=end
    return methods

def _generic_trait_satisfied(type_name: str, trait: str, impls: set[tuple[str,str]]) -> bool:
    scalar=set(INT_RANGES)|{'String'}
    if trait in ('Copy','Eq','Ord','Display'): return type_name in scalar
    return (trait,type_name) in impls

def expand_generics(source: str, with_source_map: bool=False, source_name=None):
    source,templates=_extract_generic_templates(source)
    source=_replace_builtin_vec_types(source)
    if not templates:
        expanded=_replace_builtin_vec_types(source)
        return (expanded,{},{}) if with_source_map else expanded
    requested=set()
    request_lines={}
    source=_replace_applications(source,templates,requested,request_lines)
    trait_impls=_extract_trait_impl_registry(source)
    trait_methods=_extract_trait_methods(source)
    generated=[]; generated_origins=[];generated_requests=[]; done=set()
    def expansion_error(text,name,args,template_primary=False):
        request=request_lines.get((name,args))
        template_line=templates[name]['line']
        primary=SourceSpan(template_line,1,template_line,1,source_name)
        if not template_primary and request is not None:primary=SourceSpan(request[0],request[1],request[0],request[2],source_name)
        notes=()
        if template_primary and request is not None:
            notes=(DiagnosticNote('generic instantiated here',SourceSpan(request[0],request[1],request[0],request[2],source_name)),)
        raise CompileError(text,primary,notes)
    while True:
        pending=[x for x in requested if x not in done]
        if not pending: break
        name,args=pending[0]; done.add((name,args)); t=templates[name]
        if len(args)!=len(t['params']): expansion_error(f'M7001: {name} expects {len(t["params"])} type arguments',name,args)
        for param,arg in zip(t['params'],args):
            for trait in t['bounds'].get(param,[]):
                if not _generic_trait_satisfied(arg,trait,trait_impls): expansion_error(f'M7002: type {arg} does not satisfy generic bound {trait} for {name}.{param}',name,args)
        text=t['text']
        # Rewrite declaration header and substitute type parameters token-wise.
        text=re.sub(r'\b'+re.escape(t['kind'])+r'\s+'+re.escape(name)+r'\s*<[^>{}]+>', t['kind']+' '+_mangle_generic(name,list(args)), text, count=1)
        for param,arg in zip(t['params'],args): text=re.sub(r'\b'+re.escape(param)+r'\b',arg,text)
        if t['kind']=='fn':
            rewrite_targets={}
            for param,arg in zip(t['params'],args):
                for trait in t['bounds'].get(param,[]):
                    if trait in ('Copy','Eq','Ord','Display'): continue
                    for method in sorted(trait_methods.get(trait,set()),key=len,reverse=True):
                        target=_impl_function_name(trait,arg,method)
                        if method in rewrite_targets and rewrite_targets[method]!=target:
                            expansion_error(f'M7003: ambiguous trait method {method} in generic {name}',name,args,True)
                        rewrite_targets[method]=target
            for method,target in rewrite_targets.items():
                text=re.sub(r'\b'+re.escape(method)+r'\s*\(', target+'(', text)
        if t['kind']=='enum':
            # Constructor names are nominally scoped by the instantiated enum.
            head_end=text.find('{'); body=text[head_end+1:text.rfind('}')]
            variants=re.findall(r'\b([A-Za-z_]\w*)\s*(?:\(|,|\})', body+',')
            for variant in sorted(set(variants),key=len,reverse=True):
                text=re.sub(r'\b'+re.escape(variant)+r'\b',_mangle_generic(name,list(args))+'__'+variant,text)
        text=_replace_applications(text,templates,requested,request_lines,t['line'])
        generated.append(text);generated_origins.append(t['line']);generated_requests.append(request_lines.get((name,args)))
    expanded=_replace_builtin_vec_types(source+'\n'+'\n'.join(generated)+'\n')
    if not with_source_map:return expanded
    line_map={};related_line_map={}; expanded_line=source.count('\n')+2
    for text,origin,request_line in zip(generated,generated_origins,generated_requests):
        for offset in range(text.count('\n')+1):line_map[expanded_line+offset]=origin+offset
        if request_line is not None:
            for offset in range(text.count('\n')+1):related_line_map[expanded_line+offset]=request_line
        expanded_line+=text.count('\n')+1
    return expanded,line_map,related_line_map

def parse(s:str,source_name=None)->Program:
    expanded,line_map,related_line_map=expand_generics(s,True,source_name)
    try:return ASTBuilder(source_name,line_map,related_line_map).transform(PARSER.parse(expanded))
    except VisitError as exc:
        if isinstance(exc.orig_exc,CompileError):raise exc.orig_exc
        raise
BUILTIN_TYPES={'String','Buffer','Allocator','ByteSlice','I64Vec'}|set(FS_BUILTIN_ENUMS)
VECTOR_INTRINSIC_NAMES=('new','push','len','get','set','replace','pop','drop','transfer','allocator')
ROUNDING={'half_even':ROUND_HALF_EVEN,'half_up':ROUND_HALF_UP,'down':ROUND_DOWN,'ceiling':ROUND_CEILING,'floor':ROUND_FLOOR}
INT_RANGES={'i8':(-2**7,2**7-1),'i16':(-2**15,2**15-1),'i32':(-2**31,2**31-1),'i64':(-2**63,2**63-1),'u8':(0,255),'u16':(0,65535),'u32':(0,2**32-1),'u64':(0,2**64-1)}
@dataclasses.dataclass(frozen=True)
class DiagnosticNote:
    message:str; span:SourceSpan|None=None
class CompileError(Exception):
    def __init__(self,text,span=None,notes=()):
        super().__init__(text);self.text=text;self.span=span;self.notes=tuple(notes)
        match=re.match(r'^(M\d+):\s*(.*)$',text)
        self.code=match.group(1) if match else 'M0000';self.message=match.group(2) if match else text
@dataclasses.dataclass
class TypedValue: type_name:str; value:Any; allocator:Any=None
@dataclasses.dataclass
class VarState:
    type_name:str; mutable:bool; moved:bool=False; dropped:bool=False; mode:str="value"; move_origin:SourceSpan|None=None; move_context:str|None=None; drop_origin:SourceSpan|None=None
@dataclasses.dataclass(frozen=True)
class TypeSemantics:
    owned:bool; needs_drop:bool; copyable:bool; reason:str; kind:str='scalar'; drop_strategy:str='none'
@dataclasses.dataclass(frozen=True)
class FunctionOwnership:
    owned_locals:tuple[tuple[str,str],...]; explicit_drops:frozenset[str]; consumed_roots:frozenset[str]; consumption_sites:tuple[tuple[str,SourceSpan|None],...]=()
@dataclasses.dataclass(frozen=True)
class VecIntrinsic:
    arity:int; return_kind:str; receiver_mode:str|None=None; value_index:int|None=None; index_index:int|None=None; requires_allocate:bool=False; element_policy:str='any'; capability:str|None=None; hazard:str|None=None
    @property
    def rejects_owned_result_copy(self): return self.element_policy=='copy_result'
    @property
    def rejects_owned_replace(self): return self.element_policy=='copy_replace'
    @property
    def requires_owned_element(self): return self.element_policy=='owned_replace'

@dataclasses.dataclass(frozen=True)
class BuiltinSig:
    params:tuple[tuple[str,str],...]; return_type:str; capability:str|None=None; hazard:str|None=None

@dataclasses.dataclass(frozen=True)
class CapabilityPolicy:
    capability:str; hazard_class:str; review:str; scope:str

def is_vec_type(t: str) -> bool:
    return t.startswith('Vec__')

def vec_elem_type(t: str) -> str:
    return t[5:]

def is_owned_type(t: str, p=None) -> bool:
    return type_semantics(t,p).owned

def type_needs_drop(t: str, p=None) -> bool:
    return type_semantics(t,p).needs_drop

def is_copyable_type(t: str, p=None) -> bool:
    return type_semantics(t,p).copyable

def vec_elem_needs_drop(t: str, p) -> bool:
    return type_needs_drop(t,p)

def type_semantics(t: str, p=None, seen=None) -> TypeSemantics:
    return TypeTable(p).get(t,seen)

class TypeTable:
    def __init__(self,p=None): self.p=p;self.cache={}
    def get(self,t,seen=None):
        if seen is None and t in self.cache:return self.cache[t]
        active=set() if seen is None else seen
        if t in active:return TypeSemantics(True,True,False,'recursive aggregate','recursive','aggregate')
        if t=='Buffer': result=TypeSemantics(True,True,False,'owned builtin','builtin','buffer')
        elif t=='I64Vec': result=TypeSemantics(True,True,False,'owned builtin','builtin','i64vec')
        elif is_vec_type(t): result=TypeSemantics(True,True,False,'vector','vector','vector')
        elif self.p is not None and t in self.p.structs:
            child=[self.get(field.type_name,active|{t}) for field in self.p.structs[t].fields]
            custom=t in self.p.destructors;needs=custom or any(x.needs_drop for x in child)
            result=TypeSemantics(True,needs,False,'struct with custom destructor' if custom else ('struct with owned fields' if needs else 'struct'),'struct','aggregate' if needs else 'none')
        elif self.p is not None and t in self.p.enums:
            child=[self.get(v.payload_type,active|{t}) for v in self.p.enums[t].variants if v.payload_type is not None]
            needs=any(x.needs_drop for x in child)
            result=TypeSemantics(needs,needs,not needs,'enum with owned payload' if needs else 'copy enum','enum','aggregate' if needs else 'none')
        else: result=TypeSemantics(False,False,True,'copy scalar')
        if seen is None:self.cache[t]=result
        return result
    def known_types(self):
        names=set(INT_RANGES)|set(BUILTIN_TYPES)
        if self.p is None:return sorted(names)
        names |= set(self.p.decimals)|set(self.p.bounded)|set(self.p.structs)|set(self.p.enums)
        for struct in self.p.structs.values():names.update(field.type_name for field in struct.fields)
        for enum in self.p.enums.values():names.update(variant.payload_type for variant in enum.variants if variant.payload_type)
        def statements(body):
            for statement in body:
                yield statement
                node=self.p.node(statement)
                if node.kind in ('with_cap','while'):yield from statements(node.nested_body)
                elif node.kind=='if':yield from statements(node.then_body);yield from statements(node.else_body)
                elif node.kind=='match':
                    for arm in node.match_arms:yield from statements(arm.body)
        for function in self.p.functions:
            names.add(function.return_type);names.update(param.type_name for param in function.params)
            names.update(self.p.node(statement).declared_type for statement in statements(function.body) if self.p.node(statement).kind in ('let','try_let'))
        names.discard('void')
        return sorted(names)
    def all(self):return {name:dataclasses.asdict(self.get(name)) for name in self.known_types()}

VEC_INTRINSICS={
    'new':VecIntrinsic(2,'vec',requires_allocate=True,capability='allocate',hazard='allocation'),
    'push':VecIntrinsic(2,'void',receiver_mode='borrow_mut',value_index=1),
    'len':VecIntrinsic(1,'i64',receiver_mode='borrow'),
    'get':VecIntrinsic(2,'elem',receiver_mode='borrow',index_index=1,element_policy='copy_result'),
    'set':VecIntrinsic(3,'void',receiver_mode='borrow_mut',value_index=2,index_index=1,element_policy='copy_replace'),
    'replace':VecIntrinsic(3,'void',receiver_mode='borrow_mut',value_index=2,index_index=1,element_policy='owned_replace'),
    'pop':VecIntrinsic(1,'elem',receiver_mode='borrow_mut'),
    'drop':VecIntrinsic(1,'void',receiver_mode='borrow_mut'),
    'transfer':VecIntrinsic(2,'void',receiver_mode='borrow_mut'),
    'allocator':VecIntrinsic(1,'Allocator',receiver_mode='borrow'),
}

BUILTIN_SIGS={
    'system_allocator':BuiltinSig((), 'Allocator'),
    'portable_allocator':BuiltinSig((), 'Allocator'),
    'allocator_compatible':BuiltinSig((('value','Allocator'),('value','Allocator')), 'i32'),
    'string_len':BuiltinSig((('value','String'),), 'i64'),
    'string_byte':BuiltinSig((('value','String'),('value','i64')), 'u8'),
    'buffer_new':BuiltinSig((('value','Allocator'),('value','i64')), 'Buffer', 'allocate', 'allocation'),
    'buffer_from_string':BuiltinSig((('value','Allocator'),('value','String')), 'Buffer', 'allocate', 'allocation'),
    'buffer_push':BuiltinSig((('borrow_mut','Buffer'),('value','u8')), 'void'),
    'buffer_len':BuiltinSig((('borrow','Buffer'),), 'i64'),
    'buffer_get':BuiltinSig((('borrow','Buffer'),('value','i64')), 'i64'),
    'buffer_slice':BuiltinSig((('borrow','Buffer'),('value','i64'),('value','i64')), 'ByteSlice'),
    'buffer_allocator':BuiltinSig((('borrow','Buffer'),), 'Allocator'),
    'slice_len':BuiltinSig((('value','ByteSlice'),), 'i64'),
    'slice_get':BuiltinSig((('value','ByteSlice'),('value','i64')), 'i64'),
    'i64vec_new':BuiltinSig((('value','Allocator'),('value','i64')), 'I64Vec', 'allocate', 'allocation'),
    'i64vec_push':BuiltinSig((('borrow_mut','I64Vec'),('value','i64')), 'void'),
    'i64vec_len':BuiltinSig((('borrow','I64Vec'),), 'i64'),
    'i64vec_get':BuiltinSig((('borrow','I64Vec'),('value','i64')), 'i64'),
    'i64vec_allocator':BuiltinSig((('borrow','I64Vec'),), 'Allocator'),
    'file_read':BuiltinSig((('value','Allocator'),('value','String')), 'FileReadResult', 'file_read', 'filesystem_read'),
    'file_write':BuiltinSig((('value','String'),('borrow','Buffer')), 'FileWriteResult', 'file_write', 'filesystem_write'),
}

CAPABILITY_POLICIES={
    'allocate':CapabilityPolicy('allocate','allocation','memory-resource','lexical'),
    'file_read':CapabilityPolicy('file_read','filesystem_read','io-read','lexical'),
    'file_write':CapabilityPolicy('file_write','filesystem_write','io-write','lexical'),
    'foreign_call':CapabilityPolicy('foreign_call','foreign_call','ffi-boundary','lexical'),
}

def capability_policy(cap: str) -> dict[str,str]:
    policy=CAPABILITY_POLICIES.get(cap,CapabilityPolicy(cap,'user_declared','custom','lexical'))
    return dataclasses.asdict(policy)

def hazard_entry(function: str, operation: str, capability: str, hazard: str|None):
    entry=capability_policy(capability)
    entry.update({'function':function,'operation':operation,'capability':capability,'hazard':hazard or capability})
    return entry

def audit_payload(p,checker):
    return {
        'declared_capabilities':sorted(p.capabilities),
        'capability_policies':[capability_policy(cap) for cap in sorted(p.capabilities)],
        'capability_requirements':capability_requirements(p),
        'sites':checker.audit_sites,
        'calls':checker.call_edges,
        'hazardous_operations':checker.hazardous_operations,
    }

def capability_requirements(p):
    requirements=[]
    for name,sig in BUILTIN_SIGS.items():
        if sig.capability:
            entry=capability_policy(sig.capability)
            entry.update({'kind':'builtin','operation':name,'capability':sig.capability,'hazard':sig.hazard or sig.capability})
            requirements.append(entry)
    for name,spec in VEC_INTRINSICS.items():
        if spec.capability:
            entry=capability_policy(spec.capability)
            entry.update({'kind':'vector_intrinsic','operation':f'vec_{name}<T>','capability':spec.capability,'hazard':spec.hazard or spec.capability})
            requirements.append(entry)
    for f in p.functions:
        for cap in f.requires_caps:
            entry=capability_policy(cap)
            entry.update({'kind':'function','operation':f.name,'capability':cap,'hazard':'user_declared'})
            requirements.append(entry)
    return sorted(requirements,key=lambda x:(x['kind'],x['operation'],x['capability']))

def vec_return_type(op: str, elem: str) -> str:
    kind=VEC_INTRINSICS[op].return_kind
    if kind=='vec': return 'Vec__'+elem
    if kind=='elem': return elem
    return kind

def vec_builtin(name: str):
    for op in VECTOR_INTRINSIC_NAMES:
        prefix=f'vec_{op}__'
        if name.startswith(prefix): return op,name[len(prefix):]
    return None

def generic_vec_call_name(base: str, type_arg: str) -> str|None:
    if not base.startswith('vec_'): return None
    op=base[4:]
    if op not in VEC_INTRINSICS: return None
    return f'vec_{op}__{type_arg}'

def resolved_call(e) -> tuple[str,list]:
    node=e if isinstance(e,SemanticNodeView) else SemanticNodeView(e)
    if node.kind=='call': return node.callee_name,node.arguments
    if node.kind=='generic_call':
        name=generic_vec_call_name(node.callee_name,node.type_argument)
        if name: return name,node.arguments
        raise CompileError(f'M3010: unsupported generic call {node.callee_name}<{node.type_argument}>')
    raise CompileError(f'M3011: expected call expression, got {node.kind}')

class OwnershipEffects:
    def __init__(self,p,types=None): self.p=p;self.types=types or TypeTable(p);self.fn={f.name:f for f in p.functions}
    def root(self,e):
        node=self.p.node(e)
        while node and node.kind=='field':e=node.operand(0);node=self.p.node(e)
        return node.operand(0) if node and node.kind=='var' else None
    def consume(self,e,type_name):
        return set(self.consume_sites(e,type_name))
    def consume_sites(self,e,type_name):
        sites=self.effect_sites(e);root=self.root(e)
        if root and self.types.get(type_name).owned:sites[root]=self.p.span(e)
        return sites
    def effects(self,e):
        return set(self.effect_sites(e))
    def effect_sites(self,e):
        node=self.p.node(e)
        if not node:return {}
        sites={}
        if node.kind=='struct_init':
            struct=self.p.structs[node.constructed_type]
            for field in struct.fields:sites.update(self.consume_sites(node.field_values[field.name],field.type_name))
            return sites
        if node.kind in ('call','generic_call'):
            name,args=resolved_call(e)
            for arg in args:sites.update(self.effect_sites(arg))
            variants=[variant for enum in self.p.enums.values() for variant in enum.variants if variant.name==name]
            if variants and variants[0].payload_type is not None and args:
                sites.update(self.consume_sites(args[0],variants[0].payload_type))
                return sites
            vec=vec_builtin(name)
            if vec:
                op,elem=vec;index=VEC_INTRINSICS[op].value_index
                if index is not None:sites.update(self.consume_sites(args[index],elem))
                return sites
            if name in BUILTIN_SIGS:
                for arg,(mode,type_name) in zip(args,BUILTIN_SIGS[name].params):
                    if mode=='value':sites.update(self.consume_sites(arg,type_name))
                return sites
            if name in self.fn:
                for arg,param in zip(args,self.fn[name].params):
                    if param.mode=='value':sites.update(self.consume_sites(arg,param.type_name))
            return sites
        if node.kind=='binop':
            sites.update(self.effect_sites(node.left));sites.update(self.effect_sites(node.right));return sites
        return sites
    def statements(self,body):
        for statement in body:
            yield statement
            node=self.p.node(statement);kind=node.kind
            if kind in ('with_cap','while'):yield from self.statements(node.nested_body)
            elif kind=='if':
                yield from self.statements(node.then_body);yield from self.statements(node.else_body)
            elif kind=='match':
                for arm in node.match_arms:yield from self.statements(arm.body)
    def expression_type(self,e,env):
        node=self.p.node(e);kind=node.kind
        if kind=='var':return env.get(node.atom_value)
        if kind=='field':
            base=self.expression_type(node.field_base,env);struct=self.p.structs.get(base)
            return next((field.type_name for field in struct.fields if field.name==node.field_name),None) if struct else None
        if kind=='struct_init':return node.constructed_type
        if kind in ('call','generic_call'):
            name,args=resolved_call(e)
            variants=[enum.name for enum in self.p.enums.values() for variant in enum.variants if variant.name==name]
            if variants:return variants[0]
            if name in BUILTIN_SIGS:return BUILTIN_SIGS[name].return_type
            vec=vec_builtin(name)
            if vec:return vec_return_type(*vec)
            if name in self.fn:return self.fn[name].return_type
        return None
    def function(self,f):
        env={param.name:param.type_name for param in f.params};owned=[];explicit=set();consumed_sites={}
        for statement in self.statements(f.body):
            node=self.p.node(statement);tag=node.kind
            if tag=='let':
                consumed_sites.update(self.consume_sites(node.initializer,node.declared_type));env[node.binding_name]=node.declared_type
                if self.types.get(node.declared_type).owned:owned.append((node.binding_name,node.declared_type))
            elif tag=='try_let':
                consumed_sites.update(self.effect_sites(node.initializer));env[node.binding_name]=node.declared_type
                if self.types.get(node.declared_type).owned:owned.append((node.binding_name,node.declared_type))
            elif tag=='assign':consumed_sites.update(self.effect_sites(node.assigned_value))
            elif tag=='replace':
                target_type=self.expression_type(node.assignment_target,env)
                if target_type:consumed_sites.update(self.consume_sites(node.assigned_value,target_type))
            elif tag=='return':consumed_sites.update(self.consume_sites(node.expression,f.return_type))
            elif tag=='match':
                subject_type=self.expression_type(node.expression,env)
                if subject_type:consumed_sites.update(self.consume_sites(node.expression,subject_type))
            elif tag in ('expr','print'):consumed_sites.update(self.effect_sites(node.expression))
            elif tag=='drop':explicit.add(node.binding_name)
        return FunctionOwnership(tuple(owned),frozenset(explicit),frozenset(consumed_sites),tuple(sorted(consumed_sites.items())))

class Checker:
    def __init__(self,p):self.p=p;self.types=TypeTable(p);self.ownership=OwnershipEffects(p,self.types);self.fn={f.name:f for f in p.functions};self.audit_sites=[];self.call_edges=[];self.hazardous_operations=[];self.contract_phase=None
    def fail(self,text,node=None,notes=()):
        provenance=self.p.provenance(node) if node is not None else NodeProvenance()
        if provenance.related:notes=tuple(notes)+(DiagnosticNote('generic instantiated here',provenance.related),)
        raise CompileError(text,provenance.primary,notes)
    def check(self):
        if 'main' not in self.fn:raise CompileError('M0001: program requires fn main')
        for d in self.p.decimals.values():
            if d.precision<1 or d.scale<0 or d.scale>d.precision:self.fail(f'M1001: invalid decimal {d.name}',d)
            if d.rounding not in ROUNDING:self.fail(f'M1002: unsupported rounding policy {d.rounding}',d)
        for b in self.p.bounded.values():
            lo,hi=INT_RANGES[b.base]
            if not(lo<=b.minimum<=b.maximum<=hi):self.fail(f'M1101: bounds for {b.name} exceed {b.base}',b)
        for e in self.p.enums.values():
            if not e.variants: self.fail(f'M6000: enum {e.name} requires at least one variant',e)
            seen_variants=set()
            for variant in e.variants:
                if variant.name in seen_variants: self.fail(f'M6001: duplicate variant {variant.name} in {e.name}',variant)
                seen_variants.add(variant.name)
                if variant.payload_type is not None: self.ensure_type(variant.payload_type,variant)
        for t in self.p.traits.values():
            if not t.methods: self.fail(f'M7100: trait {t.name} requires at least one method',t)
            seen_methods=set()
            for method in t.methods:
                if method.name in seen_methods: self.fail(f'M7101: duplicate method {method.name} in trait {t.name}',method)
                seen_methods.add(method.name)
                self.ensure_trait_signature_type(method.return_type,method)
                for param in method.params: self.ensure_trait_signature_type(param.type_name,method)
        seen_impls=set()
        for impl in self.p.impls:
            trait=self.p.traits.get(impl.trait_name)
            if not trait: self.fail(f'M7200: unknown trait {impl.trait_name}',impl)
            if impl.target_type=='void': self.fail('M7201: cannot implement trait for void',impl)
            self.ensure_type(impl.target_type,impl)
            key=(impl.trait_name,impl.target_type)
            if key in seen_impls: self.fail(f'M7202: duplicate impl {impl.trait_name} for {impl.target_type}',impl)
            seen_impls.add(key)
            self.check_impl_signature(impl,trait)
        for s in self.p.structs.values():
            seen=set()
            for fld in s.fields:
                self.ensure_type(fld.type_name,fld)
                if fld.name in seen:self.fail(f'M4001: duplicate field {fld.name} in {s.name}',fld)
                seen.add(fld.name)
        for destructor in self.p.destructors.values():self.check_destructor(destructor)
        for f in self.p.functions: self.check_function_body(f)
        for impl in self.p.impls:
            for f in impl.methods: self.check_function_body(f)
        return self
    def check_destructor(self,destructor):
        if destructor.type_name not in self.p.structs:self.fail(f'M5501: destructor target must be a struct, got {destructor.type_name}',destructor)
        def statements(body):
            for statement in body:
                yield statement
                node=self.p.node(statement)
                if node.kind in ('with_cap','while'):yield from statements(node.nested_body)
                elif node.kind=='if':yield from statements(node.then_body);yield from statements(node.else_body)
                elif node.kind=='match':
                    for arm in node.match_arms:yield from statements(arm.body)
        for statement in statements(destructor.body):
            if self.p.node(statement).kind not in ('print','expr','assign','if','while'):
                self.fail('M5502: destructor body statement may change ownership or capabilities',statement)
        function=FunctionDecl(f'__destructor_{destructor.type_name}',[Parameter('self',destructor.type_name,'borrow_mut')],'void',[],[],[],[],destructor.body)
        self.check_function_body(function)
    def ensure_type(self,t,node=None):
        if is_vec_type(t):
            self.ensure_type(vec_elem_type(t),node); return
        if t not in INT_RANGES and t not in self.p.decimals and t not in self.p.bounded and t not in self.p.structs and t not in self.p.enums and t not in BUILTIN_TYPES and t!='void':self.fail(f'M3000: unknown type {t}',node)
    def ensure_trait_signature_type(self,t,node=None):
        if t!='Self': self.ensure_type(t,node)
    def check_function_body(self,f):
        self.ensure_type(f.return_type,f)
        if f.return_mode!='value': self.check_borrowed_return(f)
        missing=set(f.requires_caps)-self.p.capabilities
        if missing:self.fail(f"M2001: function {f.name} requires undeclared capabilities: {sorted(missing)}",f)
        env={param.name:VarState(param.type_name,param.mode=='borrow_mut',False,False,param.mode) for param in f.params}
        for e in f.pre:self.check_contract_expr(e,env,set(f.requires_caps),f,'pre')
        self.block(f.body,env,set(f.requires_caps),f)
        if f.return_type!='void' and not self.block_definitely_returns(f.body):
            self.fail(f'M3009: function {f.name} does not return on every path',f)
        post_env=dict(env); post_env['result']=VarState(f.return_type,False)
        for e in f.post:self.check_contract_expr(e,post_env,set(f.requires_caps),f,'post')
    def block_definitely_returns(self,body):
        for statement in body:
            node=self.p.node(statement)
            if node.kind=='return':return True
            if node.kind=='if' and self.block_definitely_returns(node.then_body) and self.block_definitely_returns(node.else_body):return True
            if node.kind=='match' and node.match_arms and all(self.block_definitely_returns(arm.body) for arm in node.match_arms):return True
            if node.kind=='with_cap' and self.block_definitely_returns(node.nested_body):return True
        return False
    def check_borrowed_return(self,f):
        params={param.name:param for param in f.params}
        def returns(body):
            for statement in body:
                node=self.p.node(statement)
                if node.kind=='return':yield statement,node
                elif node.kind in ('with_cap','while'):yield from returns(node.nested_body)
                elif node.kind=='if':yield from returns(node.then_body);yield from returns(node.else_body)
                elif node.kind=='match':
                    for arm in node.match_arms:yield from returns(arm.body)
        found=False;origins=set()
        for statement,node in returns(f.body):
            found=True; expression=self.p.node(node.expression)
            if expression.kind!='var' or expression.atom_value not in params or params[expression.atom_value].mode not in ('borrow','borrow_mut'):
                self.fail('M5300: borrowed return must originate from a borrowed parameter',statement)
            param=params[expression.atom_value]
            origins.add(param.name)
            if f.return_mode=='borrow_mut' and param.mode!='borrow_mut':
                self.fail(f'M5301: borrow_mut return requires borrow_mut parameter {param.name}',statement)
        if not found:self.fail('M5303: borrowed-return function must return a borrowed parameter',f)
        if len(origins)!=1:self.fail('M5305: borrowed return must have one consistent parameter origin',f)
    def borrowed_return_origin(self,f):
        def expressions(body):
            for statement in body:
                node=self.p.node(statement)
                if node.kind=='return':yield node.expression
                elif node.kind in ('with_cap','while'):yield from expressions(node.nested_body)
                elif node.kind=='if':yield from expressions(node.then_body);yield from expressions(node.else_body)
                elif node.kind=='match':
                    for arm in node.match_arms:yield from expressions(arm.body)
        expression=next(expressions(f.body),None)
        node=self.p.node(expression) if expression is not None else None
        return node.atom_value if node and node.kind=='var' else None
    def borrowed_call_mode(self,e):
        node=e if isinstance(e,SemanticNodeView) else self.p.node(e)
        if node.kind not in ('call','generic_call'):return None
        name,_=resolved_call(node);callee=self.fn.get(name)
        return callee.return_mode if callee and callee.return_mode!='value' else None
    def borrowed_field_target_type(self,e,env,caps,fn):
        node=self.p.node(e)
        if node.kind!='field' or not self.borrowed_call_mode(node.field_base):return None
        if self.borrowed_call_mode(node.field_base)!='borrow_mut':self.fail('M5306: shared borrowed return cannot be mutated',node.field_base)
        base_type=self.expr_type(node.field_base,env,caps,fn);struct=self.p.structs.get(base_type)
        if not struct:self.fail(f'M4002: {base_type} has no fields',e)
        field=next((field for field in struct.fields if field.name==node.field_name),None)
        if not field:self.fail(f'M4003: unknown field {node.field_name} on {base_type}',e)
        root=self.root_var(node.field_base)
        if not root or not env[root].mutable:self.fail(f'M5005: borrow_mut argument {root or "<expression>"} is not mutable',node.field_base)
        return field.type_name
    def check_contract_expr(self,e,env,caps,fn,phase):
        previous=self.contract_phase
        self.contract_phase=phase
        try:
            t=self.expr_type(e,env,caps,fn)
        finally:
            self.contract_phase=previous
        if t not in ('i32','number'):
            raise CompileError(f'M3202: {phase}condition must be boolean/comparison, got {t}')
    def check_impl_signature(self,impl,trait):
        expected={m.name:m for m in trait.methods}
        actual={m['name']:m for m in impl.methods}
        if len(actual)!=len(impl.methods): self.fail(f'M7203: duplicate method in impl {impl.trait_name} for {impl.target_type}',impl)
        if set(actual)!=set(expected): self.fail(f'M7204: impl {impl.trait_name} for {impl.target_type} does not match trait methods',impl)
        def subst(type_name): return impl.target_type if type_name=='Self' else type_name
        for name,method in expected.items():
            candidate=actual[name]
            expected_params=[(subst(param.type_name),param.mode) for param in method.params]
            actual_params=[(param.type_name,param.mode) for param in candidate.params]
            if actual_params!=expected_params or candidate.return_type!=subst(method.return_type):
                self.fail(f'M7205: method {name} does not match trait {impl.trait_name} signature for {impl.target_type}',candidate)
            if candidate.effects or candidate.requires_caps:
                self.fail(f'M7206: trait impl method {name} cannot declare effects or capabilities until trait signatures support them',candidate)
    def block(self,body,env,caps,fn):
        for st in body:
            node=self.p.node(st);tag=node.kind
            if tag=='let':
                n=node.binding_name;t=node.declared_type;e=node.initializer;mut=node.mutable;self.ensure_type(t);et=self.expr_type(e,env,caps,fn)
                if self.borrowed_call_mode(e):self.fail('M5304: borrowed return cannot be stored in an owned binding',e)
                if not self.argument_matches(et,t):self.fail(f'M3001: cannot assign {et} to {t} in {n}',st)
                if self.p.node(e).kind=='number':self.validate_literal(t,self.p.node(e).atom_value)
                self.consume_owned_source(e,et,env,f'initializing {n}')
                env[n]=VarState(t,mut)
            elif tag=='try_let':
                n=node.binding_name;t=node.declared_type;e=node.initializer; self.ensure_type(t)
                et=self.expr_type(e,env,caps,fn); enum=self.p.enums.get(et)
                if not enum or [v.name for v in enum.variants] != ['Ok','Err']:
                    self.fail('M6200: try requires an enum with Ok and Err variants',st)
                ok=enum.variants[0]
                if ok.payload_type != t: self.fail(f'M6201: try Ok payload is {ok.payload_type}, binding expects {t}',st)
                ret_enum=self.p.enums.get(fn.return_type)
                if not ret_enum or [v.name for v in ret_enum.variants] != ['Ok','Err']:
                    self.fail('M6202: function using try must return a Result-style enum',st)
                if ret_enum.variants[1].payload_type != enum.variants[1].payload_type:
                    self.fail('M6203: try error payload does not match function return error type',st)
                env[n]=VarState(t,False)
            elif tag=='assign':
                target=node.assignment_target;value=node.assigned_value
                if self.borrowed_call_mode(value):self.fail('M5304: borrowed return cannot be stored in owned storage',value)
                lt=self.borrowed_field_target_type(target,env,caps,fn) or self.lvalue_type(target,env,True);rt=self.expr_type(value,env,caps,fn)
                if not self.argument_matches(rt,lt):self.fail(f'M3006: cannot assign {rt} to {lt}',st)
                if self.p.node(value).kind=='number':self.validate_literal(lt,self.p.node(value).atom_value)
                if self.types.get(lt).needs_drop: self.fail(f'M5201: cannot assign into owned storage {self.expr_path(target)}; drop and create a new owner',st)
                self.consume_owned_source(value,rt,env,f'assigning {self.expr_path(target)}')
            elif tag=='replace':
                target,value=node.assignment_target,node.assigned_value
                lt=self.borrowed_field_target_type(target,env,caps,fn) or self.lvalue_type(target,env,True)
                if not self.types.get(lt).needs_drop: self.fail(f'M5203: replace requires owned storage, got {lt}',st)
                target_root=self.root_var(target)
                rt=self.expr_type(value,env,caps,fn)
                if not self.argument_matches(rt,lt): self.fail(f'M5204: replacement type {rt} does not match {lt}',st)
                value_root=self.root_var(value)
                if value_root==target_root or env[target_root].moved or env[target_root].dropped:
                    self.fail(f'M5202: replacement source aliases target {self.expr_path(target)}',st)
                self.consume_owned_source(value,rt,env,f'replacing {self.expr_path(target)}')
            elif tag=='return':
                et=self.expr_type(node.expression,env,caps,fn)
                if not self.argument_matches(et,fn.return_type):self.fail(f"M3002: return type {et} does not match {fn.return_type}",st)
                if self.p.node(node.expression).kind=='number':self.validate_literal(fn.return_type,self.p.node(node.expression).atom_value)
                if fn.return_mode=='value' and self.borrowed_call_mode(node.expression):self.fail('M5304: borrowed return cannot escape through an owned return',node.expression)
                if fn.return_mode=='value':self.consume_owned_source(node.expression,et,env,f'returning from {fn.name}')
            elif tag in ('print','expr'):self.expr_type(node.expression,env,caps,fn)
            elif tag=='drop':
                n=node.binding_name
                if n not in env: self.fail(f'M5100: cannot drop unknown binding {n}',st)
                if env[n].moved or env[n].dropped:
                    origin=env[n].move_origin or env[n].drop_origin
                    note='value moved here' if env[n].moved else 'value previously dropped here'
                    raise CompileError(f'M5101: binding {n} already consumed',self.p.span(st),(DiagnosticNote(note,origin),))
                if env[n].mode in ('borrow','borrow_mut'): self.fail(f'M5102: cannot drop borrowed parameter {n}',st)
                env[n].dropped=True;env[n].drop_origin=self.p.span(st)
            elif tag=='match':
                subject_t=self.expr_type(node.expression,env,caps,fn); enum=self.p.enums.get(subject_t)
                if not enum: self.fail(f'M6100: match requires enum value, got {subject_t}',st)
                arms=node.match_arms; names=[arm.variant for arm in arms]; expected=[v.name for v in enum.variants]
                if len(names)!=len(set(names)): self.fail('M6101: duplicate match arm',st)
                missing=set(expected)-set(names); extra=set(names)-set(expected)
                if missing or extra: self.fail(f'M6102: non-exhaustive match; missing={sorted(missing)} extra={sorted(extra)}',st)
                states=[]
                for variant in enum.variants:
                    arm=next(arm for arm in arms if arm.variant==variant.name); local={k:dataclasses.replace(v) for k,v in env.items()}
                    binding=arm.binding
                    if variant.payload_type is None and binding is not None: self.fail(f'M6103: variant {variant.name} has no payload',st)
                    if variant.payload_type is not None and binding is None: self.fail(f'M6104: variant {variant.name} requires payload binding',st)
                    if binding is not None: local[binding]=VarState(variant.payload_type,False)
                    self.block(arm.body,local,caps,fn); states.append(local)
                for k in env:
                    env[k].moved=any(state[k].moved for state in states)
                    env[k].dropped=any(state[k].dropped for state in states)
                root=self.root_var(node.expression)
                if root and self.types.get(subject_t).needs_drop:
                    env[root].moved=True;env[root].move_origin=self.p.span(node.expression);env[root].move_context='matching owned enum subject'
            elif tag=='with_cap':
                cap=node.capability_name
                if cap not in self.p.capabilities:self.fail(f'M2002: undeclared capability {cap}',st)
                self.audit_sites.append({'function':fn.name,'capability':cap})
                self.block(node.nested_body,env,caps|{cap},fn)
            elif tag=='if':
                ct=self.expr_type(node.condition,env,caps,fn)
                if ct not in ('i32','number'): self.fail('M3300: if condition must be boolean/comparison',st)
                left={k:dataclasses.replace(v) for k,v in env.items()}; right={k:dataclasses.replace(v) for k,v in env.items()}
                self.block(node.then_body,left,caps,fn); self.block(node.else_body,right,caps,fn)
                for k in env:
                    env[k].moved=left[k].moved or right[k].moved
                    env[k].dropped=left[k].dropped or right[k].dropped
                    env[k].move_origin=left[k].move_origin or right[k].move_origin
                    env[k].move_context=left[k].move_context or right[k].move_context
                    env[k].drop_origin=left[k].drop_origin or right[k].drop_origin
            elif tag=='while':
                ct=self.expr_type(node.condition,env,caps,fn)
                if ct not in ('i32','number'): self.fail('M3301: while condition must be boolean/comparison',st)
                loop={k:dataclasses.replace(v) for k,v in env.items()}; self.block(node.nested_body,loop,caps,fn)
                for k in env:
                    env[k].moved=env[k].moved or loop[k].moved
                    env[k].dropped=env[k].dropped or loop[k].dropped
                    env[k].move_origin=env[k].move_origin or loop[k].move_origin
                    env[k].move_context=env[k].move_context or loop[k].move_context
                    env[k].drop_origin=env[k].drop_origin or loop[k].drop_origin
    def lvalue_type(self,e,env,write=False):
        node=self.p.node(e);kind=node.kind
        if kind=='var':
            n=node.atom_value
            if n not in env:self.fail(f'M3003: unknown variable {n}',e)
            if env[n].moved:
                context=f' ({env[n].move_context})' if env[n].move_context else ''
                raise CompileError(f'M5001: use of moved value {n}',self.p.span(e),(DiagnosticNote(f'value moved here{context}',env[n].move_origin),))
            if env[n].dropped:raise CompileError(f'M5103: use of dropped value {n}',self.p.span(e),(DiagnosticNote('value dropped here',env[n].drop_origin),))
            if write and not env[n].mutable:self.fail(f'M5002: cannot assign to immutable binding {n}',e)
            return env[n].type_name
        if kind=='field':
            base=node.field_base;bt=self.lvalue_type(base,env,write);s=self.p.structs.get(bt)
            if not s:self.fail(f'M4002: {bt} has no fields',e)
            for fld in s.fields:
                if fld.name==node.field_name:return fld.type_name
            self.fail(f'M4003: unknown field {node.field_name} on {bt}',e)
        self.fail('M3007: invalid assignment target',e)
    def expr_type(self,e,env,caps,fn):
        node=self.p.node(e);tag=node.kind
        if tag=='string':return 'String'
        if tag=='number':return 'number'
        if tag=='var':return self.lvalue_type(e,env)
        if tag=='field':
            base=self.p.node(node.field_base)
            if base.kind in ('call','generic_call') and self.borrowed_call_mode(base):
                bt=self.expr_type(node.field_base,env,caps,fn);struct=self.p.structs.get(bt)
                if not struct:self.fail(f'M4002: {bt} has no fields',e)
                field=next((field for field in struct.fields if field.name==node.field_name),None)
                if field:return field.type_name
                self.fail(f'M4003: unknown field {node.field_name} on {bt}',e)
            return self.lvalue_type(e,env)
        if tag=='struct_init':
            name,vals=node.constructed_type,node.field_values;s=self.p.structs.get(name)
            if not s:self.fail(f'M4004: unknown struct {name}',e)
            expected={f.name:f for f in s.fields}
            if set(vals)!=set(expected):self.fail(f'M4005: {name} fields must be {sorted(expected)}',e)
            for n,x in vals.items():
                t=self.expr_type(x,env,caps,fn)
                if not self.argument_matches(t,expected[n].type_name):self.fail(f'M4006: field {n} expects {expected[n].type_name}, got {t}',x)
                value_node=self.p.node(x)
                if value_node.kind=='number':self.validate_literal(expected[n].type_name,value_node.atom_value)
                self.consume_owned_source(x,t,env,f'initializing field {name}.{n}')
            return name
        if tag in ('call','generic_call'):
            name,args=resolved_call(e)
            variants=[(enum,variant) for enum in self.p.enums.values() for variant in enum.variants if variant.name==name]
            if variants:
                if len(variants)>1: self.fail(f'M6002: ambiguous enum constructor {name}',e)
                enum,variant=variants[0]
                expected_count=0 if variant.payload_type is None else 1
                if len(args)!=expected_count: self.fail(f'M6003: {name} expects {expected_count} arguments',e)
                if expected_count:
                    at=self.expr_type(args[0],env,caps,fn)
                    if not self.argument_matches(at,variant.payload_type): self.fail(f'M6004: {name} expects {variant.payload_type}, got {at}',args[0])
                    argument_node=self.p.node(args[0])
                    if argument_node.kind=='number': self.validate_literal(variant.payload_type,argument_node.atom_value)
                    self.consume_owned_source(args[0],at,env,f'constructing {enum.name}::{variant.name}')
                return enum.name
            if name=='old':
                if self.contract_phase!='post': self.fail('M3201: old() is only valid in postconditions',e)
                if len(args)!=1: self.fail('M3200: old expects one argument',e)
                return self.expr_type(args[0],env,caps,fn)
            if name in ('checked_add','checked_sub','checked_mul','decimal_div'):
                if name=='decimal_div' and len(args)!=2:raise CompileError('M1301: decimal_div expects 2 arguments')
                if name!='decimal_div' and len(args)!=2:raise CompileError(f'M3100: {name} expects 2 arguments')
                a=self.expr_type(args[0],env,caps,fn);b=self.expr_type(args[1],env,caps,fn)
                if a=='number':a=b
                if b=='number':b=a
                if a!=b:raise CompileError(f'M3101: {name} operands differ: {a} and {b}')
                if name=='decimal_div' and a not in self.p.decimals:raise CompileError('M1302: decimal_div requires decimal operands')
                return a
            vec=vec_builtin(name)
            if vec:
                op,elem=vec; spec=VEC_INTRINSICS[op]; vec_t='Vec__'+elem; self.ensure_type(vec_t)
                if len(args)!=spec.arity: self.fail(f'M3005: {name} expects {spec.arity} arguments',e)
                if spec.capability:
                    if spec.capability not in caps: self.fail(f'M2003: call to {name} requires capabilities [{spec.capability}]',e)
                    self.hazardous_operations.append(hazard_entry(fn.name,name,spec.capability,spec.hazard))
                    if self.expr_type(args[0],env,caps,fn)!='Allocator': raise CompileError(f'M3008: argument 0 expects Allocator')
                    cap_t=self.expr_type(args[1],env,caps,fn)
                    if cap_t not in ('i64','number'): raise CompileError(f'M3008: argument 1 expects i64, got {cap_t}')
                    return vec_return_type(op,elem)
                if spec.receiver_mode:
                    self.check_vec_receiver(args[0],env,caps,fn,vec_t,spec.receiver_mode)
                if op=='transfer':
                    self.check_vec_receiver(args[1],env,caps,fn,vec_t,'borrow_mut')
                    destination=self.root_var(args[0]);source=self.root_var(args[1])
                    if destination==source:self.fail(f'M7305: vector transfer source aliases destination {destination}',e)
                element=self.types.get(elem)
                if spec.element_policy=='copy_result' and element.needs_drop:
                    raise CompileError(f'M7301: {name} cannot copy owned element {elem}; use pop')
                if spec.element_policy=='copy_replace' and element.needs_drop:
                    raise CompileError(f'M7302: {name} cannot replace owned element {elem}')
                if spec.element_policy=='owned_replace' and not element.needs_drop:
                    raise CompileError(f'M7304: {name} requires an owned element type, got {elem}')
                if spec.index_index is not None:
                    it=self.expr_type(args[spec.index_index],env,caps,fn)
                    if it not in ('i64','number'): raise CompileError(f'M3008: argument {spec.index_index} expects i64, got {it}')
                if spec.value_index is not None:
                    value_arg=args[spec.value_index]
                    if self.borrowed_call_mode(value_arg):self.fail('M5304: borrowed return cannot be moved into a vector',value_arg)
                    receiver_root=self.root_var(args[0])
                    if op=='replace' and receiver_root in self.referenced_roots(value_arg):
                        raise CompileError(f'M7303: replacement source aliases vector {receiver_root}')
                    at=self.expr_type(value_arg,env,caps,fn)
                    if not self.argument_matches(at,elem): self.fail(f'M3008: vector value expects {elem}, got {at}',value_arg)
                    if self.p.node(value_arg).kind=='number':self.validate_literal(elem,self.p.node(value_arg).atom_value)
                    self.consume_owned_source(value_arg,at,env,f'calling {name}')
                if op=='drop':
                    root=self.root_var(args[0])
                    if root: env[root].dropped=True;env[root].drop_origin=self.p.span(args[0])
                return vec_return_type(op,elem)
            if name in BUILTIN_SIGS:
                sig=BUILTIN_SIGS[name]; params=sig.params; ret=sig.return_type; cap=sig.capability
                if cap and cap not in caps: self.fail(f'M2003: call to {name} requires capabilities {[cap]}',e)
                if cap: self.hazardous_operations.append(hazard_entry(fn.name,name,cap,sig.hazard))
                if len(args)!=len(params): self.fail(f'M3005: {name} expects {len(params)} arguments',e)
                loans=[]
                for idx,(arg,(mode,pt)) in enumerate(zip(args,params)):
                    at=self.expr_type(arg,env,caps,fn)
                    if mode=='value' and self.borrowed_call_mode(arg):self.fail('M5304: borrowed return cannot be passed by value',arg)
                    if mode=='borrow_mut' and self.borrowed_call_mode(arg)=='borrow':self.fail('M5306: shared borrowed return cannot satisfy borrow_mut',arg)
                    if not self.argument_matches(at,pt): self.fail(f'M3008: argument {idx} expects {pt}, got {at}',arg)
                    if self.p.node(arg).kind=='number':self.validate_literal(pt,self.p.node(arg).atom_value)
                    root=self.root_var(arg)
                    if mode in ('borrow','borrow_mut'):
                        if not root: raise CompileError(f'M5004: {mode} argument must be addressable')
                        if mode=='borrow_mut' and not env[root].mutable: raise CompileError(f'M5005: borrow_mut argument {root} is not mutable')
                        for pr,pm in loans:
                            if pr==root and ('borrow_mut' in (mode,pm)): raise CompileError(f'M5003: conflicting loans of {root}')
                        loans.append((root,mode))
                    if mode=='value': self.consume_owned_source(arg,at,env,f'passing argument {idx} to {name}')
                return ret
            if name not in self.fn:self.fail(f'M3004: unknown function {name}',e)
            callee=self.fn[name];missing=set(callee.requires_caps)-caps
            self.call_edges.append({'caller':fn.name,'callee':name,'required':callee.requires_caps})
            if missing:self.fail(f"M2003: call to {name} requires capabilities {sorted(missing)}",e)
            if len(args)!=len(callee.params):self.fail(f"M3005: {name} expects {len(callee.params)} arguments",e)
            loans=[]
            for arg,param in zip(args,callee.params):
                at=self.expr_type(arg,env,caps,fn)
                if param.mode=='value' and self.borrowed_call_mode(arg):self.fail('M5304: borrowed return cannot be passed by value',arg)
                if param.mode=='borrow_mut' and self.borrowed_call_mode(arg)=='borrow':self.fail('M5306: shared borrowed return cannot satisfy borrow_mut',arg)
                if not self.argument_matches(at,param.type_name):self.fail(f'M3008: argument {param.name} expects {param.type_name}, got {at}',arg)
                if self.p.node(arg).kind=='number':self.validate_literal(param.type_name,self.p.node(arg).atom_value)
                root=self.root_var(arg)
                if root and param.mode in ('borrow','borrow_mut'):
                    for previous_root,previous_mode,previous_param in loans:
                        if root==previous_root and ('borrow_mut' in (param.mode,previous_mode)):
                            raise CompileError(f'M5003: conflicting loans of {root} for {previous_param} and {param.name}')
                    loans.append((root,param.mode,param.name))
                if param.mode=='borrow_mut':
                    if not root: raise CompileError(f'M5004: borrow_mut argument {param.name} must be an addressable binding')
                    if not env[root].mutable: raise CompileError(f'M5005: borrow_mut argument {root} is not mutable')
                if param.mode=='value':self.consume_owned_source(arg,at,env,f'passing argument {param.name} to {name}')
            return callee.return_type
        if tag=='binop':
            a=self.expr_type(node.left,env,caps,fn);b=self.expr_type(node.right,env,caps,fn)
            if node.operator in ('==','!=','>=','<=','>','<'):return 'i32'
            if a=='number':return b
            if b=='number':return a
            if a!=b:self.fail(f'M3102: arithmetic operands differ: {a} and {b}',e)
            return a
        self.fail(f'M3999: unsupported expression {e}',e)
    def check_vec_receiver(self,arg,env,caps,fn,vec_t,mode):
        at=self.expr_type(arg,env,caps,fn)
        if at!=vec_t: raise CompileError(f'M3008: vector argument expects {vec_t}, got {at}')
        if mode=='borrow_mut' and self.borrowed_call_mode(arg)=='borrow':self.fail('M5306: shared borrowed return cannot satisfy borrow_mut',arg)
        root=self.root_var(arg)
        if not root: raise CompileError(f'M5004: {mode} argument must be addressable')
        if mode=='borrow_mut' and not env[root].mutable: raise CompileError(f'M5005: borrow_mut argument {root} is not mutable')
    def consume_owned_source(self,e,t,env,context):
        root=self.root_var(e)
        if not root or not self.types.get(t).owned: return
        if self.p.node(e).kind=='field': raise CompileError(f'M5200: cannot move owned field {self.expr_path(e)} while {context}; move or drop the owning aggregate {root}')
        if env[root].mode in ('borrow','borrow_mut'): raise CompileError(f'M5102: cannot move borrowed parameter {root}')
        env[root].moved=True;env[root].move_origin=self.p.span(e);env[root].move_context=context
    def expr_path(self,e):
        node=self.p.node(e)
        if node.kind=='var': return node.operand(0)
        if node.kind=='field': return self.expr_path(node.field_base)+'.'+node.field_name
        return '<expression>'
    def root_var(self,e):
        node=self.p.node(e)
        while node and node.kind=='field':e=node.field_base;node=self.p.node(e)
        if node and node.kind in ('call','generic_call'):
            name,args=resolved_call(node);callee=self.fn.get(name)
            if callee and callee.return_mode!='value':
                origin=self.borrowed_return_origin(callee)
                index=next((index for index,param in enumerate(callee.params) if param.name==origin),None)
                if index is not None:return self.root_var(args[index])
        return node.operand(0) if node and node.kind=='var' else None
    def referenced_roots(self,e):
        if not isinstance(e,SemanticNode): return set()
        root=self.root_var(e)
        if root: return {root}
        roots=set()
        for part in self.p.node(e).operands:
            if isinstance(part,SemanticNode): roots |= self.referenced_roots(part)
            elif isinstance(part,list):
                for item in part: roots |= self.referenced_roots(item)
            elif isinstance(part,dict):
                for item in part.values(): roots |= self.referenced_roots(item)
        return roots
    def validate_literal(self,t,text):
        if t in self.p.decimals:
            d=self.p.decimals[t];v=Decimal(text);q=Decimal(1).scaleb(-d.scale)
            if v.quantize(q)!=v:raise CompileError(f'M1003: literal {text} exceeds scale {d.scale} for {t}; explicit rounding required')
            digits=len(v.as_tuple().digits)
            if digits>d.precision:raise CompileError(f'M1004: literal {text} exceeds precision {d.precision} for {t}')
        elif t in self.p.bounded:
            v=int(Decimal(text));b=self.p.bounded[t]
            if Decimal(text)!=v:raise CompileError(f'M1102: non-integer literal for {t}')
            if not b.minimum<=v<=b.maximum:raise CompileError(f'M1103: {v} outside {t} range {b.minimum}..{b.maximum}')
        elif t in INT_RANGES:
            v=int(Decimal(text));lo,hi=INT_RANGES[t]
            if Decimal(text)!=v or not lo<=v<=hi:raise CompileError(f'M1201: literal {text} invalid for {t}')
    def argument_matches(self,actual,expected):
        return actual==expected or (actual=='number' and (expected in INT_RANGES or expected in self.p.decimals or expected in self.p.bounded))

class LayoutEngine:
    SIZES={'i8':(1,1),'u8':(1,1),'i16':(2,2),'u16':(2,2),'i32':(4,4),'u32':(4,4),'i64':(8,8),'u64':(8,8)}
    def __init__(self,p):self.p=p
    def hash_layout(self,kind,data):
        canonical=json.dumps({'kind':kind,**data},sort_keys=True,separators=(',',':'))
        return hashlib.sha256(canonical.encode()).hexdigest()[:24]
    def vec_types(self):
        found=set()
        def add(t):
            if is_vec_type(t):
                found.add(t); add(vec_elem_type(t))
        for s in self.p.structs.values():
            for f in s.fields: add(f.type_name)
        for e in self.p.enums.values():
            for v in e.variants:
                if v.payload_type: add(v.payload_type)
        for f in self.p.functions:
            add(f.return_type)
            for param in f.params: add(param.type_name)
            for st in CGenerator(self.p).walk_statements(f.body):
                node=self.p.node(st)
                if node.kind in ('let','try_let'): add(node.declared_type)
        return sorted(found,key=lambda name:(name.count('Vec__'),name))
    def size_align(self,t):
        if t in self.SIZES:return self.SIZES[t]
        if t in self.p.decimals:return (8,8) if self.p.decimals[t].precision<=18 else (16,16)
        if t in self.p.bounded:return self.size_align(self.p.bounded[t].base)
        if t in ('String','ByteSlice'): return (16,8)
        if t=='Buffer': return (32,8)
        if t=='I64Vec': return (32,8)
        if is_vec_type(t): return (32,8)
        if t=='Allocator': return (4,4)
        if t in self.p.structs:
            x=self.struct_layout(self.p.structs[t]);return x['size'],x['alignment']
        if t in self.p.enums:
            x=self.enum_layout(self.p.enums[t]);return x['size'],x['alignment']
        raise CompileError(f'layout unavailable for {t}')
    def struct_layout(self,s):
        off=0;align=1;fields=[]
        for f in s.fields:
            sz,al=self.size_align(f.type_name);off=(off+al-1)//al*al
            fields.append({'name':f.name,'type':f.type_name,'offset':off,'size':sz,'alignment':al});off+=sz;align=max(align,al)
        size=(off+align-1)//align*align
        data={'name':s.name,'abi':s.stable_abi,'size':size,'alignment':align,'fields':fields}
        return {'kind':'struct',**data,'layout_hash':self.hash_layout('struct',data)}
    def layout(self,s): return self.struct_layout(s)
    def vec_layout(self,t):
        elem=vec_elem_type(t)
        data={'name':t,'element_type':elem,'size':32,'alignment':8,'fields':[
            {'name':'data','type':elem+'*','offset':0,'size':8,'alignment':8},
            {'name':'len','type':'usize','offset':8,'size':8,'alignment':8},
            {'name':'cap','type':'usize','offset':16,'size':8,'alignment':8},
            {'name':'allocator','type':'Allocator','offset':24,'size':4,'alignment':4},
        ]}
        return {'kind':'vector',**data,'layout_hash':self.hash_layout('vector',data)}
    def enum_layout(self,e):
        payloads=[]
        max_size=0;max_align=1
        for variant in e.variants:
            if variant.payload_type is None:
                payloads.append({'variant':variant.name,'type':None,'size':0,'alignment':1})
            else:
                sz,al=self.size_align(variant.payload_type);max_size=max(max_size,sz);max_align=max(max_align,al)
                payloads.append({'variant':variant.name,'type':variant.payload_type,'size':sz,'alignment':al})
        tag={'type':'i32','offset':0,'size':4,'alignment':4}
        align=max(4,max_align)
        payload_offset=((4+max_align-1)//max_align*max_align) if max_size else None
        size=4 if max_size==0 else (payload_offset+max_size+align-1)//align*align
        data={'name':e.name,'size':size,'alignment':align,'tag':tag,'payload_offset':payload_offset,'payload_size':max_size,'payload_alignment':max_align,'variants':payloads}
        return {'kind':'enum',**data,'layout_hash':self.hash_layout('enum',data)}
    def all(self):
        return [self.struct_layout(s) for s in self.p.structs.values()] + [self.enum_layout(e) for e in self.p.enums.values()] + [self.vec_layout(vt) for vt in self.vec_types()]

@dataclasses.dataclass
class ReturnSignal:
    value:TypedValue

@dataclasses.dataclass
class TrySignal:
    value:TypedValue

class Interpreter:
    def __init__(self,p):self.p=p;self.types=TypeTable(p);self.fn={f.name:f for f in p.functions};self.call_modes=[]
    def run(self):return self.call('main',[])
    def call(self,n,args):
        f=self.fn[n];env={param.name:v for param,v in zip(f.params,args)}
        self.call_modes.append({param.name:param.mode for param in f.params})
        try:
            for c in f.pre:
                if not self.eval(c,env).value:raise RuntimeError(f'precondition failed in {n}')
            before={k:self.clone(v) for k,v in env.items()}
            sig=self.block(f.body,env); r=sig.value if isinstance(sig,(ReturnSignal,TrySignal)) else TypedValue('void',None)
            post_env=dict(env); post_env['result']=r; post_env['__old__']=before
            for c in f.post:
                if not self.eval(c,post_env).value:raise RuntimeError(f'postcondition failed in {n}')
            ownership=OwnershipEffects(self.p,self.types).function(f)
            for name,type_name in reversed(ownership.owned_locals):
                if name in env and name not in ownership.explicit_drops and name not in ownership.consumed_roots:
                    self.drop_value(env.pop(name))
            return r
        finally:
            self.call_modes.pop()
    def block(self,b,env):
        for st in b:
            node=self.p.node(st);kind=node.kind
            if kind=='let':env[node.binding_name]=self.eval(node.initializer,env,node.declared_type)
            elif kind=='try_let':
                value=self.eval(node.initializer,env); enum=self.p.enums[value.type_name]
                if value.value['variant']=='Err': return TrySignal(value)
                env[node.binding_name]=value.value['payload']
            elif kind=='assign':self.assign(node.assignment_target,self.eval(node.assigned_value,env),env)
            elif kind=='replace':
                replacement=self.eval(node.assigned_value,env);self.drop_value(self.eval(node.assignment_target,env));self.assign(node.assignment_target,replacement,env)
            elif kind=='print':print(self.format(self.eval(node.expression,env)))
            elif kind=='return':return ReturnSignal(self.eval(node.expression,env))
            elif kind=='expr':self.eval(node.expression,env)
            elif kind=='drop': self.drop_value(env.pop(node.binding_name,None))
            elif kind=='match':
                value=self.eval(node.expression,env); variant=value.value['variant']
                arm=next(arm for arm in node.match_arms if arm.variant==variant)
                if arm.binding is not None: env[arm.binding]=value.value['payload']
                r=self.block(arm.body,env)
                if isinstance(r,(ReturnSignal,TrySignal)):return r
            elif kind=='with_cap':
                r=self.block(node.nested_body,env)
                if isinstance(r,(ReturnSignal,TrySignal)):return r
            elif kind=='if':
                branch=node.then_body if self.eval(node.condition,env).value else node.else_body
                r=self.block(branch,env)
                if isinstance(r,(ReturnSignal,TrySignal)):return r
            elif kind=='while':
                guard=0
                while self.eval(node.condition,env).value:
                    r=self.block(node.nested_body,env)
                    if isinstance(r,(ReturnSignal,TrySignal)):return r
                    guard+=1
                    if guard>1000000:raise RuntimeError('loop iteration limit exceeded')
        return None
    def assign(self,e,v,env):
        node=self.p.node(e)
        if node.kind=='var':
            if self.call_modes and self.call_modes[-1].get(node.atom_value)=='borrow_mut':
                env[node.atom_value].type_name=v.type_name;env[node.atom_value].value=v.value
            else: env[node.atom_value]=v
            return
        if node.kind=='field':self.eval(node.field_base,env).value[node.field_name]=v;return
    def clone(self,v):
        if isinstance(v,TypedValue):
            if isinstance(v.value,dict): return TypedValue(v.type_name,{k:self.clone(x) for k,x in v.value.items()},v.allocator)
            return TypedValue(v.type_name,v.value,v.allocator)
        return v
    def drop_value(self,v):
        if not isinstance(v,TypedValue):return
        semantics=self.types.get(v.type_name)
        if not semantics.needs_drop:return
        if semantics.drop_strategy=='buffer':v.value=bytearray();return
        if semantics.drop_strategy=='i64vec':v.value=[];return
        if semantics.drop_strategy=='vector':
            for element in v.value:self.drop_value(element)
            v.value=[];return
        if semantics.kind=='struct':
            destructor=self.p.destructors.get(v.type_name)
            if destructor is not None:self.block(destructor.body,{'self':v})
            for field in self.p.structs[v.type_name].fields:self.drop_value(v.value[field.name])
            return
        if semantics.kind=='enum':
            payload=v.value.get('payload')
            if payload is not None:self.drop_value(payload)
    def eval(self,e,env,expected=None):
        node=self.p.node(e);kind=node.kind
        if kind=='string':return TypedValue('String',node.atom_value)
        if kind=='number':return self.literal(expected or 'i64',node.atom_value)
        if kind=='var':return env[node.atom_value]
        if kind=='field':return self.eval(node.field_base,env).value[node.field_name]
        if kind=='struct_init':
            s=self.p.structs[node.constructed_type];return TypedValue(node.constructed_type,{f.name:self.eval(node.field_values[f.name],env,f.type_name) for f in s.fields})
        if kind in ('call','generic_call'):
            n,args=resolved_call(e)
            variants=[(enum,variant) for enum in self.p.enums.values() for variant in enum.variants if variant.name==n]
            if variants:
                enum,variant=variants[0]
                payload=self.eval(args[0],env,variant.payload_type) if variant.payload_type is not None else None
                return TypedValue(enum.name,{'variant':variant.name,'payload':payload})
            if n=='old':
                old_env=env.get('__old__')
                if old_env is None: raise RuntimeError('old() is only valid in postconditions')
                return self.eval(args[0],old_env)
            if n=='system_allocator': return TypedValue('Allocator','system')
            if n=='portable_allocator': return TypedValue('Allocator','portable')
            if n=='allocator_compatible': return TypedValue('i32',int(self.eval(args[0],env).value==self.eval(args[1],env).value))
            if n=='string_len': return TypedValue('i64',len(self.eval(args[0],env).value.encode('utf-8')))
            if n=='string_byte':
                text=self.eval(args[0],env).value.encode('utf-8'); idx=self.eval(args[1],env).value
                if idx<0 or idx>=len(text): raise RuntimeError('string index out of bounds')
                return TypedValue('u8',text[idx])
            if n=='buffer_new': return TypedValue('Buffer',bytearray(),self.eval(args[0],env).value)
            if n=='buffer_from_string': return TypedValue('Buffer',bytearray(self.eval(args[1],env).value.encode('utf-8')),self.eval(args[0],env).value)
            if n=='buffer_push':
                buf=self.eval(args[0],env); buf.value.append(self.eval(args[1],env).value); return TypedValue('void',None)
            if n=='buffer_len': return TypedValue('i64',len(self.eval(args[0],env).value))
            if n=='buffer_get':
                buf=self.eval(args[0],env).value; idx=self.eval(args[1],env).value
                if idx<0 or idx>=len(buf): raise RuntimeError('buffer index out of bounds')
                return TypedValue('i64',buf[idx])
            if n=='buffer_slice':
                buf=self.eval(args[0],env).value; start=self.eval(args[1],env).value; length=self.eval(args[2],env).value
                if start<0 or length<0 or start+length>len(buf): raise RuntimeError('slice out of bounds')
                return TypedValue('ByteSlice',memoryview(buf)[start:start+length])
            if n=='buffer_allocator': return TypedValue('Allocator',self.eval(args[0],env).allocator)
            if n=='slice_len': return TypedValue('i64',len(self.eval(args[0],env).value))
            if n=='slice_get':
                view=self.eval(args[0],env).value; idx=self.eval(args[1],env).value
                if idx<0 or idx>=len(view): raise RuntimeError('slice index out of bounds')
                return TypedValue('i64',int(view[idx]))
            if n=='i64vec_new': return TypedValue('I64Vec',[],self.eval(args[0],env).value)
            if n=='i64vec_push':
                vec=self.eval(args[0],env); vec.value.append(self.eval(args[1],env).value); return TypedValue('void',None)
            if n=='i64vec_len': return TypedValue('i64',len(self.eval(args[0],env).value))
            if n=='i64vec_get':
                vec=self.eval(args[0],env).value; idx=self.eval(args[1],env).value
                if idx<0 or idx>=len(vec): raise RuntimeError('vector index out of bounds')
                return TypedValue('i64',vec[idx])
            if n=='i64vec_allocator': return TypedValue('Allocator',self.eval(args[0],env).allocator)
            vec=vec_builtin(n)
            if vec:
                op,elem=vec; vec_t='Vec__'+elem
                if op=='new': return TypedValue(vec_t,[],self.eval(args[0],env).value)
                if op=='push':
                    self.eval(args[0],env).value.append(self.clone(self.eval(args[1],env,elem))); return TypedValue('void',None)
                if op=='len': return TypedValue('i64',len(self.eval(args[0],env).value))
                if op=='allocator': return TypedValue('Allocator',self.eval(args[0],env).allocator)
                if op=='get':
                    data=self.eval(args[0],env).value; idx=self.eval(args[1],env).value
                    if idx<0 or idx>=len(data): raise RuntimeError('vector index out of bounds')
                    return self.clone(data[idx])
                if op=='set':
                    data=self.eval(args[0],env).value; idx=self.eval(args[1],env).value
                    if idx<0 or idx>=len(data): raise RuntimeError('vector index out of bounds')
                    data[idx]=self.clone(self.eval(args[2],env,elem)); return TypedValue('void',None)
                if op=='replace':
                    data=self.eval(args[0],env).value; idx=self.eval(args[1],env).value
                    replacement=self.clone(self.eval(args[2],env,elem))
                    if idx<0 or idx>=len(data): raise RuntimeError('vector index out of bounds')
                    self.drop_value(data[idx]);data[idx]=replacement; return TypedValue('void',None)
                if op=='pop':
                    data=self.eval(args[0],env).value
                    if not data: raise RuntimeError('vector pop from empty')
                    return self.clone(data.pop())
                if op=='drop':
                    self.drop_value(self.eval(args[0],env)); return TypedValue('void',None)
                if op=='transfer':
                    destination=self.eval(args[0],env);source=self.eval(args[1],env)
                    if destination.allocator!=source.allocator:raise RuntimeError('incompatible vector allocators')
                    if destination.value:raise RuntimeError('vector transfer destination is not empty')
                    destination.value=source.value;source.value=[];return TypedValue('void',None)
            if n=='file_read':
                allocator=self.eval(args[0],env).value;path=self.eval(args[1],env).value
                try:return TypedValue('FileReadResult',{'variant':'ReadOk','payload':TypedValue('Buffer',bytearray(Path(path).read_bytes()),allocator)})
                except FileNotFoundError:return TypedValue('FileReadResult',{'variant':'ReadErr','payload':TypedValue('FsError',{'variant':'FsNotFound','payload':None})})
                except PermissionError:return TypedValue('FileReadResult',{'variant':'ReadErr','payload':TypedValue('FsError',{'variant':'FsPermissionDenied','payload':None})})
                except OSError:return TypedValue('FileReadResult',{'variant':'ReadErr','payload':TypedValue('FsError',{'variant':'FsIoError','payload':None})})
            if n=='file_write':
                path=self.eval(args[0],env).value
                data=self.eval(args[1],env).value
                try:return TypedValue('FileWriteResult',{'variant':'WriteOk','payload':TypedValue('i64',Path(path).write_bytes(bytes(data)))})
                except FileNotFoundError:return TypedValue('FileWriteResult',{'variant':'WriteErr','payload':TypedValue('FsError',{'variant':'FsNotFound','payload':None})})
                except PermissionError:return TypedValue('FileWriteResult',{'variant':'WriteErr','payload':TypedValue('FsError',{'variant':'FsPermissionDenied','payload':None})})
                except OSError:return TypedValue('FileWriteResult',{'variant':'WriteErr','payload':TypedValue('FsError',{'variant':'FsIoError','payload':None})})
            if n.startswith('checked_') or n=='decimal_div':
                first=self.eval(args[0],env)
                second=self.eval(args[1],env,first.type_name)
                return self.arith('div' if n=='decimal_div' else n[8:],first,second)
            callee=self.fn[n]
            vals=[self.eval(x,env,param.type_name) for x,param in zip(args,callee.params)]
            return self.call(n,vals)
        if kind=='binop':
            a=self.eval(node.left,env);b=self.eval(node.right,env,a.type_name)
            if node.operator in ('==','!=','>=','<=','>','<'):
                return TypedValue('i32',int({'==':a.value==b.value,'!=':a.value!=b.value,'>=':a.value>=b.value,'<=':a.value<=b.value,'>':a.value>b.value,'<':a.value<b.value}[node.operator]))
            return self.arith({'+':'add','-':'sub','*':'mul','/':'div'}[node.operator],a,b)
    def literal(self,t,x):
        if t in self.p.decimals:return TypedValue(t,int(Decimal(x)*(10**self.p.decimals[t].scale)))
        return TypedValue(t,int(Decimal(x)))
    def arith(self,op,a,b):
        if op=='add':v=a.value+b.value
        elif op=='sub':v=a.value-b.value
        elif op=='mul':
            if a.type_name in self.p.decimals:
                d=self.p.decimals[a.type_name];v=int((Decimal(a.value)*Decimal(b.value)/Decimal(10**d.scale)).quantize(Decimal(1),rounding=ROUNDING[d.rounding]))
            else:v=a.value*b.value
        elif op=='div':
            if b.value==0:raise RuntimeError('division by zero')
            if a.type_name in self.p.decimals:
                d=self.p.decimals[a.type_name];q=(Decimal(a.value)*(10**d.scale)/Decimal(b.value)).quantize(Decimal(1),rounding=ROUNDING[d.rounding]);v=int(q)
            else:
                quotient=abs(a.value)//abs(b.value);v=-quotient if (a.value<0) != (b.value<0) else quotient
        self.range(a.type_name,v);return TypedValue(a.type_name,v)
    def range(self,t,v):
        if t in self.p.decimals and abs(v)>10**self.p.decimals[t].precision-1:raise RuntimeError(f'decimal overflow in {t}')
        if t in self.p.bounded and not self.p.bounded[t].minimum<=v<=self.p.bounded[t].maximum:raise RuntimeError(f'bounded overflow in {t}')
        if t in INT_RANGES and not INT_RANGES[t][0]<=v<=INT_RANGES[t][1]:raise RuntimeError(f'integer overflow in {t}')
    def format(self,v):
        if v.type_name in self.p.decimals:
            s=self.p.decimals[v.type_name].scale;n=abs(v.value);return ('-' if v.value<0 else '')+f'{n//10**s}.{n%10**s:0{s}d}'
        if v.type_name=='String': return v.value
        if v.type_name=='Buffer': return bytes(v.value).decode('utf-8',errors='replace')
        if v.type_name=='Allocator': return '<allocator>'
        if v.type_name in self.p.enums:
            payload=v.value['payload']; return v.value['variant'] if payload is None else f"{v.value['variant']}({self.format(payload)})"
        if v.type_name in self.p.structs:return '{'+', '.join(f'{k}: {self.format(x)}' for k,x in v.value.items())+'}'
        return str(v.value)

class CGenerator:
    def __init__(self,p):self.p=p;self.types=TypeTable(p);self.ownership=OwnershipEffects(p,self.types);self.fn={f.name:f for f in p.functions};self.old_map={};self.current_return=None;self.temp_counter=0
    def vec_types(self):
        found=set()
        def add(t):
            if is_vec_type(t):
                found.add(t); add(vec_elem_type(t))
        for s in self.p.structs.values():
            for f in s.fields: add(f.type_name)
        for e in self.p.enums.values():
            for v in e.variants:
                if v.payload_type: add(v.payload_type)
        for f in self.p.functions:
            add(f.return_type)
            for param in f.params: add(param.type_name)
            for st in self.walk_statements(f.body):
                node=self.p.node(st)
                if node.kind in ('let','try_let'): add(node.declared_type)
        return sorted(found,key=lambda name:(name.count('Vec__'),name))
    def ctype(self,t):
        if t in self.p.decimals:return 'int64_t'
        if t in self.p.bounded:return self.ctype(self.p.bounded[t].base)
        if t in self.p.structs:return f'merit_{t}'
        if t in self.p.enums:return f'merit_{t}'
        if t=='String': return 'merit_String'
        if t=='Buffer': return 'merit_Buffer'
        if t=='Allocator': return 'merit_Allocator'
        if t=='ByteSlice': return 'merit_ByteSlice'
        if t=='I64Vec': return 'merit_I64Vec'
        if is_vec_type(t): return 'merit_'+t
        return {'i8':'int8_t','i16':'int16_t','i32':'int32_t','i64':'int64_t','u8':'uint8_t','u16':'uint16_t','u32':'uint32_t','u64':'uint64_t','void':'void'}[t]
    def vec_typedef_lines(self,vt):
        layout=LayoutEngine(self.p).vec_layout(vt)
        return [
            f'/* Merit layout vector {vt} hash {layout["layout_hash"]} */',
            f'typedef struct merit_{vt} {{',
            f'    {self.ctype(vec_elem_type(vt))} *data;',
            '    size_t len;',
            '    size_t cap;',
            '    merit_Allocator allocator;',
            f'}} merit_{vt};',
            f'_Static_assert(__builtin_offsetof(merit_{vt}, data) == 0, "Merit Vec layout mismatch: {vt}.data");',
            f'_Static_assert(__builtin_offsetof(merit_{vt}, len) == sizeof(void *), "Merit Vec layout mismatch: {vt}.len");',
            f'_Static_assert(__builtin_offsetof(merit_{vt}, cap) == sizeof(void *) + sizeof(size_t), "Merit Vec layout mismatch: {vt}.cap");',
            f'_Static_assert(__builtin_offsetof(merit_{vt}, allocator) == sizeof(void *) + sizeof(size_t) * 2, "Merit Vec layout mismatch: {vt}.allocator");',
            f'_Static_assert(sizeof(merit_{vt}) == 32, "Merit Vec size mismatch: {vt}");',
            ''
        ]
    def vec_can_define_before_composites(self,vt):
        elem=vec_elem_type(vt)
        return not is_vec_type(elem) and elem not in self.p.structs and elem not in self.p.enums
    def header(self,include_private=False):
        o=['#pragma once','#include <stdint.h>','#include <stddef.h>','', 'typedef struct { const char *data; size_t len; } merit_String;', 'typedef struct { int kind; } merit_Allocator;', 'typedef struct { uint8_t *data; size_t len; size_t cap; merit_Allocator allocator; } merit_Buffer;', 'typedef struct { const uint8_t *data; size_t len; } merit_ByteSlice;', 'typedef struct { int64_t *data; size_t len; size_t cap; merit_Allocator allocator; } merit_I64Vec;', '']
        early_vecs=[vt for vt in self.vec_types() if self.vec_can_define_before_composites(vt)]
        for vt in early_vecs: o.extend(self.vec_typedef_lines(vt))
        le=LayoutEngine(self.p)
        for enum in self.p.enums.values():
            if self.p.exports and not include_private and enum.name not in self.p.exports and enum.name not in FS_BUILTIN_ENUMS:continue
            layout=le.enum_layout(enum)
            o.append(f'/* Merit layout enum {enum.name} hash {layout["layout_hash"]} */')
            o.append(f'typedef enum merit_{enum.name}_tag {{')
            for idx,variant in enumerate(enum.variants): o.append(f'    merit_{enum.name}_{variant.name} = {idx},')
            o.append(f'}} merit_{enum.name}_tag;')
            o.append(f'typedef struct merit_{enum.name} {{')
            o.append(f'    merit_{enum.name}_tag tag;')
            payloads=[v for v in enum.variants if v.payload_type is not None]
            if payloads:
                o.append('    union {')
                for variant in payloads:o.append(f'        {self.ctype(variant.payload_type)} {variant.name};')
                o.append('    } data;')
            o.append(f'}} merit_{enum.name};')
            o.append(f'_Static_assert(__builtin_offsetof(merit_{enum.name}, tag) == 0, "Merit enum layout mismatch: {enum.name}.tag");')
            if payloads:
                o.append(f'_Static_assert(__builtin_offsetof(merit_{enum.name}, data) >= sizeof(merit_{enum.name}_tag), "Merit enum layout mismatch: {enum.name}.data");')
                o.append(f'_Static_assert(sizeof(merit_{enum.name}) >= __builtin_offsetof(merit_{enum.name}, data), "Merit enum size mismatch: {enum.name}");')
            for variant in enum.variants:
                params='void' if variant.payload_type is None else f'{self.ctype(variant.payload_type)} value'
                init=f'(merit_{enum.name}){{.tag=merit_{enum.name}_{variant.name}'
                if variant.payload_type is not None:init+=f',.data.{variant.name}=value'
                init+='}'
                o.append(f'static inline merit_{enum.name} merit_make_{enum.name}_{variant.name}({params}){{return {init};}}')
            o.append('')
        for s in self.p.structs.values():
            if self.p.exports and not include_private and s.name not in self.p.exports:continue
            if s.stable_abi:
                layout=le.layout(s);o.append(f'/* Merit layout struct {s.name} hash {layout["layout_hash"]} */')
            o.append(f'typedef struct merit_{s.name} {{')
            for f in s.fields:o.append(f'    {self.ctype(f.type_name)} {f.name};')
            o.append(f'}} merit_{s.name};')
            if s.stable_abi:
                o.append(f'_Static_assert(sizeof(merit_{s.name}) == {layout["size"]}, "Merit ABI size mismatch: {s.name}");')
                for fld in layout['fields']:o.append(f'_Static_assert(__builtin_offsetof(merit_{s.name}, {fld["name"]}) == {fld["offset"]}, "Merit ABI offset mismatch: {s.name}.{fld["name"]}");')
            o.append('')
        for vt in self.vec_types():
            if vt not in early_vecs:
                o.extend(self.vec_typedef_lines(vt))
        for f in self.p.functions:
            if f.name=='main':continue
            if self.p.exports and not include_private and f.name not in self.p.exports:continue
            params=', '.join(f'{self.ctype(param.type_name)}{" *" if param.mode in ("borrow","borrow_mut") else " "}{param.name}' for param in f.params) or 'void'
            return_type=self.ctype(f.return_type)+(' *' if f.return_mode!='value' else '')
            o.append(f'{return_type} merit_{f.name}({params});')
        return '\n'.join(o)
    def generate(self):
        o=['#include <stdint.h>','#include <stddef.h>','#include <stdio.h>','#include <stdlib.h>','#include <string.h>','#include <errno.h>','#if defined(__GNUC__) || defined(__clang__)','#define MERIT_UNUSED __attribute__((unused))','#else','#define MERIT_UNUSED','#endif','']
        o.append(self.header(include_private=True).replace('#pragma once','').replace('#include <stdint.h>',''))
        o += [r'''static void merit_fail(const char *m,int c){fputs(m,stderr);fputc('\n',stderr);exit(c);}''',
              r'''static merit_Allocator merit_system_allocator(void){return (merit_Allocator){0};}''',
              r'''static merit_Allocator merit_portable_allocator(void){return (merit_Allocator){1};}''',
              r'''static int32_t merit_allocator_compatible(merit_Allocator a,merit_Allocator b){return a.kind==b.kind;}''',
              r'''static void *merit_allocator_realloc(merit_Allocator a,void *p,size_t n){if(a.kind!=0&&a.kind!=1)merit_fail("unsupported allocator",89);return realloc(p,n);}''',
              r'''static void merit_allocator_free(merit_Allocator a,void *p){if(a.kind!=0&&a.kind!=1)merit_fail("unsupported allocator",89);free(p);}''',
              r'''static void merit_buffer_reserve(merit_Buffer *b,size_t need){if(need<=b->cap)return;size_t c=b->cap?b->cap:8;while(c<need)c*=2;void *p=merit_allocator_realloc(b->allocator,b->data,c);if(!p)merit_fail("allocation failed",80);b->data=(uint8_t*)p;b->cap=c;}''',
              r'''static merit_Buffer merit_buffer_new(merit_Allocator a,int64_t cap){merit_Buffer b={0};b.allocator=a;if(cap<0)merit_fail("negative capacity",81);merit_buffer_reserve(&b,(size_t)cap);return b;}''',
              r'''static merit_Buffer merit_buffer_from_string(merit_Allocator a,merit_String s){merit_Buffer b=merit_buffer_new(a,(int64_t)s.len);if(s.len){memcpy(b.data,s.data,s.len);b.len=s.len;}return b;}''',
              r'''static void merit_buffer_push(merit_Buffer *b,uint8_t v){merit_buffer_reserve(b,b->len+1);b->data[b->len++]=v;}''',
              r'''static int64_t merit_buffer_len(const merit_Buffer *b){return (int64_t)b->len;}''',
              r'''static int64_t merit_buffer_get(const merit_Buffer *b,int64_t i){if(i<0||(size_t)i>=b->len)merit_fail("buffer index out of bounds",82);return (int64_t)b->data[i];}''',
              r'''static merit_ByteSlice merit_buffer_slice(const merit_Buffer *b,int64_t start,int64_t len){if(start<0||len<0||(size_t)start>b->len||(size_t)len>b->len-(size_t)start)merit_fail("slice out of bounds",85);return (merit_ByteSlice){b->data+(size_t)start,(size_t)len};}''',
              r'''static merit_Allocator merit_buffer_allocator(const merit_Buffer *b){return b->allocator;}''',
              r'''static int64_t merit_slice_len(merit_ByteSlice s){return (int64_t)s.len;}''',
              r'''static int64_t merit_slice_get(merit_ByteSlice s,int64_t i){if(i<0||(size_t)i>=s.len)merit_fail("slice index out of bounds",85);return (int64_t)s.data[i];}''',
              r'''static void merit_i64vec_reserve(merit_I64Vec *v,size_t need){if(need<=v->cap)return;size_t c=v->cap?v->cap:8;while(c<need)c*=2;void *p=merit_allocator_realloc(v->allocator,v->data,c*sizeof(int64_t));if(!p)merit_fail("allocation failed",80);v->data=(int64_t*)p;v->cap=c;}''',
              r'''static merit_I64Vec merit_i64vec_new(merit_Allocator a,int64_t cap){merit_I64Vec v={0};v.allocator=a;if(cap<0)merit_fail("negative capacity",81);merit_i64vec_reserve(&v,(size_t)cap);return v;}''',
              r'''static void merit_i64vec_push(merit_I64Vec *v,int64_t x){merit_i64vec_reserve(v,v->len+1);v->data[v->len++]=x;}''',
              r'''static int64_t merit_i64vec_len(const merit_I64Vec *v){return (int64_t)v->len;}''',
              r'''static int64_t merit_i64vec_get(const merit_I64Vec *v,int64_t i){if(i<0||(size_t)i>=v->len)merit_fail("vector index out of bounds",86);return v->data[i];}''',
              r'''static merit_Allocator merit_i64vec_allocator(const merit_I64Vec *v){return v->allocator;}''',
              r'''static void merit_i64vec_drop(merit_I64Vec *v){merit_allocator_free(v->allocator,v->data);v->data=NULL;v->len=0;v->cap=0;}''',
              r'''static void merit_buffer_drop(merit_Buffer *b){merit_allocator_free(b->allocator,b->data);b->data=NULL;b->len=0;b->cap=0;}''',
              r'''static merit_FsError merit_fs_error(int e){if(e==ENOENT)return merit_make_FsError_FsNotFound();if(e==EACCES||e==EPERM)return merit_make_FsError_FsPermissionDenied();return merit_make_FsError_FsIoError();}''',
              r'''static merit_FileReadResult merit_file_read(merit_Allocator a,merit_String path){char *z=(char*)malloc(path.len+1);if(!z)merit_fail("allocation failed",80);memcpy(z,path.data,path.len);z[path.len]=0;FILE *f=fopen(z,"rb");int open_error=errno;free(z);if(!f)return merit_make_FileReadResult_ReadErr(merit_fs_error(open_error));if(fseek(f,0,SEEK_END)!=0){int e=errno;fclose(f);return merit_make_FileReadResult_ReadErr(merit_fs_error(e));}long n=ftell(f);if(n<0){int e=errno;fclose(f);return merit_make_FileReadResult_ReadErr(merit_fs_error(e));}rewind(f);merit_Buffer b=merit_buffer_new(a,n);if(n>0){size_t got=fread(b.data,1,(size_t)n,f);if(got!=(size_t)n){int e=errno;merit_buffer_drop(&b);fclose(f);return merit_make_FileReadResult_ReadErr(merit_fs_error(e));}b.len=got;}if(fclose(f)!=0){merit_buffer_drop(&b);return merit_make_FileReadResult_ReadErr(merit_fs_error(errno));}return merit_make_FileReadResult_ReadOk(b);}''',
              r'''static merit_FileWriteResult merit_file_write(merit_String path,const merit_Buffer *b){char *z=(char*)malloc(path.len+1);if(!z)merit_fail("allocation failed",80);memcpy(z,path.data,path.len);z[path.len]=0;FILE *f=fopen(z,"wb");int open_error=errno;free(z);if(!f)return merit_make_FileWriteResult_WriteErr(merit_fs_error(open_error));size_t wrote=b->len?fwrite(b->data,1,b->len,f):0;if(wrote!=b->len){int e=errno;fclose(f);return merit_make_FileWriteResult_WriteErr(merit_fs_error(e));}if(fclose(f)!=0)return merit_make_FileWriteResult_WriteErr(merit_fs_error(errno));return merit_make_FileWriteResult_WriteOk((int64_t)wrote);}''',
              r'''static int64_t merit_add(int64_t a,int64_t b){int64_t r;if(__builtin_add_overflow(a,b,&r))merit_fail("Merit addition overflow",70);return r;}''',
              r'''static int64_t merit_sub(int64_t a,int64_t b){int64_t r;if(__builtin_sub_overflow(a,b,&r))merit_fail("Merit subtraction overflow",70);return r;}''',
              r'''static int64_t merit_div(int64_t a,int64_t b){if(!b)merit_fail("Merit division by zero",72);if(a==INT64_MIN&&b==-1)merit_fail("Merit division overflow",70);return a/b;}''',
              r'''static int64_t merit_round_div(__int128 n,__int128 d,int mode){if(d==0)merit_fail("Merit division by zero",72);int neg=(n<0)^(d<0);if(n<0)n=-n;if(d<0)d=-d;__int128 q=n/d,r=n%d;int up=0;if(mode==0){__int128 twice=r*2;up=twice>d || (twice==d && (q&1));}else if(mode==1)up=r*2>=d;else if(mode==3)up=!neg&&r;else if(mode==4)up=neg&&r;q+=up;__int128 z=neg?-q:q;if(z>INT64_MAX||z<INT64_MIN)merit_fail("Merit decimal overflow",70);return (int64_t)z;}''','']
        for type_name,(minimum,maximum) in INT_RANGES.items():
            signed=type_name.startswith('i');ctype=self.ctype(type_name);wide='__int128' if signed else 'unsigned __int128';minimum_literal='INT64_MIN' if type_name=='i64' else str(minimum);maximum_literal='UINT64_MAX' if type_name=='u64' else str(maximum);limit=f'({wide}){maximum_literal}';range_test=(f'z<({wide}){minimum_literal}||' if signed else '')+f'z>{limit}';sub_guard='' if signed else f'if(a<b)merit_fail("{type_name} subtraction overflow",70);'
            o.extend([
                f'static {ctype} merit_add_{type_name}({ctype} a,{ctype} b){{{wide} z=({wide})a+({wide})b;if({range_test})merit_fail("{type_name} addition overflow",70);return ({ctype})z;}}',
                f'static {ctype} merit_sub_{type_name}({ctype} a,{ctype} b){{{sub_guard}{wide} z=({wide})a-({wide})b;if({range_test})merit_fail("{type_name} subtraction overflow",70);return ({ctype})z;}}',
                f'static {ctype} merit_mul_{type_name}({ctype} a,{ctype} b){{{wide} z=({wide})a*({wide})b;if({range_test})merit_fail("{type_name} multiplication overflow",70);return ({ctype})z;}}',
                f'static {ctype} merit_div_{type_name}({ctype} a,{ctype} b){{if(!b)merit_fail("Merit division by zero",72);{wide} z=({wide})a/({wide})b;if({range_test})merit_fail("Merit division overflow",70);return ({ctype})z;}}',
            ])
        for e in self.p.enums.values():
            if self.types.get(e.name).needs_drop:
                o.append(f'static void merit_drop_{e.name}({self.ctype(e.name)} *v);')
        for s in self.p.structs.values():
            if self.types.get(s.name).needs_drop:
                o.append(f'static void merit_drop_{s.name}({self.ctype(s.name)} *v);')
        if any(self.types.get(e.name).needs_drop for e in self.p.enums.values()) or any(self.types.get(s.name).needs_drop for s in self.p.structs.values()):
            o.append('')
        for vt in self.vec_types(): o.extend(self.vec_runtime(vt))
        for e in self.p.enums.values():
            if self.types.get(e.name).needs_drop:
                o.extend(self.enum_drop_runtime(e))
        for s in self.p.structs.values():
            if self.types.get(s.name).needs_drop:
                o.extend(self.struct_drop_runtime(s))
        for t,b in self.p.bounded.items():
            o.append(f'static {self.ctype(t)} merit_check_{t}({self.ctype(t)} x){{if(x < {b.minimum} || x > {b.maximum}) merit_fail("bounded range violation: {t}",70);return x;}}')
        for t,d in self.p.decimals.items():
            m=10**d.precision-1;o.append(f'static int64_t merit_check_{t}(int64_t x){{if(x < -{m}LL || x > {m}LL) merit_fail("decimal range violation: {t}",70);return x;}}')
        for f in self.p.functions:o.append(self.fn_c(f))
        return re.sub(r'\bstatic (?!inline\b)', 'static MERIT_UNUSED ', '\n'.join(o))
    def vec_runtime(self,vt):
        elem=vec_elem_type(vt); ct=self.ctype(elem); vct=self.ctype(vt); suffix=vec_elem_type(vt)
        elem_drop=self.drop_field_stmt('v->data[i]',elem)
        drop_live=f'for(size_t i=0;i<v->len;i++){elem_drop}' if elem_drop else ''
        return [
            f'static void merit_vec_reserve__{suffix}({vct} *v,size_t need){{if(need<=v->cap)return;size_t c=v->cap?v->cap:8;while(c<need)c*=2;void *p=merit_allocator_realloc(v->allocator,v->data,c*sizeof({ct}));if(!p)merit_fail("allocation failed",80);v->data=({ct}*)p;v->cap=c;}}',
            f'static {vct} merit_vec_new__{suffix}(merit_Allocator a,int64_t cap){{{vct} v={{0}};v.allocator=a;if(cap<0)merit_fail("negative capacity",81);merit_vec_reserve__{suffix}(&v,(size_t)cap);return v;}}',
            f'static void merit_vec_push__{suffix}({vct} *v,{ct} x){{merit_vec_reserve__{suffix}(v,v->len+1);v->data[v->len++]=x;}}',
            f'static int64_t merit_vec_len__{suffix}(const {vct} *v){{return (int64_t)v->len;}}',
            f'static merit_Allocator merit_vec_allocator__{suffix}(const {vct} *v){{return v->allocator;}}',
            f'static {ct} merit_vec_get__{suffix}(const {vct} *v,int64_t i){{if(i<0||(size_t)i>=v->len)merit_fail("vector index out of bounds",86);return v->data[i];}}',
            f'static void merit_vec_set__{suffix}({vct} *v,int64_t i,{ct} x){{if(i<0||(size_t)i>=v->len)merit_fail("vector index out of bounds",86);v->data[i]=x;}}',
            f'static void merit_vec_replace__{suffix}({vct} *v,int64_t i,{ct} x){{if(i<0||(size_t)i>=v->len)merit_fail("vector index out of bounds",86);{self.drop_field_stmt("v->data[i]",elem)}v->data[i]=x;}}',
            f'static {ct} merit_vec_pop__{suffix}({vct} *v){{if(!v->len)merit_fail("vector pop from empty",86);return v->data[--v->len];}}',
            f'static void merit_vec_drop__{suffix}({vct} *v){{{drop_live}merit_allocator_free(v->allocator,v->data);v->data=NULL;v->len=0;v->cap=0;}}',
            f'static void merit_vec_transfer__{suffix}({vct} *destination,{vct} *source){{if(destination==source)merit_fail("vector transfer aliases itself",90);if(!merit_allocator_compatible(destination->allocator,source->allocator))merit_fail("incompatible vector allocators",90);if(destination->len)merit_fail("vector transfer destination is not empty",90);merit_allocator_free(destination->allocator,destination->data);destination->data=source->data;destination->len=source->len;destination->cap=source->cap;source->data=NULL;source->len=0;source->cap=0;}}',
            ''
        ]
    def drop_field_stmt(self,base,t):
        return self.drop_address_stmt(f'&{base}',t)
    def drop_address_stmt(self,address,t):
        strategy=self.types.get(t).drop_strategy
        if strategy=='buffer': return f'merit_buffer_drop({address});'
        if strategy=='i64vec': return f'merit_i64vec_drop({address});'
        if strategy=='vector': return f'merit_vec_drop__{vec_elem_type(t)}({address});'
        if strategy=='aggregate': return f'merit_drop_{t}({address});'
        return ''
    def drop_binding_line(self,prefix,name,t):
        stmt=self.drop_field_stmt(name,t)
        return f'{prefix}{stmt}' if stmt else f'{prefix}/* deterministic drop {name} */'
    def drop_address_line(self,prefix,address,t):
        stmt=self.drop_address_stmt(address,t)
        return f'{prefix}{stmt}' if stmt else f'{prefix}/* deterministic replacement drop */'
    def enum_drop_runtime(self,e):
        lines=[f'static void merit_drop_{e.name}({self.ctype(e.name)} *v){{','    switch (v->tag) {']
        for variant in e.variants:
            lines.append(f'    case merit_{e.name}_{variant.name}:')
            if variant.payload_type is not None:
                stmt=self.drop_field_stmt(f'v->data.{variant.name}',variant.payload_type)
                if stmt: lines.append(f'        {stmt}')
            lines.append('        break;')
        lines.extend(['    }','}',''])
        return lines
    def struct_drop_runtime(self,s):
        lines=[f'static void merit_drop_{s.name}({self.ctype(s.name)} *self){{']
        destructor=self.p.destructors.get(s.name)
        if destructor is not None:
            env={'self':(s.name,'borrow_mut')}
            for statement in destructor.body:lines.extend(self.stmt(statement,env,1))
        for field in s.fields:
            stmt=self.drop_field_stmt(f'self->{field.name}',field.type_name)
            if stmt: lines.append(f'    {stmt}')
        lines.append('}')
        lines.append('')
        return lines
    def walk_old(self,e,out):
        if not isinstance(e,SemanticNode):return
        node=self.p.node(e)
        if node.kind=='call' and node.callee_name=='old':
            key=repr(node.arguments[0]);out.setdefault(key,node.arguments[0]);return
        for x in node.operands:
            if isinstance(x,SemanticNode):self.walk_old(x,out)
            elif isinstance(x,list):
                for y in x:self.walk_old(y,out)
    def walk_statements(self, body):
        for st in body:
            yield st
            node=self.p.node(st)
            if node.kind in ('with_cap','while'):
                yield from self.walk_statements(node.nested_body)
            elif node.kind=='if':
                yield from self.walk_statements(node.then_body); yield from self.walk_statements(node.else_body)
            elif node.kind=='match':
                for arm in node.match_arms: yield from self.walk_statements(arm.body)
    def owned_buffer_cleanup(self, f):
        ownership=self.ownership.function(f)
        return [
            (name,type_name)
            for name,type_name in reversed(ownership.owned_locals)
            if self.types.get(type_name).needs_drop
            and name not in ownership.explicit_drops
            and name not in ownership.consumed_roots
        ]
    def fn_c(self,f):
        name='main' if f.name=='main' else 'merit_'+f.name;params=', '.join(f'{self.ctype(param.type_name)}{" *" if param.mode in ("borrow","borrow_mut") else " "}{param.name}' for param in f.params) or 'void';env={param.name:(param.type_name,param.mode) for param in f.params};return_type=self.ctype(f.return_type)+(' *' if f.return_mode!='value' else '');o=[f'{return_type} {name}({params}) {{']
        old={}
        for c in f.post:self.walk_old(c,old)
        self.old_map={}
        for idx,(key,e) in enumerate(old.items()):
            t=self.etype(e,env);v=f'_merit_old_{idx}';self.old_map[key]=v;o.append(f'    {self.ctype(t)} {v} = {self.expr(e,env)};')
        for c in f.pre:o.append(f'    if(!({self.expr(c,env)})) merit_fail("precondition failed in {f.name}",71);')
        self.current_return=f.return_type
        if f.return_type!='void':
            if f.return_mode!='value':o.append(f'    {self.ctype(f.return_type)} *_merit_result = NULL;')
            else:o.append(f'    {self.ctype(f.return_type)} _merit_result = {{0}};' if f.return_type in self.p.enums or f.return_type in self.p.structs or f.return_type in BUILTIN_TYPES else f'    {self.ctype(f.return_type)} _merit_result = 0;')
        for st in f.body:o+=self.stmt(st,env,1)
        o.append('    _merit_epilogue: ;')
        postenv=dict(env);postenv['result']=(f.return_type,'__result__')
        for c in f.post:o.append(f'    if(!({self.expr(c,postenv)})) merit_fail("postcondition failed in {f.name}",73);')
        for name,t in self.owned_buffer_cleanup(f):
            o.append(self.drop_binding_line('    ',name,t))
        if f.return_type!='void':o.append('    return _merit_result;')
        o.append('}');return '\n'.join(o)
    def checked(self,t,x):
        if t in self.p.bounded or t in self.p.decimals:return f'merit_check_{t}({x})'
        return x
    def stmt(self,s,env,i):
        p='    '*i
        node=self.p.node(s);kind=node.kind
        if kind=='let':env[node.binding_name]=node.declared_type;return [f'{p}{self.ctype(node.declared_type)} {node.binding_name} = {self.checked(node.declared_type,self.expr(node.initializer,env,node.declared_type))};']
        if kind=='try_let':
            enum_t=self.etype(node.initializer,env); enum=self.p.enums[enum_t]; temp=f'_merit_try_{self.temp_counter}'; self.temp_counter+=1
            err=next(v for v in enum.variants if v.name=='Err'); ret=self.p.enums[self.current_return]
            env[node.binding_name]=node.declared_type
            return [f'{p}{self.ctype(enum_t)} {temp} = {self.expr(node.initializer,env)};', f'{p}if ({temp}.tag == merit_{enum_t}_Err) {{', f'{p}    _merit_result = merit_make_{self.current_return}_Err({temp}.data.Err);', f'{p}    goto _merit_epilogue;', f'{p}}}', f'{p}{self.ctype(node.declared_type)} {node.binding_name} = {temp}.data.Ok;']
        if kind=='assign':
            t=self.etype(node.assignment_target,env);return [f'{p}{self.expr(node.assignment_target,env)} = {self.checked(t,self.expr(node.assigned_value,env,t))};']
        if kind=='replace':
            t=self.etype(node.assignment_target,env);temp=f'_merit_replace_{self.temp_counter}';self.temp_counter+=1
            address=self.address_expr(node.assignment_target,env)
            return [
                f'{p}{self.ctype(t)} {temp} = {self.expr(node.assigned_value,env,t)};',
                self.drop_address_line(p,address,t),
                f'{p}*({address}) = {temp};',
            ]
        if kind=='return':return [f'{p}_merit_result = {self.checked(self.current_return,self.expr(node.expression,env,self.current_return))};',f'{p}goto _merit_epilogue;']
        if kind=='print':
            t=self.etype(node.expression,env);x=self.expr(node.expression,env)
            temp=f'_merit_print_{self.temp_counter}';self.temp_counter+=1
            lines=[f'{p}{self.ctype(t)} {temp} = {x};']
            if t=='String':
                lines.append(f'{p}printf("%.*s\\n",(int){temp}.len,{temp}.data);')
            elif t=='Buffer':
                lines.append(f"{p}fwrite({temp}.data,1,{temp}.len,stdout); fputc('\\n',stdout);")
            elif t in self.p.enums:
                lines.append(f'{p}printf("%d\\n",(int){temp}.tag);')
            elif t in self.p.decimals:
                sc=10**self.p.decimals[t].scale;digits=self.p.decimals[t].scale
                lines.append(f'{p}printf("%s%lld.%0{digits}lld\\n",{temp}<0?"-":"",(long long)(llabs({temp})/{sc}),(long long)(llabs({temp})%{sc}));')
            else:
                lines.append(f'{p}printf("%lld\\n",(long long)({temp}));')
            return lines
        if kind=='expr':
            expression=node.expression
            if self.p.node(expression).kind in ('call','generic_call'):
                name,args=resolved_call(expression);vec=vec_builtin(name)
                if vec and vec[0]=='replace':
                    elem=vec[1];counter=self.temp_counter;self.temp_counter+=1
                    index_temp=f'_merit_vec_replace_index_{counter}'
                    value_temp=f'_merit_vec_replace_value_{counter}'
                    return [
                        f'{p}int64_t {index_temp} = {self.expr(args[1],env)};',
                        f'{p}{self.ctype(elem)} {value_temp} = {self.expr(args[2],env,elem)};',
                        f'{p}merit_vec_replace__{elem}({self.address_expr(args[0],env)}, {index_temp}, {value_temp});',
                    ]
            return [f'{p}(void)({self.expr(expression,env)});']
        if kind=='drop':
            t=self.env_type(env,node.binding_name)
            return [self.drop_binding_line(p,node.binding_name,t)]
        if kind=='match':
            enum_t=self.etype(node.expression,env); temp=f'_merit_match_{self.temp_counter}';self.temp_counter+=1
            o=[f'{p}{self.ctype(enum_t)} {temp} = {self.expr(node.expression,env)};',f'{p}switch ({temp}.tag) {{']
            enum=self.p.enums[enum_t]
            for arm in node.match_arms:
                variant=next(v for v in enum.variants if v.name==arm.variant);o.append(f'{p}case merit_{enum_t}_{variant.name}: {{')
                local=dict(env)
                if arm.binding is not None:
                    local[arm.binding]=variant.payload_type;o.append(f'{p}    {self.ctype(variant.payload_type)} {arm.binding} = {temp}.data.{variant.name};');o.append(f'{p}    (void){arm.binding};')
                for z in arm.body:o+=self.stmt(z,local,i+1)
                o.append(f'{p}    break;');o.append(f'{p}}}')
            o.append(f'{p}}}');return o
        if kind=='with_cap':
            o=[f'{p}/* merit capability begin: {node.capability_name} */']
            for z in node.nested_body:o+=self.stmt(z,env,i)
            o.append(f'{p}/* merit capability end: {node.capability_name} */')
            return o
        if kind=='if':
            o=[f'{p}if ({self.expr(node.condition,env)}) {{']
            for z in node.then_body:o+=self.stmt(z,env,i+1)
            o.append(f'{p}}} else {{')
            for z in node.else_body:o+=self.stmt(z,env,i+1)
            o.append(f'{p}}}');return o
        if kind=='while':
            o=[f'{p}while ({self.expr(node.condition,env)}) {{']
            for z in node.nested_body:o+=self.stmt(z,env,i+1)
            o.append(f'{p}}}');return o
        return []
    def env_type(self,env,n):
        v=env[n]; return v[0] if isinstance(v,tuple) else v
    def env_mode(self,env,n):
        v=env[n]; return v[1] if isinstance(v,tuple) else 'value'
    def etype(self,e,env):
        node=self.p.node(e);kind=node.kind
        if kind=='string':return 'String'
        if kind=='number':return 'i64'
        if kind=='var':return self.env_type(env,node.atom_value)
        if kind=='field':
            t=self.etype(node.field_base,env);return next(f.type_name for f in self.p.structs[t].fields if f.name==node.field_name)
        if kind=='struct_init':return node.constructed_type
        if kind in ('call','generic_call'):
            name,args=resolved_call(e)
            variants=[enum.name for enum in self.p.enums.values() for variant in enum.variants if variant.name==name]
            if variants:return variants[0]
            if name=='old':return self.etype(args[0],env)
            if name in BUILTIN_SIGS:return BUILTIN_SIGS[name].return_type
            vec=vec_builtin(name)
            if vec:
                op,elem=vec
                return vec_return_type(op,elem)
            return self.etype(args[0],env) if name.startswith('checked_') or name=='decimal_div' else self.fn[name]['return']
        if kind=='binop':return 'i32' if node.operator in ('==','!=','>=','<=','>','<') else self.etype(node.left,env)
    def address_expr(self,e,env):
        rendered=self.expr(e,env)
        node=self.p.node(e)
        if node.kind=='var' and self.env_mode(env,node.operand(0)) in ('borrow','borrow_mut'):
            return rendered
        if node.kind in ('call','generic_call'):
            called,_=resolved_call(node);callee=self.fn.get(called)
            if callee and callee.return_mode!='value':return rendered
        return '&'+rendered
    def expr(self,e,env,expected=None):
        node=self.p.node(e);kind=node.kind
        if kind=='string':
            raw=json.dumps(node.atom_value); return f'(merit_String){{{raw}, sizeof({raw})-1}}'
        if kind=='number':
            value=int(Decimal(node.atom_value)*(10**self.p.decimals[expected].scale)) if expected in self.p.decimals else int(Decimal(node.atom_value))
            if expected=='i64' and value==INT_RANGES['i64'][0]:return 'INT64_MIN'
            if expected=='u64' and value==INT_RANGES['u64'][1]:return 'UINT64_MAX'
            return str(value)
        if kind=='var':return '_merit_result' if node.atom_value=='result' and isinstance(env.get('result'),tuple) and env['result'][1]=='__result__' else node.atom_value
        if kind=='field':
            base=node.field_base; op='.'
            base_node=self.p.node(base)
            if base_node.kind=='var' and self.env_mode(env,base_node.atom_value) in ('borrow','borrow_mut'): op='->'
            elif base_node.kind in ('call','generic_call'):
                called,_=resolved_call(base_node);callee=self.fn.get(called)
                if callee and callee.return_mode!='value':op='->'
            return f'{self.expr(base,env)}{op}{node.field_name}'
        if kind=='struct_init':
            s=self.p.structs[node.constructed_type];return f'({self.ctype(node.constructed_type)}){{'+', '.join(f'.{f.name}={self.expr(node.field_values[f.name],env,f.type_name)}' for f in s.fields)+'}'
        if kind in ('call','generic_call'):
            n,a=resolved_call(e)
            variants=[(enum,variant) for enum in self.p.enums.values() for variant in enum.variants if variant.name==n]
            if variants:
                enum,variant=variants[0]
                rendered='' if variant.payload_type is None else self.expr(a[0],env,variant.payload_type)
                return f'merit_make_{enum.name}_{variant.name}({rendered})'
            if n=='old':return self.old_map[repr(a[0])]
            if n=='system_allocator': return 'merit_system_allocator()'
            if n=='portable_allocator': return 'merit_portable_allocator()'
            if n=='allocator_compatible': return f'merit_allocator_compatible({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='string_len': return f'((int64_t){self.expr(a[0],env)}.len)'
            if n=='string_byte': return f'((uint8_t){self.expr(a[0],env)}.data[{self.expr(a[1],env)}])'
            if n=='buffer_new': return f'merit_buffer_new({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='buffer_from_string': return f'merit_buffer_from_string({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='buffer_push': return f'(merit_buffer_push({self.address_expr(a[0],env)}, {self.expr(a[1],env)}), 0)'
            if n=='buffer_len': return f'merit_buffer_len({self.address_expr(a[0],env)})'
            if n=='buffer_get': return f'merit_buffer_get({self.address_expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='buffer_slice': return f'merit_buffer_slice({self.address_expr(a[0],env)}, {self.expr(a[1],env)}, {self.expr(a[2],env)})'
            if n=='buffer_allocator': return f'merit_buffer_allocator({self.address_expr(a[0],env)})'
            if n=='slice_len': return f'merit_slice_len({self.expr(a[0],env)})'
            if n=='slice_get': return f'merit_slice_get({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='i64vec_new': return f'merit_i64vec_new({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='i64vec_push': return f'(merit_i64vec_push({self.address_expr(a[0],env)}, {self.expr(a[1],env)}), 0)'
            if n=='i64vec_len': return f'merit_i64vec_len({self.address_expr(a[0],env)})'
            if n=='i64vec_get': return f'merit_i64vec_get({self.address_expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='i64vec_allocator': return f'merit_i64vec_allocator({self.address_expr(a[0],env)})'
            if n=='file_read': return f'merit_file_read({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='file_write': return f'merit_file_write({self.expr(a[0],env)}, {self.address_expr(a[1],env)})'
            vec=vec_builtin(n)
            if vec:
                op,elem=vec
                if op=='new': return f'merit_vec_new__{elem}({self.expr(a[0],env)}, {self.expr(a[1],env)})'
                if op=='push': return f'(merit_vec_push__{elem}({self.address_expr(a[0],env)}, {self.expr(a[1],env,elem)}), 0)'
                if op=='len': return f'merit_vec_len__{elem}({self.address_expr(a[0],env)})'
                if op=='allocator': return f'merit_vec_allocator__{elem}({self.address_expr(a[0],env)})'
                if op=='get': return f'merit_vec_get__{elem}({self.address_expr(a[0],env)}, {self.expr(a[1],env)})'
                if op=='set': return f'(merit_vec_set__{elem}({self.address_expr(a[0],env)}, {self.expr(a[1],env)}, {self.expr(a[2],env,elem)}), 0)'
                if op=='replace': return f'(merit_vec_replace__{elem}({self.address_expr(a[0],env)}, {self.expr(a[1],env)}, {self.expr(a[2],env,elem)}), 0)'
                if op=='pop': return f'merit_vec_pop__{elem}({self.address_expr(a[0],env)})'
                if op=='drop': return f'(merit_vec_drop__{elem}({self.address_expr(a[0],env)}), 0)'
                if op=='transfer': return f'(merit_vec_transfer__{elem}({self.address_expr(a[0],env)}, {self.address_expr(a[1],env)}), 0)'
            if n in ('checked_add','checked_sub','checked_mul','decimal_div'):
                t=self.etype(a[0],env);left=self.expr(a[0],env,t);right=self.expr(a[1],env,t)
                if t in self.p.decimals:
                    d=self.p.decimals[t];scale=10**d.scale;mode={'half_even':0,'half_up':1,'down':2,'ceiling':3,'floor':4}[d.rounding]
                    if n=='checked_add':return self.checked(t,f'merit_add({left}, {right})')
                    if n=='checked_sub':return self.checked(t,f'merit_sub({left}, {right})')
                    rendered=f'merit_round_div((__int128)({left}) * ({right}), {scale}, {mode})' if n=='checked_mul' else f'merit_round_div((__int128)({left}) * {scale}, ({right}), {mode})'
                    return self.checked(t,rendered)
                operation={'checked_add':'add','checked_sub':'sub','checked_mul':'mul','decimal_div':'div'}[n]
                base=self.p.bounded[t].base if t in self.p.bounded else t
                return self.checked(t,f'merit_{operation}_{base}({left}, {right})')
            callee=self.fn[n];rendered=[]
            for x,param in zip(a,callee.params):
                ex=self.expr(x,env,param.type_name);rendered.append(self.address_expr(x,env) if param.mode in ('borrow','borrow_mut') else ex)
            return f'merit_{n}('+', '.join(rendered)+')'
        if kind=='binop':
            t=expected or self.etype(node.left,env);left=self.expr(node.left,env,t);right=self.expr(node.right,env,t)
            operations={'+':'add','-':'sub','*':'mul','/':'div'}
            if node.operator in operations:
                operation=operations[node.operator]
                if t in self.p.decimals:
                    decimal=self.p.decimals[t];scale=10**decimal.scale;mode={'half_even':0,'half_up':1,'down':2,'ceiling':3,'floor':4}[decimal.rounding]
                    if operation=='add':rendered=f'merit_add({left}, {right})'
                    elif operation=='sub':rendered=f'merit_sub({left}, {right})'
                    elif operation=='mul':rendered=f'merit_round_div((__int128)({left}) * ({right}), {scale}, {mode})'
                    else:rendered=f'merit_round_div((__int128)({left}) * {scale}, ({right}), {mode})'
                    return self.checked(t,rendered)
                base=self.p.bounded[t].base if t in self.p.bounded else t
                if base in INT_RANGES:return self.checked(t,f'merit_{operation}_{base}({left}, {right})')
            return f'({left} {node.operator} {right})'

def semantic_payload(value,p):
    if isinstance(value,SemanticNode):
        provenance=p.provenance(value)
        return {
            'kind':value.kind,
            'operands':[semantic_payload(item,p) for item in value.operands],
            'provenance':{
                'primary':dataclasses.asdict(provenance.primary) if provenance.primary else None,
                'related':dataclasses.asdict(provenance.related) if provenance.related else None,
            },
        }
    if isinstance(value,list):return [semantic_payload(item,p) for item in value]
    if isinstance(value,tuple):return [semantic_payload(item,p) for item in value]
    if isinstance(value,dict):return {key:semantic_payload(item,p) for key,item in value.items()}
    if dataclasses.is_dataclass(value):return {field.name:semantic_payload(getattr(value,field.name),p) for field in dataclasses.fields(value)}
    return value

def hir(p):
    return {'module':p.module,'types':{'decimal':[dataclasses.asdict(x) for x in p.decimals.values()],'bounded':[dataclasses.asdict(x) for x in p.bounded.values()],'enum':[dataclasses.asdict(x) for x in p.enums.values()],'trait':[dataclasses.asdict(x) for x in p.traits.values()],'struct':[{'name':s.name,'stable_abi':s.stable_abi,'fields':[dataclasses.asdict(f) for f in s.fields]} for s in p.structs.values()]},'type_semantics':TypeTable(p).all(),'impls':[dataclasses.asdict(x) for x in p.impls],'destructors':[{'type':d.type_name,'body':semantic_payload(d.body,p),'provenance':semantic_payload(d.provenance,p)} for d in p.destructors.values()],'functions':[f.to_dict(lambda value:semantic_payload(value,p)) if isinstance(f,FunctionDecl) else semantic_payload(dict(f),p) for f in p.functions]}
def reachable_mir_blocks(blocks):
    by_id={block['id']:block for block in blocks}; reachable=set(); pending=[0]
    while pending:
        block_id=pending.pop()
        if block_id in reachable or block_id not in by_id:continue
        reachable.add(block_id);terminator=by_id[block_id]['terminator'];kind=terminator['kind']
        if kind=='goto':pending.append(terminator['target'])
        elif kind=='branch':pending.extend((terminator['then'],terminator['else']))
        elif kind=='switch':pending.extend(arm['target'] for arm in terminator['arms'])
    return [block for block in blocks if block['id'] in reachable]
def constant_mir_value(p,expression):
    node=p.node(expression)
    if node.kind=='number':return int(Decimal(node.atom_value))
    if node.kind!='binop':return None
    left=constant_mir_value(p,node.left);right=constant_mir_value(p,node.right)
    if left is None or right is None:return None
    if node.operator=='+':return left+right
    if node.operator=='-':return left-right
    if node.operator=='*':return left*right
    if node.operator=='/':return int(Decimal(left)/Decimal(right)) if right!=0 else None
    comparisons={'==':left==right,'!=':left!=right,'>=':left>=right,'<=':left<=right,'>':left>right,'<':left<right}
    return int(comparisons[node.operator]) if node.operator in comparisons else None
def fold_constant_mir_branches(p,blocks):
    for block in blocks:
        terminator=block['terminator']
        if terminator['kind']!='branch':continue
        value=constant_mir_value(p,terminator['condition'])
        if value is None:continue
        block['terminator']={'kind':'goto','target':terminator['then'] if value!=0 else terminator['else'],'folded_condition':terminator['condition']}
    return blocks
def mir(p):
    types=TypeTable(p);ownership_model=OwnershipEffects(p,types)
    def lower_function(f):
        blocks=[]
        next_id=0
        def new_block(statements=None, terminator=None):
            nonlocal next_id
            block={'id':next_id,'statements':statements or [],'terminator':terminator or {'kind':'fallthrough'}}
            next_id+=1; blocks.append(block); return block
        entry=new_block()
        def lower_seq(body,current):
            for st in body:
                node=p.node(st);kind=node.kind
                if kind=='if':
                    then_b=new_block(); else_b=new_block(); join_b=new_block()
                    current['terminator']={'kind':'branch','condition':node.condition,'then':then_b['id'],'else':else_b['id']}
                    end_then=lower_seq(node.then_body,then_b); end_else=lower_seq(node.else_body,else_b)
                    if end_then['terminator']['kind']=='fallthrough': end_then['terminator']={'kind':'goto','target':join_b['id']}
                    if end_else['terminator']['kind']=='fallthrough': end_else['terminator']={'kind':'goto','target':join_b['id']}
                    current=join_b
                elif kind=='while':
                    cond_b=new_block(); body_b=new_block(); exit_b=new_block()
                    current['terminator']={'kind':'goto','target':cond_b['id']}
                    cond_b['terminator']={'kind':'branch','condition':node.condition,'then':body_b['id'],'else':exit_b['id']}
                    end_body=lower_seq(node.nested_body,body_b)
                    if end_body['terminator']['kind']=='fallthrough': end_body['terminator']={'kind':'goto','target':cond_b['id']}
                    current=exit_b
                elif kind=='match':
                    arm_blocks=[]; join_b=new_block()
                    for arm in node.match_arms:
                        b=new_block(); arm_blocks.append({'variant':arm.variant,'binding':arm.binding,'target':b['id']})
                        end_arm=lower_seq(arm.body,b)
                        if end_arm['terminator']['kind']=='fallthrough': end_arm['terminator']={'kind':'goto','target':join_b['id']}
                    current['terminator']={'kind':'switch','subject':node.expression,'arms':arm_blocks}
                    current=join_b
                elif kind=='return':
                    current['terminator']={'kind':'return','value':node.expression}; current=new_block()
                else:
                    current['statements'].append(st)
            return current
        tail=lower_seq(f.body,entry)
        if tail['terminator']['kind']=='fallthrough': tail['terminator']={'kind':'return','value':None}
        blocks=reachable_mir_blocks(fold_constant_mir_branches(p,blocks))
        ownership=ownership_model.function(f)
        locals_order=[name for name,_ in ownership.owned_locals]
        entry['statements'].extend(
            ('drop_implicit',name)
            for name in reversed(locals_order)
            if name not in ownership.explicit_drops and name not in ownership.consumed_roots
        )
        sites={name:(dataclasses.asdict(span) if span else None) for name,span in ownership.consumption_sites}
        return {'name':f.name,'params':semantic_payload(f.params,p),'return':f.return_type,'owned_locals':locals_order,'explicit_drops':sorted(ownership.explicit_drops),'consumed_roots':sorted(ownership.consumed_roots),'consumption_sites':sites,'semantic_blocks':semantic_payload(blocks,p)}
    return {'module':p.module,'destructors':[{'type':d.type_name,'semantic_body':semantic_payload(d.body,p),'provenance':semantic_payload(d.provenance,p)} for d in p.destructors.values()],'functions':[lower_function(f) for f in p.functions]}


def compile_file(path,out=None):
    p=parse(path.read_text(),str(path));ch=Checker(p).check();cg=CGenerator(p);exe=out or path.with_suffix('');cpath=exe.with_suffix('.c');hpath=exe.with_suffix('.h');cpath.write_text(cg.generate());hpath.write_text(cg.header());subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2','-Wall','-Wextra',str(cpath),'-o',str(exe)],check=True);return ch,cpath,hpath,exe

PROGRAM_TEMPLATE = """module {module}

fn main() -> i32 {{
    print(42);
    return 0;
}}
"""

def _create_project(target: Path, name: str | None = None) -> Path:
    target = target.resolve()
    module = re.sub(r'[^A-Za-z0-9_]', '_', name or target.name)
    if not module or module[0].isdigit():
        module = 'merit_' + module
    target.mkdir(parents=True, exist_ok=False)
    (target / 'src').mkdir()
    (target / 'src' / 'main.mrt').write_text(PROGRAM_TEMPLATE.format(module=module))
    (target / 'README.md').write_text(
        f'# {module}\n\n'
        'Build and run:\n\n'
        '```bash\n'
        'merit check src/main.mrt\n'
        'merit verify src/main.mrt\n'
        'merit exec src/main.mrt\n'
        '```\n'
    )
    return target / 'src' / 'main.mrt'

def main(argv=None):
    ap=argparse.ArgumentParser(prog='merit',description='Merit 0.1 experimental compiler')
    sub=ap.add_subparsers(dest='cmd',required=True)
    source_commands=('check','run','build','exec','verify','audit','emit-c','emit-h','layout','emit-hir','emit-mir')
    for n in source_commands:
        q=sub.add_parser(n)
        q.add_argument('source')
        q.add_argument('--diagnostic-format',choices=('text','json'),default='text')
        if n in ('build','exec'):q.add_argument('-o','--output')
    q=sub.add_parser('new',help='create a small Merit project')
    q.add_argument('directory')
    q.add_argument('--name')
    ns=ap.parse_args(argv)
    try:
        if ns.cmd=='new':
            main_file=_create_project(Path(ns.directory),ns.name)
            print(f'created {main_file.parent.parent}')
            print(f'entry point: {main_file}')
            return 0
        path=Path(ns.source)
        if not path.exists(): raise FileNotFoundError(path)
        p=parse(path.read_text(),str(path));ch=Checker(p).check()
        if ns.cmd=='check':print(f'ok: {p.module} ({len(p.functions)} functions, {len(p.structs)} structs)')
        elif ns.cmd=='run':Interpreter(p).run()
        elif ns.cmd=='verify':
            interpreted=io.StringIO()
            with contextlib.redirect_stdout(interpreted): Interpreter(p).run()
            with tempfile.TemporaryDirectory() as td:
                exe=Path(td)/'program'
                compile_file(path,exe)
                native=subprocess.run([str(exe)],check=True,text=True,capture_output=True).stdout
            if interpreted.getvalue()!=native:
                raise RuntimeError('interpreter/native mismatch\n--- interpreter ---\n'+interpreted.getvalue()+'--- native ---\n'+native)
            print(f'verified: interpreter and native outputs match ({len(native.encode())} bytes)')
        elif ns.cmd=='audit':print(json.dumps(audit_payload(p,ch),indent=2))
        elif ns.cmd=='emit-c':print(CGenerator(p).generate())
        elif ns.cmd=='emit-h':print(CGenerator(p).header())
        elif ns.cmd=='layout':print(json.dumps(LayoutEngine(p).all(),indent=2))
        elif ns.cmd=='emit-hir':print(json.dumps(hir(p),indent=2,default=str))
        elif ns.cmd=='emit-mir':print(json.dumps(mir(p),indent=2,default=str))
        elif ns.cmd in ('build','exec'):
            output=Path(ns.output) if ns.output else path.with_suffix('')
            _,c,h,e=compile_file(path,output)
            if ns.cmd=='build':print(f'built {e}\nemitted {c}\nemitted {h}')
            else:
                completed=subprocess.run([str(e.resolve())])
                return completed.returncode
    except CompileError as e:
        from merit.diagnostics import diagnostic_from_exception,render_exception
        if getattr(ns,'diagnostic_format','text')=='json':print(json.dumps(diagnostic_from_exception(e,path,path.read_text()).to_dict()),file=sys.stderr)
        else:print(render_exception(e,path,path.read_text()),file=sys.stderr)
        return 1
    except Exception as e:
        if getattr(ns,'diagnostic_format','text')=='json':
            from merit.diagnostics import diagnostic_from_exception
            diagnostic_path=locals().get('path',Path(getattr(ns,'source','<unknown>')))
            source=diagnostic_path.read_text() if diagnostic_path.is_file() else ''
            print(json.dumps(diagnostic_from_exception(e,diagnostic_path,source).to_dict()),file=sys.stderr)
        else:print(f'error: {e}',file=sys.stderr)
        return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
