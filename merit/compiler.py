from __future__ import annotations

import argparse, contextlib, dataclasses, hashlib, io, json, os, re, subprocess, sys, tempfile
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_DOWN, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any
from lark import Lark, Transformer

GRAMMAR=r'''
start: module_decl declaration*
module_decl: "module" CNAME
?declaration: enum_decl | trait_decl | decimal_decl | bounded_decl | capability_decl | struct_decl | function_decl
enum_decl: "enum" CNAME "{" enum_variant ("," enum_variant)* [","] "}"
enum_variant: CNAME ["(" type_ref ")"]
trait_decl: "trait" CNAME "{" trait_method* "}"
trait_method: "fn" CNAME "(" [params] ")" "->" type_ref ";"
decimal_decl: "decimal" CNAME "(" INT "," INT "," CNAME ")" ";"
bounded_decl: "bounded" CNAME "(" BASE_INT "," SIGNED_NUMBER "," SIGNED_NUMBER ")" ";"
capability_decl: "capability" CNAME ";"
struct_decl: ["stable" "(" ESCAPED_STRING ")"] "struct" CNAME "{" field_decl* "}"
field_decl: CNAME ":" type_ref ";"
function_decl: "fn" CNAME "(" [params] ")" "->" type_ref effects? requires_caps? contract* block
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
?statement: let_stmt | var_stmt | try_let_stmt | assign_stmt | return_stmt | print_stmt | expr_stmt | drop_stmt | with_capability | if_stmt | while_stmt | match_stmt
let_stmt: "let" CNAME ":" type_ref "=" expr ";"
var_stmt: "var" CNAME ":" type_ref "=" expr ";"
try_let_stmt: "let" CNAME ":" type_ref "=" "try" expr ";"
assign_stmt: postfix "=" expr ";"
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
@dataclasses.dataclass(frozen=True)
class TraitMethod: name:str; params:tuple[tuple[str,str,str],...]; return_type:str
@dataclasses.dataclass(frozen=True)
class TraitType: name:str; methods:tuple[TraitMethod,...]
@dataclasses.dataclass(frozen=True)
class Field: name:str; type_name:str
@dataclasses.dataclass(frozen=True)
class StructType: name:str; fields:tuple[Field,...]; stable_abi:str|None
@dataclasses.dataclass
class Program:
    module:str; decimals:dict[str,DecimalType]; bounded:dict[str,BoundedType]; capabilities:set[str]; structs:dict[str,StructType]; functions:list[dict[str,Any]]; enums:dict[str,EnumType]=dataclasses.field(default_factory=dict); traits:dict[str,TraitType]=dataclasses.field(default_factory=dict)

class ASTBuilder(Transformer):
    def module_decl(self,x): return str(x[0])
    def enum_variant(self,x): return EnumVariant(str(x[0]), x[1] if len(x)>1 else None)
    def enum_decl(self,x): return ('enum', EnumType(str(x[0]), tuple(x[1:])))
    def trait_method(self,x):
        name=str(x[0]); i=1; params=[]
        if i<len(x) and x[i] is None:i+=1
        elif i<len(x) and isinstance(x[i],list):params=x[i];i+=1
        return TraitMethod(name, tuple(params), x[i])
    def trait_decl(self,x): return ('trait', TraitType(str(x[0]), tuple(x[1:])))
    def decimal_decl(self,x): return ('decimal',DecimalType(str(x[0]),int(x[1]),int(x[2]),str(x[3])))
    def bounded_decl(self,x): return ('bounded',BoundedType(str(x[0]),str(x[1]),int(Decimal(str(x[2]))),int(Decimal(str(x[3])))))
    def capability_decl(self,x): return ('capability',str(x[0]))
    def type_ref(self,x): return str(x[0]) if x else 'void'
    def field_decl(self,x): return Field(str(x[0]),x[1])
    def struct_decl(self,x):
        x=[v for v in x if v is not None]
        abi=None; i=0
        if x and str(x[0]).startswith('"'): abi=str(x[0])[1:-1]; i=1
        name=str(x[i]); return ('struct',StructType(name,tuple(x[i+1:]),abi))
    def param_borrow_mut(self,x): return (str(x[0]),x[1],'borrow_mut')
    def param_borrow(self,x): return (str(x[0]),x[1],'borrow')
    def param_value(self,x): return (str(x[0]),x[1],'value')
    def params(self,x): return list(x)
    def name_list(self,x): return [str(v) for v in x]
    def effects(self,x): return ('effects',x[0] if x else [])
    def requires_caps(self,x): return ('requires_caps',x[0] if x else [])
    def precontract(self,x): return ('pre',x[0])
    def postcontract(self,x): return ('post',x[0])
    def string(self,x): return ('string',json.loads(str(x[0])))
    def number(self,x): return ('number',str(x[0]))
    def variable(self,x): return ('var',str(x[0]))
    def args(self,x): return list(x)
    def field_init(self,x): return (str(x[0]),x[1])
    def field_inits(self,x): return list(x)
    def struct_init(self,x): return ('struct_init',str(x[0]),dict(x[1]) if len(x)>1 else {})
    def call(self,x): return ('call',str(x[0]),x[1] if len(x)>1 and x[1] is not None else [])
    def postfix(self,x):
        node=x[0]
        for f in x[1:]: node=('field',node,str(f))
        return node
    def comparison(self,x): return x[0] if len(x)==1 else ('binop',str(x[1]),x[0],x[2])
    def sum(self,x):
        n=x[0]
        for i in range(1,len(x),2): n=('binop',str(x[i]),n,x[i+1])
        return n
    def product(self,x):
        n=x[0]
        for i in range(1,len(x),2): n=('binop',str(x[i]),n,x[i+1])
        return n
    def let_stmt(self,x): return ('let',str(x[0]),x[1],x[2],False)
    def var_stmt(self,x): return ('let',str(x[0]),x[1],x[2],True)
    def try_let_stmt(self,x): return ('try_let',str(x[0]),x[1],x[2])
    def assign_stmt(self,x): return ('assign',x[0],x[1])
    def return_stmt(self,x): return ('return',x[0])
    def print_stmt(self,x): return ('print',x[0])
    def expr_stmt(self,x): return ('expr',x[0])
    def drop_stmt(self,x): return ('drop',str(x[0]))
    def block(self,x): return list(x)
    def with_capability(self,x): return ('with_cap',str(x[0]),x[1])
    def if_stmt(self,x): return ('if',x[0],x[1],x[2] if len(x)>2 and x[2] is not None else [])
    def while_stmt(self,x): return ('while',x[0],x[1])
    def match_arm(self,x): return (str(x[0]), str(x[1]) if len(x)==3 and x[1] is not None else None, x[-1])
    def match_stmt(self,x): return ('match',x[0],list(x[1:]))
    def function_decl(self,x):
        name=str(x[0]); i=1; params=[]
        if i<len(x) and x[i] is None:i+=1
        elif i<len(x) and isinstance(x[i],list):params=x[i];i+=1
        ret=x[i];i+=1; effects=[]; caps=[]; pre=[]; post=[]
        while i<len(x)-1:
            tag,val=x[i]
            if tag=='effects':effects=val
            elif tag=='requires_caps':caps=val
            elif tag=='pre':pre.append(val)
            elif tag=='post':post.append(val)
            i+=1
        return ('function',{'name':name,'params':params,'return':ret,'effects':effects,'requires_caps':caps,'pre':pre,'post':post,'body':x[-1]})
    def start(self,x):
        ds={};bs={};cs=set();ss={};es={};ts={};fs=[];symbols={}
        def add_symbol(kind,name):
            if name in symbols: raise CompileError(f'M0002: duplicate top-level symbol {name}')
            symbols[name]=kind
        for k,v in x[1:]:
            if k in ('decimal','bounded','struct','enum','trait'):
                add_symbol(k,v.name)
            elif k=='function':
                add_symbol(k,v['name'])
            {'decimal':lambda:ds.__setitem__(v.name,v),'bounded':lambda:bs.__setitem__(v.name,v),'capability':lambda:cs.add(v),'struct':lambda:ss.__setitem__(v.name,v),'enum':lambda:es.__setitem__(v.name,v),'trait':lambda:ts.__setitem__(v.name,v),'function':lambda:fs.append(v)}[k]()
        return Program(x[0],ds,bs,cs,ss,fs,es,ts)

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
        templates[m.group(2)]={'kind':m.group(1),'name':m.group(2),'params':params,'bounds':bounds,'text':source[m.start():end]}
        spans.append((m.start(),end)); pos=end
    for a,b in reversed(spans): source=source[:a]+source[b:]
    return source,templates

def _replace_applications(text: str, templates: dict, requested: set[tuple[str,tuple[str,...]]]) -> str:
    # Qualified enum variants are rewritten before ordinary applications.
    changed=True
    while changed:
        changed=False
        for name in templates:
            pat=re.compile(r'\b'+re.escape(name)+r'<([^<>]+)>::([A-Za-z_]\w*)')
            def qrepl(m):
                nonlocal changed
                args=_split_generic_args(m.group(1)); requested.add((name,tuple(args))); changed=True
                return _mangle_generic(name,args)+'__'+m.group(2)
            text=pat.sub(qrepl,text)
        for name in templates:
            pat=re.compile(r'\b'+re.escape(name)+r'<([^<>]+)>')
            def repl(m):
                nonlocal changed
                args=_split_generic_args(m.group(1)); requested.add((name,tuple(args))); changed=True
                return _mangle_generic(name,args)
            text=pat.sub(repl,text)
    return text

def _generic_trait_satisfied(type_name: str, trait: str) -> bool:
    scalar=set(INT_RANGES)|{'String'}
    if trait in ('Copy','Eq','Ord','Display'): return type_name in scalar
    return False

def expand_generics(source: str) -> str:
    source,templates=_extract_generic_templates(source)
    if not templates: return source
    requested=set()
    source=_replace_applications(source,templates,requested)
    generated=[]; done=set()
    while True:
        pending=[x for x in requested if x not in done]
        if not pending: break
        name,args=pending[0]; done.add((name,args)); t=templates[name]
        if len(args)!=len(t['params']): raise CompileError(f'M7001: {name} expects {len(t["params"])} type arguments')
        for param,arg in zip(t['params'],args):
            for trait in t['bounds'].get(param,[]):
                if not _generic_trait_satisfied(arg,trait): raise CompileError(f'M7002: type {arg} does not satisfy generic bound {trait} for {name}.{param}')
        text=t['text']
        # Rewrite declaration header and substitute type parameters token-wise.
        text=re.sub(r'\b'+re.escape(t['kind'])+r'\s+'+re.escape(name)+r'\s*<[^>{}]+>', t['kind']+' '+_mangle_generic(name,list(args)), text, count=1)
        for param,arg in zip(t['params'],args): text=re.sub(r'\b'+re.escape(param)+r'\b',arg,text)
        if t['kind']=='enum':
            # Constructor names are nominally scoped by the instantiated enum.
            head_end=text.find('{'); body=text[head_end+1:text.rfind('}')]
            variants=re.findall(r'\b([A-Za-z_]\w*)\s*(?:\(|,|\})', body+',')
            for variant in sorted(set(variants),key=len,reverse=True):
                text=re.sub(r'\b'+re.escape(variant)+r'\b',_mangle_generic(name,list(args))+'__'+variant,text)
        text=_replace_applications(text,templates,requested)
        generated.append(text)
    return source+'\n'+'\n'.join(generated)+'\n'

def parse(s:str)->Program:
    return ASTBuilder().transform(PARSER.parse(expand_generics(s)))
BUILTIN_TYPES={'String','Buffer','Allocator','ByteSlice','I64Vec'}
OWNED_BUILTINS={'Buffer','I64Vec'}
ROUNDING={'half_even':ROUND_HALF_EVEN,'half_up':ROUND_HALF_UP,'down':ROUND_DOWN,'ceiling':ROUND_CEILING,'floor':ROUND_FLOOR}
INT_RANGES={'i8':(-2**7,2**7-1),'i16':(-2**15,2**15-1),'i32':(-2**31,2**31-1),'i64':(-2**63,2**63-1),'u8':(0,255),'u16':(0,65535),'u32':(0,2**32-1),'u64':(0,2**64-1)}
class CompileError(Exception):pass
@dataclasses.dataclass
class TypedValue: type_name:str; value:Any
@dataclasses.dataclass
class VarState: type_name:str; mutable:bool; moved:bool=False; dropped:bool=False; mode:str="value"

class Checker:
    def __init__(self,p):self.p=p;self.fn={f['name']:f for f in p.functions};self.audit_sites=[];self.call_edges=[]
    def check(self):
        if 'main' not in self.fn:raise CompileError('M0001: program requires fn main')
        for d in self.p.decimals.values():
            if d.precision<1 or d.scale<0 or d.scale>d.precision:raise CompileError(f'M1001: invalid decimal {d.name}')
            if d.rounding not in ROUNDING:raise CompileError(f'M1002: unsupported rounding policy {d.rounding}')
        for b in self.p.bounded.values():
            lo,hi=INT_RANGES[b.base]
            if not(lo<=b.minimum<=b.maximum<=hi):raise CompileError(f'M1101: bounds for {b.name} exceed {b.base}')
        for e in self.p.enums.values():
            if not e.variants: raise CompileError(f'M6000: enum {e.name} requires at least one variant')
            seen_variants=set()
            for variant in e.variants:
                if variant.name in seen_variants: raise CompileError(f'M6001: duplicate variant {variant.name} in {e.name}')
                seen_variants.add(variant.name)
                if variant.payload_type is not None: self.ensure_type(variant.payload_type)
        for t in self.p.traits.values():
            if not t.methods: raise CompileError(f'M7100: trait {t.name} requires at least one method')
            seen_methods=set()
            for method in t.methods:
                if method.name in seen_methods: raise CompileError(f'M7101: duplicate method {method.name} in trait {t.name}')
                seen_methods.add(method.name)
                self.ensure_trait_signature_type(method.return_type)
                for _, type_name, _ in method.params: self.ensure_trait_signature_type(type_name)
        for s in self.p.structs.values():
            seen=set()
            for fld in s.fields:
                self.ensure_type(fld.type_name)
                if fld.name in seen:raise CompileError(f'M4001: duplicate field {fld.name} in {s.name}')
                seen.add(fld.name)
        for f in self.p.functions:
            self.ensure_type(f['return'])
            missing=set(f['requires_caps'])-self.p.capabilities
            if missing:raise CompileError(f"M2001: function {f['name']} requires undeclared capabilities: {sorted(missing)}")
            env={n:VarState(t,mode=='borrow_mut',False,False,mode) for n,t,mode in f['params']}
            for e in f['pre']:self.expr_type(e,env,set(f['requires_caps']),f)
            self.block(f['body'],env,set(f['requires_caps']),f)
            post_env=dict(env); post_env['result']=VarState(f['return'],False)
            for e in f['post']:self.expr_type(e,post_env,set(f['requires_caps']),f)
        return self
    def ensure_type(self,t):
        if t not in INT_RANGES and t not in self.p.decimals and t not in self.p.bounded and t not in self.p.structs and t not in self.p.enums and t not in BUILTIN_TYPES and t!='void':raise CompileError(f'M3000: unknown type {t}')
    def ensure_trait_signature_type(self,t):
        if t!='Self': self.ensure_type(t)
    def block(self,body,env,caps,fn):
        for st in body:
            tag=st[0]
            if tag=='let':
                _,n,t,e,mut=st;self.ensure_type(t);et=self.expr_type(e,env,caps,fn)
                if et not in (t,'number'):raise CompileError(f'M3001: cannot assign {et} to {t} in {n}')
                if e[0]=='number':self.validate_literal(t,e[1])
                if e[0]=='var' and e[1] in env and (env[e[1]].type_name in self.p.structs or env[e[1]].type_name in OWNED_BUILTINS):
                    if env[e[1]].moved:raise CompileError(f'M5001: use of moved value {e[1]}')
                    env[e[1]].moved=True
                env[n]=VarState(t,mut)
            elif tag=='try_let':
                _,n,t,e=st; self.ensure_type(t)
                et=self.expr_type(e,env,caps,fn); enum=self.p.enums.get(et)
                if not enum or [v.name for v in enum.variants] != ['Ok','Err']:
                    raise CompileError('M6200: try requires an enum with Ok and Err variants')
                ok=enum.variants[0]
                if ok.payload_type != t: raise CompileError(f'M6201: try Ok payload is {ok.payload_type}, binding expects {t}')
                ret_enum=self.p.enums.get(fn['return'])
                if not ret_enum or [v.name for v in ret_enum.variants] != ['Ok','Err']:
                    raise CompileError('M6202: function using try must return a Result-style enum')
                if ret_enum.variants[1].payload_type != enum.variants[1].payload_type:
                    raise CompileError('M6203: try error payload does not match function return error type')
                env[n]=VarState(t,False)
            elif tag=='assign':
                lt=self.lvalue_type(st[1],env,True);rt=self.expr_type(st[2],env,caps,fn)
                if rt not in (lt,'number'):raise CompileError(f'M3006: cannot assign {rt} to {lt}')
            elif tag=='return':
                et=self.expr_type(st[1],env,caps,fn)
                if et not in (fn['return'],'number'):raise CompileError(f"M3002: return type {et} does not match {fn['return']}")
            elif tag in ('print','expr'):self.expr_type(st[1],env,caps,fn)
            elif tag=='drop':
                n=st[1]
                if n not in env: raise CompileError(f'M5100: cannot drop unknown binding {n}')
                if env[n].moved or env[n].dropped: raise CompileError(f'M5101: binding {n} already consumed')
                if env[n].mode in ('borrow','borrow_mut'): raise CompileError(f'M5102: cannot drop borrowed parameter {n}')
                env[n].dropped=True
            elif tag=='match':
                subject_t=self.expr_type(st[1],env,caps,fn); enum=self.p.enums.get(subject_t)
                if not enum: raise CompileError(f'M6100: match requires enum value, got {subject_t}')
                arms=st[2]; names=[a[0] for a in arms]; expected=[v.name for v in enum.variants]
                if len(names)!=len(set(names)): raise CompileError('M6101: duplicate match arm')
                missing=set(expected)-set(names); extra=set(names)-set(expected)
                if missing or extra: raise CompileError(f'M6102: non-exhaustive match; missing={sorted(missing)} extra={sorted(extra)}')
                states=[]
                for variant in enum.variants:
                    arm=next(a for a in arms if a[0]==variant.name); local={k:dataclasses.replace(v) for k,v in env.items()}
                    binding=arm[1]
                    if variant.payload_type is None and binding is not None: raise CompileError(f'M6103: variant {variant.name} has no payload')
                    if variant.payload_type is not None and binding is None: raise CompileError(f'M6104: variant {variant.name} requires payload binding')
                    if binding is not None: local[binding]=VarState(variant.payload_type,False)
                    self.block(arm[2],local,caps,fn); states.append(local)
                for k in env:
                    env[k].moved=any(state[k].moved for state in states)
                    env[k].dropped=any(state[k].dropped for state in states)
            elif tag=='with_cap':
                cap=st[1]
                if cap not in self.p.capabilities:raise CompileError(f'M2002: undeclared capability {cap}')
                self.audit_sites.append({'function':fn['name'],'capability':cap})
                self.block(st[2],env,caps|{cap},fn)
            elif tag=='if':
                ct=self.expr_type(st[1],env,caps,fn)
                if ct not in ('i32','number'): raise CompileError('M3300: if condition must be boolean/comparison')
                left={k:dataclasses.replace(v) for k,v in env.items()}; right={k:dataclasses.replace(v) for k,v in env.items()}
                self.block(st[2],left,caps,fn); self.block(st[3],right,caps,fn)
                for k in env:
                    env[k].moved=left[k].moved or right[k].moved
                    env[k].dropped=left[k].dropped or right[k].dropped
            elif tag=='while':
                ct=self.expr_type(st[1],env,caps,fn)
                if ct not in ('i32','number'): raise CompileError('M3301: while condition must be boolean/comparison')
                loop={k:dataclasses.replace(v) for k,v in env.items()}; self.block(st[2],loop,caps,fn)
                for k in env:
                    env[k].moved=env[k].moved or loop[k].moved
                    env[k].dropped=env[k].dropped or loop[k].dropped
    def lvalue_type(self,e,env,write=False):
        if e[0]=='var':
            n=e[1]
            if n not in env:raise CompileError(f'M3003: unknown variable {n}')
            if env[n].moved:raise CompileError(f'M5001: use of moved value {n}')
            if env[n].dropped:raise CompileError(f'M5103: use of dropped value {n}')
            if write and not env[n].mutable:raise CompileError(f'M5002: cannot assign to immutable binding {n}')
            return env[n].type_name
        if e[0]=='field':
            base=e[1];bt=self.lvalue_type(base,env,write);s=self.p.structs.get(bt)
            if not s:raise CompileError(f'M4002: {bt} has no fields')
            for fld in s.fields:
                if fld.name==e[2]:return fld.type_name
            raise CompileError(f'M4003: unknown field {e[2]} on {bt}')
        raise CompileError('M3007: invalid assignment target')
    def expr_type(self,e,env,caps,fn):
        tag=e[0]
        if tag=='string':return 'String'
        if tag=='number':return 'number'
        if tag=='var':return self.lvalue_type(e,env)
        if tag=='field':return self.lvalue_type(e,env)
        if tag=='struct_init':
            name,vals=e[1],e[2];s=self.p.structs.get(name)
            if not s:raise CompileError(f'M4004: unknown struct {name}')
            expected={f.name:f for f in s.fields}
            if set(vals)!=set(expected):raise CompileError(f'M4005: {name} fields must be {sorted(expected)}')
            for n,x in vals.items():
                t=self.expr_type(x,env,caps,fn)
                if t not in (expected[n].type_name,'number'):raise CompileError(f'M4006: field {n} expects {expected[n].type_name}, got {t}')
                if x[0]=='number':self.validate_literal(expected[n].type_name,x[1])
            return name
        if tag=='call':
            name,args=e[1],e[2]
            variants=[(enum,variant) for enum in self.p.enums.values() for variant in enum.variants if variant.name==name]
            if variants:
                if len(variants)>1: raise CompileError(f'M6002: ambiguous enum constructor {name}')
                enum,variant=variants[0]
                expected_count=0 if variant.payload_type is None else 1
                if len(args)!=expected_count: raise CompileError(f'M6003: {name} expects {expected_count} arguments')
                if expected_count:
                    at=self.expr_type(args[0],env,caps,fn)
                    if at not in (variant.payload_type,'number'): raise CompileError(f'M6004: {name} expects {variant.payload_type}, got {at}')
                    if args[0][0]=='number': self.validate_literal(variant.payload_type,args[0][1])
                return enum.name
            if name=='old':
                if len(args)!=1: raise CompileError('M3200: old expects one argument')
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
            builtin_sigs={
                'system_allocator':([], 'Allocator', None),
                'string_len':([('value','String')], 'i64', None),
                'string_byte':([('value','String'),('value','i64')], 'u8', None),
                'buffer_new':([('value','Allocator'),('value','i64')], 'Buffer', 'allocate'),
                'buffer_from_string':([('value','Allocator'),('value','String')], 'Buffer', 'allocate'),
                'buffer_push':([('borrow_mut','Buffer'),('value','u8')], 'void', None),
                'buffer_len':([('borrow','Buffer')], 'i64', None),
                'buffer_get':([('borrow','Buffer'),('value','i64')], 'i64', None),
                'buffer_slice':([('borrow','Buffer'),('value','i64'),('value','i64')], 'ByteSlice', None),
                'slice_len':([('value','ByteSlice')], 'i64', None),
                'slice_get':([('value','ByteSlice'),('value','i64')], 'i64', None),
                'i64vec_new':([('value','Allocator'),('value','i64')], 'I64Vec', 'allocate'),
                'i64vec_push':([('borrow_mut','I64Vec'),('value','i64')], 'void', None),
                'i64vec_len':([('borrow','I64Vec')], 'i64', None),
                'i64vec_get':([('borrow','I64Vec'),('value','i64')], 'i64', None),
                'file_read':([('value','Allocator'),('value','String')], 'Buffer', 'file_read'),
            }
            if name in builtin_sigs:
                params,ret,cap=builtin_sigs[name]
                if cap and cap not in caps: raise CompileError(f'M2003: call to {name} requires capabilities {[cap]}')
                if len(args)!=len(params): raise CompileError(f'M3005: {name} expects {len(params)} arguments')
                loans=[]
                for idx,(arg,(mode,pt)) in enumerate(zip(args,params)):
                    at=self.expr_type(arg,env,caps,fn)
                    if at not in (pt,'number'): raise CompileError(f'M3008: argument {idx} expects {pt}, got {at}')
                    root=self.root_var(arg)
                    if mode in ('borrow','borrow_mut'):
                        if not root: raise CompileError(f'M5004: {mode} argument must be addressable')
                        if mode=='borrow_mut' and not env[root].mutable: raise CompileError(f'M5005: borrow_mut argument {root} is not mutable')
                        for pr,pm in loans:
                            if pr==root and ('borrow_mut' in (mode,pm)): raise CompileError(f'M5003: conflicting loans of {root}')
                        loans.append((root,mode))
                    if mode=='value' and root and at in OWNED_BUILTINS: env[root].moved=True
                return ret
            if name not in self.fn:raise CompileError(f'M3004: unknown function {name}')
            callee=self.fn[name];missing=set(callee['requires_caps'])-caps
            self.call_edges.append({'caller':fn['name'],'callee':name,'required':callee['requires_caps']})
            if missing:raise CompileError(f"M2003: call to {name} requires capabilities {sorted(missing)}")
            if len(args)!=len(callee['params']):raise CompileError(f"M3005: {name} expects {len(callee['params'])} arguments")
            loans=[]
            for arg,(pn,pt,mode) in zip(args,callee['params']):
                at=self.expr_type(arg,env,caps,fn)
                if at not in (pt,'number'):raise CompileError(f'M3008: argument {pn} expects {pt}, got {at}')
                root=self.root_var(arg)
                if root and mode in ('borrow','borrow_mut'):
                    for previous_root,previous_mode,previous_param in loans:
                        if root==previous_root and ('borrow_mut' in (mode,previous_mode)):
                            raise CompileError(f'M5003: conflicting loans of {root} for {previous_param} and {pn}')
                    loans.append((root,mode,pn))
                if mode=='borrow_mut':
                    if not root: raise CompileError(f'M5004: borrow_mut argument {pn} must be an addressable binding')
                    if not env[root].mutable: raise CompileError(f'M5005: borrow_mut argument {root} is not mutable')
                if mode=='value' and root and (at in self.p.structs or at in OWNED_BUILTINS):env[root].moved=True
            return callee['return']
        if tag=='binop':
            a=self.expr_type(e[2],env,caps,fn);b=self.expr_type(e[3],env,caps,fn)
            if e[1] in ('==','!=','>=','<=','>','<'):return 'i32'
            if a=='number':return b
            if b=='number':return a
            if a!=b:raise CompileError(f'M3102: arithmetic operands differ: {a} and {b}')
            return a
        raise CompileError(f'M3999: unsupported expression {e}')
    def root_var(self,e):
        while e and e[0]=='field': e=e[1]
        return e[1] if e and e[0]=='var' else None
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

class LayoutEngine:
    SIZES={'i8':(1,1),'u8':(1,1),'i16':(2,2),'u16':(2,2),'i32':(4,4),'u32':(4,4),'i64':(8,8),'u64':(8,8)}
    def __init__(self,p):self.p=p
    def size_align(self,t):
        if t in self.SIZES:return self.SIZES[t]
        if t in self.p.decimals:return (8,8) if self.p.decimals[t].precision<=18 else (16,16)
        if t in self.p.bounded:return self.size_align(self.p.bounded[t].base)
        if t in self.p.structs:
            x=self.layout(self.p.structs[t]);return x['size'],x['alignment']
        raise CompileError(f'layout unavailable for {t}')
    def layout(self,s):
        off=0;align=1;fields=[]
        for f in s.fields:
            sz,al=self.size_align(f.type_name);off=(off+al-1)//al*al
            fields.append({'name':f.name,'type':f.type_name,'offset':off,'size':sz,'alignment':al});off+=sz;align=max(align,al)
        size=(off+align-1)//align*align
        canonical=json.dumps({'abi':s.stable_abi,'name':s.name,'fields':fields,'size':size,'alignment':align},sort_keys=True,separators=(',',':'))
        return {'name':s.name,'abi':s.stable_abi,'size':size,'alignment':align,'fields':fields,'layout_hash':hashlib.sha256(canonical.encode()).hexdigest()[:24]}
    def all(self):return [self.layout(s) for s in self.p.structs.values()]

@dataclasses.dataclass
class ReturnSignal:
    value:TypedValue

@dataclasses.dataclass
class TrySignal:
    value:TypedValue

class Interpreter:
    def __init__(self,p):self.p=p;self.fn={f['name']:f for f in p.functions}
    def run(self):return self.call('main',[])
    def call(self,n,args):
        f=self.fn[n];env={pn:v for (pn,_,_),v in zip(f['params'],args)}
        for c in f['pre']:
            if not self.eval(c,env).value:raise RuntimeError(f'precondition failed in {n}')
        before={k:self.clone(v) for k,v in env.items()}
        sig=self.block(f['body'],env); r=sig.value if isinstance(sig,(ReturnSignal,TrySignal)) else TypedValue('void',None)
        post_env=dict(env); post_env['result']=r; post_env['__old__']=before
        for c in f['post']:
            if not self.eval(c,post_env).value:raise RuntimeError(f'postcondition failed in {n}')
        return r
    def block(self,b,env):
        for st in b:
            if st[0]=='let':env[st[1]]=self.eval(st[3],env,st[2])
            elif st[0]=='try_let':
                value=self.eval(st[3],env); enum=self.p.enums[value.type_name]
                if value.value['variant']=='Err': return TrySignal(value)
                env[st[1]]=value.value['payload']
            elif st[0]=='assign':self.assign(st[1],self.eval(st[2],env),env)
            elif st[0]=='print':print(self.format(self.eval(st[1],env)))
            elif st[0]=='return':return ReturnSignal(self.eval(st[1],env))
            elif st[0]=='expr':self.eval(st[1],env)
            elif st[0]=='drop': env.pop(st[1],None)
            elif st[0]=='match':
                value=self.eval(st[1],env); variant=value.value['variant']
                arm=next(a for a in st[2] if a[0]==variant)
                if arm[1] is not None: env[arm[1]]=value.value['payload']
                r=self.block(arm[2],env)
                if isinstance(r,(ReturnSignal,TrySignal)):return r
            elif st[0]=='with_cap':
                r=self.block(st[2],env)
                if isinstance(r,(ReturnSignal,TrySignal)):return r
            elif st[0]=='if':
                branch=st[2] if self.eval(st[1],env).value else st[3]
                r=self.block(branch,env)
                if isinstance(r,(ReturnSignal,TrySignal)):return r
            elif st[0]=='while':
                guard=0
                while self.eval(st[1],env).value:
                    r=self.block(st[2],env)
                    if isinstance(r,(ReturnSignal,TrySignal)):return r
                    guard+=1
                    if guard>1000000:raise RuntimeError('loop iteration limit exceeded')
        return None
    def assign(self,e,v,env):
        if e[0]=='var':env[e[1]]=v;return
        if e[0]=='field':env[e[1][1]].value[e[2]]=v;return
    def clone(self,v):
        if isinstance(v,TypedValue):
            if isinstance(v.value,dict): return TypedValue(v.type_name,{k:self.clone(x) for k,x in v.value.items()})
            return TypedValue(v.type_name,v.value)
        return v
    def eval(self,e,env,expected=None):
        if e[0]=='string':return TypedValue('String',e[1])
        if e[0]=='number':return self.literal(expected or 'i64',e[1])
        if e[0]=='var':return env[e[1]]
        if e[0]=='field':return self.eval(e[1],env).value[e[2]]
        if e[0]=='struct_init':
            s=self.p.structs[e[1]];return TypedValue(e[1],{f.name:self.eval(e[2][f.name],env,f.type_name) for f in s.fields})
        if e[0]=='call':
            n=e[1]
            variants=[(enum,variant) for enum in self.p.enums.values() for variant in enum.variants if variant.name==n]
            if variants:
                enum,variant=variants[0]
                payload=self.eval(e[2][0],env,variant.payload_type) if variant.payload_type is not None else None
                return TypedValue(enum.name,{'variant':variant.name,'payload':payload})
            if n=='old':
                old_env=env.get('__old__')
                if old_env is None: raise RuntimeError('old() is only valid in postconditions')
                return self.eval(e[2][0],old_env)
            if n=='system_allocator': return TypedValue('Allocator','system')
            if n=='string_len': return TypedValue('i64',len(self.eval(e[2][0],env).value.encode('utf-8')))
            if n=='string_byte':
                text=self.eval(e[2][0],env).value.encode('utf-8'); idx=self.eval(e[2][1],env).value
                if idx<0 or idx>=len(text): raise RuntimeError('string index out of bounds')
                return TypedValue('u8',text[idx])
            if n=='buffer_new': return TypedValue('Buffer',bytearray())
            if n=='buffer_from_string': return TypedValue('Buffer',bytearray(self.eval(e[2][1],env).value.encode('utf-8')))
            if n=='buffer_push':
                buf=self.eval(e[2][0],env); buf.value.append(self.eval(e[2][1],env).value); return TypedValue('void',None)
            if n=='buffer_len': return TypedValue('i64',len(self.eval(e[2][0],env).value))
            if n=='buffer_get':
                buf=self.eval(e[2][0],env).value; idx=self.eval(e[2][1],env).value
                if idx<0 or idx>=len(buf): raise RuntimeError('buffer index out of bounds')
                return TypedValue('i64',buf[idx])
            if n=='buffer_slice':
                buf=self.eval(e[2][0],env).value; start=self.eval(e[2][1],env).value; length=self.eval(e[2][2],env).value
                if start<0 or length<0 or start+length>len(buf): raise RuntimeError('slice out of bounds')
                return TypedValue('ByteSlice',memoryview(buf)[start:start+length])
            if n=='slice_len': return TypedValue('i64',len(self.eval(e[2][0],env).value))
            if n=='slice_get':
                view=self.eval(e[2][0],env).value; idx=self.eval(e[2][1],env).value
                if idx<0 or idx>=len(view): raise RuntimeError('slice index out of bounds')
                return TypedValue('i64',int(view[idx]))
            if n=='i64vec_new': return TypedValue('I64Vec',[])
            if n=='i64vec_push':
                vec=self.eval(e[2][0],env); vec.value.append(self.eval(e[2][1],env).value); return TypedValue('void',None)
            if n=='i64vec_len': return TypedValue('i64',len(self.eval(e[2][0],env).value))
            if n=='i64vec_get':
                vec=self.eval(e[2][0],env).value; idx=self.eval(e[2][1],env).value
                if idx<0 or idx>=len(vec): raise RuntimeError('vector index out of bounds')
                return TypedValue('i64',vec[idx])
            if n=='file_read':
                path=self.eval(e[2][1],env).value
                return TypedValue('Buffer',bytearray(Path(path).read_bytes()))
            if n.startswith('checked_') or n=='decimal_div':
                first=self.eval(e[2][0],env)
                second=self.eval(e[2][1],env,first.type_name)
                return self.arith('div' if n=='decimal_div' else n[8:],first,second)
            callee=self.fn[n]
            vals=[self.eval(x,env,t) for x,(_,t,_) in zip(e[2],callee['params'])]
            return self.call(n,vals)
        if e[0]=='binop':
            a=self.eval(e[2],env);b=self.eval(e[3],env,a.type_name)
            if e[1] in ('==','!=','>=','<=','>','<'):
                return TypedValue('i32',int({'==':a.value==b.value,'!=':a.value!=b.value,'>=':a.value>=b.value,'<=':a.value<=b.value,'>':a.value>b.value,'<':a.value<b.value}[e[1]]))
            return self.arith({'+':'add','-':'sub','*':'mul','/':'div'}[e[1]],a,b)
    def literal(self,t,x):
        if t in self.p.decimals:return TypedValue(t,int(Decimal(x)*(10**self.p.decimals[t].scale)))
        return TypedValue(t,int(Decimal(x)))
    def arith(self,op,a,b):
        if op=='add':v=a.value+b.value
        elif op=='sub':v=a.value-b.value
        elif op=='mul':v=(a.value*b.value)//(10**self.p.decimals[a.type_name].scale) if a.type_name in self.p.decimals else a.value*b.value
        elif op=='div':
            if b.value==0:raise RuntimeError('division by zero')
            if a.type_name in self.p.decimals:
                d=self.p.decimals[a.type_name];q=(Decimal(a.value)*(10**d.scale)/Decimal(b.value)).quantize(Decimal(1),rounding=ROUNDING[d.rounding]);v=int(q)
            else:v=a.value//b.value
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
    def __init__(self,p):self.p=p;self.fn={f['name']:f for f in p.functions};self.old_map={};self.current_return=None;self.temp_counter=0
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
        return {'i8':'int8_t','i16':'int16_t','i32':'int32_t','i64':'int64_t','u8':'uint8_t','u16':'uint16_t','u32':'uint32_t','u64':'uint64_t','void':'void'}[t]
    def header(self):
        o=['#pragma once','#include <stdint.h>','#include <stddef.h>','', 'typedef struct { const char *data; size_t len; } merit_String;', 'typedef struct { uint8_t *data; size_t len; size_t cap; } merit_Buffer;', 'typedef struct { int kind; } merit_Allocator;', 'typedef struct { const uint8_t *data; size_t len; } merit_ByteSlice;', 'typedef struct { int64_t *data; size_t len; size_t cap; } merit_I64Vec;', '']
        le=LayoutEngine(self.p)
        for enum in self.p.enums.values():
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
            for variant in enum.variants:
                params='void' if variant.payload_type is None else f'{self.ctype(variant.payload_type)} value'
                init=f'(merit_{enum.name}){{.tag=merit_{enum.name}_{variant.name}'
                if variant.payload_type is not None:init+=f',.data.{variant.name}=value'
                init+='}'
                o.append(f'static inline merit_{enum.name} merit_make_{enum.name}_{variant.name}({params}){{return {init};}}')
            o.append('')
        for s in self.p.structs.values():
            o.append(f'typedef struct merit_{s.name} {{')
            for f in s.fields:o.append(f'    {self.ctype(f.type_name)} {f.name};')
            o.append(f'}} merit_{s.name};')
            if s.stable_abi:
                layout=le.layout(s);o.append(f'_Static_assert(sizeof(merit_{s.name}) == {layout["size"]}, "Merit ABI size mismatch: {s.name}");')
                for fld in layout['fields']:o.append(f'_Static_assert(__builtin_offsetof(merit_{s.name}, {fld["name"]}) == {fld["offset"]}, "Merit ABI offset mismatch: {s.name}.{fld["name"]}");')
            o.append('')
        for f in self.p.functions:
            if f['name']=='main':continue
            params=', '.join(f'{self.ctype(t)}{" *" if m in ("borrow","borrow_mut") else " "}{n}' for n,t,m in f['params']) or 'void'
            o.append(f'{self.ctype(f["return"])} merit_{f["name"]}({params});')
        return '\n'.join(o)
    def generate(self):
        o=['#include <stdint.h>','#include <stddef.h>','#include <stdio.h>','#include <stdlib.h>','#include <string.h>','']
        o.append(self.header().replace('#pragma once','').replace('#include <stdint.h>',''))
        o += [r'''static void merit_fail(const char *m,int c){fputs(m,stderr);fputc('\n',stderr);exit(c);}''',
              r'''static merit_Allocator merit_system_allocator(void){return (merit_Allocator){0};}''',
              r'''static void merit_buffer_reserve(merit_Buffer *b,size_t need){if(need<=b->cap)return;size_t c=b->cap?b->cap:8;while(c<need)c*=2;void *p=realloc(b->data,c);if(!p)merit_fail("allocation failed",80);b->data=(uint8_t*)p;b->cap=c;}''',
              r'''static merit_Buffer merit_buffer_new(merit_Allocator a,int64_t cap){(void)a;merit_Buffer b={0};if(cap<0)merit_fail("negative capacity",81);merit_buffer_reserve(&b,(size_t)cap);return b;}''',
              r'''static merit_Buffer merit_buffer_from_string(merit_Allocator a,merit_String s){merit_Buffer b=merit_buffer_new(a,(int64_t)s.len);if(s.len){memcpy(b.data,s.data,s.len);b.len=s.len;}return b;}''',
              r'''static void merit_buffer_push(merit_Buffer *b,uint8_t v){merit_buffer_reserve(b,b->len+1);b->data[b->len++]=v;}''',
              r'''static int64_t merit_buffer_len(const merit_Buffer *b){return (int64_t)b->len;}''',
              r'''static int64_t merit_buffer_get(const merit_Buffer *b,int64_t i){if(i<0||(size_t)i>=b->len)merit_fail("buffer index out of bounds",82);return (int64_t)b->data[i];}''',
              r'''static merit_ByteSlice merit_buffer_slice(const merit_Buffer *b,int64_t start,int64_t len){if(start<0||len<0||(size_t)start>b->len||(size_t)len>b->len-(size_t)start)merit_fail("slice out of bounds",85);return (merit_ByteSlice){b->data+(size_t)start,(size_t)len};}''',
              r'''static int64_t merit_slice_len(merit_ByteSlice s){return (int64_t)s.len;}''',
              r'''static int64_t merit_slice_get(merit_ByteSlice s,int64_t i){if(i<0||(size_t)i>=s.len)merit_fail("slice index out of bounds",85);return (int64_t)s.data[i];}''',
              r'''static void merit_i64vec_reserve(merit_I64Vec *v,size_t need){if(need<=v->cap)return;size_t c=v->cap?v->cap:8;while(c<need)c*=2;void *p=realloc(v->data,c*sizeof(int64_t));if(!p)merit_fail("allocation failed",80);v->data=(int64_t*)p;v->cap=c;}''',
              r'''static merit_I64Vec merit_i64vec_new(merit_Allocator a,int64_t cap){(void)a;merit_I64Vec v={0};if(cap<0)merit_fail("negative capacity",81);merit_i64vec_reserve(&v,(size_t)cap);return v;}''',
              r'''static void merit_i64vec_push(merit_I64Vec *v,int64_t x){merit_i64vec_reserve(v,v->len+1);v->data[v->len++]=x;}''',
              r'''static int64_t merit_i64vec_len(const merit_I64Vec *v){return (int64_t)v->len;}''',
              r'''static int64_t merit_i64vec_get(const merit_I64Vec *v,int64_t i){if(i<0||(size_t)i>=v->len)merit_fail("vector index out of bounds",86);return v->data[i];}''',
              r'''static void merit_i64vec_drop(merit_I64Vec *v){free(v->data);v->data=NULL;v->len=0;v->cap=0;}''',
              r'''static void merit_buffer_drop(merit_Buffer *b){free(b->data);b->data=NULL;b->len=0;b->cap=0;}''',
              r'''static merit_Buffer merit_file_read(merit_Allocator a,merit_String path){char *z=(char*)malloc(path.len+1);if(!z)merit_fail("allocation failed",80);memcpy(z,path.data,path.len);z[path.len]=0;FILE *f=fopen(z,"rb");free(z);if(!f)merit_fail("file read failed",83);if(fseek(f,0,SEEK_END)!=0)merit_fail("file seek failed",84);long n=ftell(f);rewind(f);merit_Buffer b=merit_buffer_new(a,n);if(n>0){size_t got=fread(b.data,1,(size_t)n,f);if(got!=(size_t)n)merit_fail("file read incomplete",84);b.len=got;}fclose(f);return b;}''',
              r'''static int64_t merit_add(int64_t a,int64_t b){int64_t r;if(__builtin_add_overflow(a,b,&r))merit_fail("Merit addition overflow",70);return r;}''',
              r'''static int64_t merit_sub(int64_t a,int64_t b){int64_t r;if(__builtin_sub_overflow(a,b,&r))merit_fail("Merit subtraction overflow",70);return r;}''',
              r'''static int64_t merit_round_div(__int128 n,__int128 d,int mode){if(d==0)merit_fail("Merit division by zero",72);int neg=(n<0)^(d<0);if(n<0)n=-n;if(d<0)d=-d;__int128 q=n/d,r=n%d;int up=0;if(mode==0){__int128 twice=r*2;up=twice>d || (twice==d && (q&1));}else if(mode==1)up=r*2>=d;else if(mode==3)up=!neg&&r;else if(mode==4)up=neg&&r;q+=up;__int128 z=neg?-q:q;if(z>INT64_MAX||z<INT64_MIN)merit_fail("Merit decimal overflow",70);return (int64_t)z;}''','']
        for t,b in self.p.bounded.items():
            o.append(f'static {self.ctype(t)} merit_check_{t}({self.ctype(t)} x){{if(x < {b.minimum} || x > {b.maximum}) merit_fail("bounded range violation: {t}",70);return x;}}')
        for t,d in self.p.decimals.items():
            m=10**d.precision-1;o.append(f'static int64_t merit_check_{t}(int64_t x){{if(x < -{m}LL || x > {m}LL) merit_fail("decimal range violation: {t}",70);return x;}}')
        for f in self.p.functions:o.append(self.fn_c(f))
        return '\n'.join(o)
    def walk_old(self,e,out):
        if not isinstance(e,tuple):return
        if e[0]=='call' and e[1]=='old':
            key=repr(e[2][0]);out.setdefault(key,e[2][0]);return
        for x in e[1:]:
            if isinstance(x,tuple):self.walk_old(x,out)
            elif isinstance(x,list):
                for y in x:self.walk_old(y,out)
    def walk_statements(self, body):
        for st in body:
            yield st
            if st[0] in ('with_cap','while'):
                yield from self.walk_statements(st[-1])
            elif st[0]=='if':
                yield from self.walk_statements(st[2]); yield from self.walk_statements(st[3])
            elif st[0]=='match':
                for arm in st[2]: yield from self.walk_statements(arm[2])
    def owned_buffer_cleanup(self, f):
        locals_order=[]; explicit=set(); returned=set()
        for st in self.walk_statements(f['body']):
            if st[0]=='let' and st[2] in OWNED_BUILTINS: locals_order.append((st[1],st[2]))
            elif st[0]=='drop': explicit.add(st[1])
            elif st[0]=='return' and st[1][0]=='var': returned.add(st[1][1])
        return [(n,t) for n,t in reversed(locals_order) if n not in explicit and n not in returned]
    def fn_c(self,f):
        name='main' if f['name']=='main' else 'merit_'+f['name'];params=', '.join(f'{self.ctype(t)}{" *" if m in ("borrow","borrow_mut") else " "}{n}' for n,t,m in f['params']) or 'void';env={n:(t,m) for n,t,m in f['params']};o=[f'{self.ctype(f["return"])} {name}({params}) {{']
        old={}
        for c in f['post']:self.walk_old(c,old)
        self.old_map={}
        for idx,(key,e) in enumerate(old.items()):
            t=self.etype(e,env);v=f'_merit_old_{idx}';self.old_map[key]=v;o.append(f'    {self.ctype(t)} {v} = {self.expr(e,env)};')
        for c in f['pre']:o.append(f'    if(!({self.expr(c,env)})) merit_fail("precondition failed in {f["name"]}",71);')
        self.current_return=f['return']
        if f['return']!='void':o.append(f'    {self.ctype(f["return"])} _merit_result = {{0}};' if f['return'] in self.p.enums or f['return'] in self.p.structs or f['return'] in BUILTIN_TYPES else f'    {self.ctype(f["return"])} _merit_result = 0;')
        for st in f['body']:o+=self.stmt(st,env,1)
        o.append('    _merit_epilogue: ;')
        postenv=dict(env);postenv['result']=(f['return'],'__result__')
        for c in f['post']:o.append(f'    if(!({self.expr(c,postenv)})) merit_fail("postcondition failed in {f["name"]}",73);')
        for name,t in self.owned_buffer_cleanup(f): o.append(f'    merit_buffer_drop(&{name});' if t=='Buffer' else f'    merit_i64vec_drop(&{name});')
        if f['return']!='void':o.append('    return _merit_result;')
        o.append('}');return '\n'.join(o)
    def checked(self,t,x):
        if t in self.p.bounded or t in self.p.decimals:return f'merit_check_{t}({x})'
        return x
    def stmt(self,s,env,i):
        p='    '*i
        if s[0]=='let':env[s[1]]=s[2];return [f'{p}{self.ctype(s[2])} {s[1]} = {self.checked(s[2],self.expr(s[3],env,s[2]))};']
        if s[0]=='try_let':
            enum_t=self.etype(s[3],env); enum=self.p.enums[enum_t]; temp=f'_merit_try_{self.temp_counter}'; self.temp_counter+=1
            err=next(v for v in enum.variants if v.name=='Err'); ret=self.p.enums[self.current_return]
            env[s[1]]=s[2]
            return [f'{p}{self.ctype(enum_t)} {temp} = {self.expr(s[3],env)};', f'{p}if ({temp}.tag == merit_{enum_t}_Err) {{', f'{p}    _merit_result = merit_make_{self.current_return}_Err({temp}.data.Err);', f'{p}    goto _merit_epilogue;', f'{p}}}', f'{p}{self.ctype(s[2])} {s[1]} = {temp}.data.Ok;']
        if s[0]=='assign':
            t=self.etype(s[1],env);return [f'{p}{self.expr(s[1],env)} = {self.checked(t,self.expr(s[2],env,t))};']
        if s[0]=='return':return [f'{p}_merit_result = {self.checked(self.current_return,self.expr(s[1],env,self.current_return))};',f'{p}goto _merit_epilogue;']
        if s[0]=='print':
            t=self.etype(s[1],env);x=self.expr(s[1],env)
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
        if s[0]=='expr':return [f'{p}(void)({self.expr(s[1],env)});']
        if s[0]=='drop':
            t=self.env_type(env,s[1]); return [f'{p}merit_buffer_drop(&{s[1]});'] if t=='Buffer' else ([f'{p}merit_i64vec_drop(&{s[1]});'] if t=='I64Vec' else [f'{p}/* deterministic drop {s[1]} */'])
        if s[0]=='match':
            enum_t=self.etype(s[1],env); temp=f'_merit_match_{self.temp_counter}';self.temp_counter+=1
            o=[f'{p}{self.ctype(enum_t)} {temp} = {self.expr(s[1],env)};',f'{p}switch ({temp}.tag) {{']
            enum=self.p.enums[enum_t]
            for arm in s[2]:
                variant=next(v for v in enum.variants if v.name==arm[0]);o.append(f'{p}case merit_{enum_t}_{variant.name}: {{')
                local=dict(env)
                if arm[1] is not None:
                    local[arm[1]]=variant.payload_type;o.append(f'{p}    {self.ctype(variant.payload_type)} {arm[1]} = {temp}.data.{variant.name};')
                for z in arm[2]:o+=self.stmt(z,local,i+1)
                o.append(f'{p}    break;');o.append(f'{p}}}')
            o.append(f'{p}}}');return o
        if s[0]=='with_cap':
            o=[f'{p}/* capability: {s[1]} */']
            for z in s[2]:o+=self.stmt(z,env,i)
            return o
        if s[0]=='if':
            o=[f'{p}if ({self.expr(s[1],env)}) {{']
            for z in s[2]:o+=self.stmt(z,env,i+1)
            o.append(f'{p}}} else {{')
            for z in s[3]:o+=self.stmt(z,env,i+1)
            o.append(f'{p}}}');return o
        if s[0]=='while':
            o=[f'{p}while ({self.expr(s[1],env)}) {{']
            for z in s[2]:o+=self.stmt(z,env,i+1)
            o.append(f'{p}}}');return o
        return []
    def env_type(self,env,n):
        v=env[n]; return v[0] if isinstance(v,tuple) else v
    def env_mode(self,env,n):
        v=env[n]; return v[1] if isinstance(v,tuple) else 'value'
    def etype(self,e,env):
        if e[0]=='string':return 'String'
        if e[0]=='number':return 'i64'
        if e[0]=='var':return self.env_type(env,e[1])
        if e[0]=='field':
            t=self.etype(e[1],env);return next(f.type_name for f in self.p.structs[t].fields if f.name==e[2])
        if e[0]=='struct_init':return e[1]
        if e[0]=='call':
            variants=[enum.name for enum in self.p.enums.values() for variant in enum.variants if variant.name==e[1]]
            if variants:return variants[0]
            if e[1]=='old':return self.etype(e[2][0],env)
            builtin_returns={'system_allocator':'Allocator','string_len':'i64','string_byte':'u8','buffer_new':'Buffer','buffer_from_string':'Buffer','buffer_push':'void','buffer_len':'i64','buffer_get':'i64','buffer_slice':'ByteSlice','slice_len':'i64','slice_get':'i64','i64vec_new':'I64Vec','i64vec_push':'void','i64vec_len':'i64','i64vec_get':'i64','file_read':'Buffer'}
            if e[1] in builtin_returns:return builtin_returns[e[1]]
            return self.etype(e[2][0],env) if e[1].startswith('checked_') or e[1]=='decimal_div' else self.fn[e[1]]['return']
        if e[0]=='binop':return 'i32' if e[1] in ('==','!=','>=','<=','>','<') else self.etype(e[2],env)
    def address_expr(self,e,env):
        rendered=self.expr(e,env)
        if e[0]=='var' and self.env_mode(env,e[1]) in ('borrow','borrow_mut'):
            return rendered
        return '&'+rendered
    def expr(self,e,env,expected=None):
        if e[0]=='string':
            raw=json.dumps(e[1]); return f'(merit_String){{{raw}, sizeof({raw})-1}}'
        if e[0]=='number':return str(int(Decimal(e[1])*(10**self.p.decimals[expected].scale))) if expected in self.p.decimals else str(int(Decimal(e[1])))
        if e[0]=='var':return '_merit_result' if e[1]=='result' and isinstance(env.get('result'),tuple) and env['result'][1]=='__result__' else e[1]
        if e[0]=='field':
            base=e[1]; op='.'
            if base[0]=='var' and self.env_mode(env,base[1]) in ('borrow','borrow_mut'): op='->'
            return f'{self.expr(base,env)}{op}{e[2]}'
        if e[0]=='struct_init':
            s=self.p.structs[e[1]];return f'({self.ctype(e[1])}){{'+', '.join(f'.{f.name}={self.expr(e[2][f.name],env,f.type_name)}' for f in s.fields)+'}'
        if e[0]=='call':
            n=e[1];a=e[2]
            variants=[(enum,variant) for enum in self.p.enums.values() for variant in enum.variants if variant.name==n]
            if variants:
                enum,variant=variants[0]
                rendered='' if variant.payload_type is None else self.expr(a[0],env,variant.payload_type)
                return f'merit_make_{enum.name}_{variant.name}({rendered})'
            if n=='old':return self.old_map[repr(a[0])]
            if n=='system_allocator': return 'merit_system_allocator()'
            if n=='string_len': return f'((int64_t){self.expr(a[0],env)}.len)'
            if n=='string_byte': return f'((uint8_t){self.expr(a[0],env)}.data[{self.expr(a[1],env)}])'
            if n=='buffer_new': return f'merit_buffer_new({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='buffer_from_string': return f'merit_buffer_from_string({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='buffer_push': return f'(merit_buffer_push({self.address_expr(a[0],env)}, {self.expr(a[1],env)}), 0)'
            if n=='buffer_len': return f'merit_buffer_len({self.address_expr(a[0],env)})'
            if n=='buffer_get': return f'merit_buffer_get({self.address_expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='buffer_slice': return f'merit_buffer_slice({self.address_expr(a[0],env)}, {self.expr(a[1],env)}, {self.expr(a[2],env)})'
            if n=='slice_len': return f'merit_slice_len({self.expr(a[0],env)})'
            if n=='slice_get': return f'merit_slice_get({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='i64vec_new': return f'merit_i64vec_new({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='i64vec_push': return f'(merit_i64vec_push({self.address_expr(a[0],env)}, {self.expr(a[1],env)}), 0)'
            if n=='i64vec_len': return f'merit_i64vec_len({self.address_expr(a[0],env)})'
            if n=='i64vec_get': return f'merit_i64vec_get({self.address_expr(a[0],env)}, {self.expr(a[1],env)})'
            if n=='file_read': return f'merit_file_read({self.expr(a[0],env)}, {self.expr(a[1],env)})'
            if n in ('checked_add','checked_sub','checked_mul','decimal_div'):
                t=self.etype(a[0],env);left=self.expr(a[0],env,t);right=self.expr(a[1],env,t)
                if n=='checked_add':return f'merit_add({left}, {right})'
                if n=='checked_sub':return f'merit_sub({left}, {right})'
                if t in self.p.decimals:
                    d=self.p.decimals[t];scale=10**d.scale;mode={'half_even':0,'half_up':1,'down':2,'ceiling':3,'floor':4}[d.rounding]
                    return f'merit_round_div((__int128)({left}) * ({right}), {scale}, {mode})' if n=='checked_mul' else f'merit_round_div((__int128)({left}) * {scale}, ({right}), {mode})'
                return f'({left} * {right})' if n=='checked_mul' else f'({left} / {right})'
            callee=self.fn[n];rendered=[]
            for x,(_,t,m) in zip(a,callee['params']):
                ex=self.expr(x,env,t);rendered.append(('&'+ex) if m in ('borrow','borrow_mut') else ex)
            return f'merit_{n}('+', '.join(rendered)+')'
        if e[0]=='binop':
            t=expected or self.etype(e[2],env)
            return f'({self.expr(e[2],env,t)} {e[1]} {self.expr(e[3],env,t)})'

def hir(p):
    return {'module':p.module,'types':{'decimal':[dataclasses.asdict(x) for x in p.decimals.values()],'bounded':[dataclasses.asdict(x) for x in p.bounded.values()],'enum':[dataclasses.asdict(x) for x in p.enums.values()],'trait':[dataclasses.asdict(x) for x in p.traits.values()],'struct':[{'name':s.name,'stable_abi':s.stable_abi,'fields':[dataclasses.asdict(f) for f in s.fields]} for s in p.structs.values()]},'functions':p.functions}
def mir(p):
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
                if st[0]=='if':
                    then_b=new_block(); else_b=new_block(); join_b=new_block()
                    current['terminator']={'kind':'branch','condition':st[1],'then':then_b['id'],'else':else_b['id']}
                    end_then=lower_seq(st[2],then_b); end_else=lower_seq(st[3],else_b)
                    if end_then['terminator']['kind']=='fallthrough': end_then['terminator']={'kind':'goto','target':join_b['id']}
                    if end_else['terminator']['kind']=='fallthrough': end_else['terminator']={'kind':'goto','target':join_b['id']}
                    current=join_b
                elif st[0]=='while':
                    cond_b=new_block(); body_b=new_block(); exit_b=new_block()
                    current['terminator']={'kind':'goto','target':cond_b['id']}
                    cond_b['terminator']={'kind':'branch','condition':st[1],'then':body_b['id'],'else':exit_b['id']}
                    end_body=lower_seq(st[2],body_b)
                    if end_body['terminator']['kind']=='fallthrough': end_body['terminator']={'kind':'goto','target':cond_b['id']}
                    current=exit_b
                elif st[0]=='match':
                    arm_blocks=[]; join_b=new_block()
                    for arm in st[2]:
                        b=new_block(); arm_blocks.append({'variant':arm[0],'binding':arm[1],'target':b['id']})
                        end_arm=lower_seq(arm[2],b)
                        if end_arm['terminator']['kind']=='fallthrough': end_arm['terminator']={'kind':'goto','target':join_b['id']}
                    current['terminator']={'kind':'switch','subject':st[1],'arms':arm_blocks}
                    current=join_b
                elif st[0]=='return':
                    current['terminator']={'kind':'return','value':st[1]}; current=new_block()
                else:
                    current['statements'].append(st)
            return current
        tail=lower_seq(f['body'],entry)
        if tail['terminator']['kind']=='fallthrough': tail['terminator']={'kind':'return','value':None}
        locals_order=[st[1] for st in CGenerator(p).walk_statements(f['body']) if st[0]=='let' and (st[2] in p.structs or st[2] in OWNED_BUILTINS)]
        explicit={st[1] for st in CGenerator(p).walk_statements(f['body']) if st[0]=='drop'}
        entry['statements'].extend(('drop_implicit',name) for name in reversed(locals_order) if name not in explicit)
        return {'name':f['name'],'params':f['params'],'return':f['return'],'owned_locals':locals_order,'blocks':blocks}
    return {'module':p.module,'functions':[lower_function(f) for f in p.functions]}


def compile_file(path,out=None):
    p=parse(path.read_text());ch=Checker(p).check();cg=CGenerator(p);exe=out or path.with_suffix('');cpath=exe.with_suffix('.c');hpath=exe.with_suffix('.h');cpath.write_text(cg.generate());hpath.write_text(cg.header());subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2','-Wall','-Wextra',str(cpath),'-o',str(exe)],check=True);return ch,cpath,hpath,exe

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
        p=parse(path.read_text());ch=Checker(p).check()
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
        elif ns.cmd=='audit':print(json.dumps({'declared_capabilities':sorted(p.capabilities),'sites':ch.audit_sites,'calls':ch.call_edges},indent=2))
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
    except Exception as e:print(f'error: {e}',file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
