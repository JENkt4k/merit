from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest
from lark.exceptions import UnexpectedInput

from merit.bootstrap.native_frontend_driver import build_native_replacement_driver
from merit.bootstrap.resolved_source_function_bundle import decode_resolved_source_function_bundle
from merit.bootstrap.resolved_source_function_snapshot import materialize_resolved_source_function_snapshot
from merit.compiler import Checker, CompileError, parse
from merit.project.build import build
from merit.project.loader import ProjectError, load_project
from merit.project.replacement import ReplacementProjectError, build_replacement_project
from merit.project.replacement_prepare import NativeReplacementDriver, prepare_replacement_artifacts


SOURCE = "module main\nfn main()->i32 { return 7; }\n"
MULTI_FUNCTION_SOURCE = (
    "module main\n"
    "fn helper()->i32 { return 6; }\n"
    "fn main()->i32 { return 7; }\n"
)
GENERIC_FUNCTION_SOURCE = (
    "module main\n"
    "fn identity<T: Copy>(value:T)->T { return value; }\n"
    "fn main()->i32 { let value:i64=identity<i64>(7); print(value); return 0; }\n"
)
GENERIC_AGGREGATE_SOURCE = """module main
struct Pair<T,U> { first:T; second:U; }
enum Option<T> { Some(T), None }
fn main()->i32 {
    let pair:Pair<i64,i32>=Pair<i64,i32>{first:7,second:3};
    let maybe:Option<i64>=Option<i64>::Some(pair.first);
    match(maybe){Option<i64>::Some(value)=>{print(value);} Option<i64>::None=>{print(0);}}
    return 0;
}
"""
GENERIC_TRAIT_DISPATCH_SOURCE = """module main
struct Point { x:i32; }
trait Summarized { fn score(value:Self)->i32; }
impl Summarized for Point { fn score(value:Point)->i32 { return value.x; } }
fn summarize<T:Summarized>(value:T)->i32 { return score(value); }
fn main()->i32 {
    let point:Point=Point{x:17};
    let total:i32=summarize<Point>(point);
    print(total);return 0;
}
"""
GENERIC_VEC_I64_SOURCE = """module main
capability allocate;
fn main()->i32 { with capability allocate {
    let allocator:Allocator=system_allocator();
    var values:Vec<i64>=vec_new<i64>(allocator,2);
    vec_push<i64>(values,7);vec_push<i64>(values,11);
    vec_set<i64>(values,1,13);
    print(vec_len<i64>(values));print(vec_get<i64>(values,0));print(vec_pop<i64>(values));
} return 0; }
"""
GENERIC_OWNERSHIP_SOURCE = """module main
capability allocate;
fn forward<T>(value:T)->T { return value; }
fn observe<T>(borrow value:T)->i32 { return 1; }
fn main()->i32 { with capability allocate {
    let allocator:Allocator=system_allocator();
    let source:Buffer=buffer_from_string(allocator,"owned");
    let moved:Buffer=forward<Buffer>(source);
    print(observe<Buffer>(moved));print(buffer_len(moved));drop(moved);
} return 0; }
"""
GENERIC_VEC_OWNED_SOURCE = """module main
capability allocate;
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn main()->i32 { with capability allocate {
    let portable:Allocator=portable_allocator();let system:Allocator=system_allocator();
    var values:Vec<Marker>=vec_new<Marker>(portable,1);
    let first:Marker=Marker{number:41};let second:Marker=Marker{number:43};
    vec_push<Marker>(values,first);vec_replace<Marker>(values,0,second);
    print(allocator_compatible(vec_allocator<Marker>(values),portable));
    var destination:Vec<Marker>=vec_new<Marker>(portable,0);
    vec_transfer<Marker>(destination,values);
    let restored:Marker=vec_pop<Marker>(destination);print(restored.number);drop(restored);
    var inner:Vec<Marker>=vec_new<Marker>(system,1);
    let nested:Marker=Marker{number:53};vec_push<Marker>(inner,nested);
    var outer:Vec<Vec<Marker>>=vec_new<Vec<Marker>>(system,1);
    vec_push<Vec<Marker>>(outer,inner);print(vec_len<Vec<Marker>>(outer));
} return 0; }
"""
M4_REJECTED_SOURCES = (
    (
        "wrong-generic-arity",
        "module main\nstruct Pair<T,U>{first:T;second:U;}\n"
        "fn main()->i32 { let pair:Pair<i64>=Pair<i64>{first:1}; return 0; }\n",
    ),
    (
        "missing-trait-implementation",
        "module main\nstruct Point{x:i32;}\ntrait Summarized{fn score(value:Self)->i32;}\n"
        "fn summarize<T:Summarized>(value:T)->i32{return score(value);}\n"
        "fn main()->i32 { let point:Point=Point{x:1}; return summarize<Point>(point); }\n",
    ),
    (
        "duplicate-trait-implementation",
        "module main\nstruct Point{x:i32;}\ntrait Summarized{fn score(value:Self)->i32;}\n"
        "impl Summarized for Point{fn score(value:Point)->i32{return value.x;}}\n"
        "impl Summarized for Point{fn score(value:Point)->i32{return value.x;}}\n"
        "fn main()->i32{return 0;}\n",
    ),
    (
        "ambiguous-trait-method",
        "module main\nstruct Point{x:i32;}\n"
        "trait Primary{fn score(value:Self)->i32;} trait Secondary{fn score(value:Self)->i32;}\n"
        "impl Primary for Point{fn score(value:Point)->i32{return value.x;}}\n"
        "impl Secondary for Point{fn score(value:Point)->i32{return value.x;}}\n"
        "fn summarize<T:Primary+Secondary>(value:T)->i32{return score(value);}\n"
        "fn main()->i32{let point:Point=Point{x:1};return summarize<Point>(point);}\n",
    ),
    (
        "generic-use-after-move",
        "module main\ncapability allocate;\nfn forward<T>(value:T)->T{return value;}\n"
        "fn main()->i32{with capability allocate{let allocator:Allocator=system_allocator();"
        "let source:Buffer=buffer_from_string(allocator,\"x\");let moved:Buffer=forward<Buffer>(source);"
        "print(buffer_len(source));drop(moved);}return 0;}\n",
    ),
    (
        "non-copy-generic-copy-bound",
        "module main\ncapability allocate;\nfn copy_value<T:Copy>(value:T)->T{return value;}\n"
        "fn main()->i32{with capability allocate{let allocator:Allocator=system_allocator();"
        "let source:Buffer=buffer_from_string(allocator,\"x\");"
        "let copied:Buffer=copy_value<Buffer>(source);drop(copied);}return 0;}\n",
    ),
    (
        "illegal-vector-copy",
        "module main\ncapability allocate;\nfn main()->i32{with capability allocate{"
        "let allocator:Allocator=system_allocator();var values:Vec<i64>=vec_new<i64>(allocator,1);"
        "let moved:Vec<i64>=values;print(vec_len<i64>(values));drop(moved);}return 0;}\n",
    ),
    (
        "illegal-owned-vector-copy-out",
        "module main\ncapability allocate;\nfn main()->i32{with capability allocate{"
        "let allocator:Allocator=system_allocator();var values:Vec<Buffer>=vec_new<Buffer>(allocator,1);"
        "let item:Buffer=buffer_from_string(allocator,\"x\");vec_push<Buffer>(values,item);"
        "let copied:Buffer=vec_get<Buffer>(values,0);drop(copied);}return 0;}\n",
    ),
    (
        "vector-allocation-without-capability",
        "module main\nfn main()->i32{let allocator:Allocator=system_allocator();"
        "var values:Vec<i64>=vec_new<i64>(allocator,1);drop(values);return 0;}\n",
    ),
)
PRIMITIVE_INTEGER_SURFACE_SOURCE = (
    "module main\n"
    "fn main()->i32 { "
    "let i8_left:i8=120; let i8_right:i8=7; print(i8_left+i8_right); "
    "let i16_left:i16=30000; let i16_right:i16=123; print(i16_left-i16_right); "
    "let i32_left:i32=50000; let i32_right:i32=40; print(i32_left*i32_right); "
    "let i64_left:i64=7; let i64_right:i64=3; print(i64_left/i64_right); "
    "let u8_left:u8=250; let u8_right:u8=5; print(u8_left+u8_right); "
    "let u16_left:u16=60000; let u16_right:u16=1000; print(u16_left+u16_right); "
    "let u32_left:u32=4000000000; let u32_right:u32=2; print(u32_left/u32_right); "
    "let u64_left:u64=9000000000000000000; let u64_right:u64=3; print(u64_left/u64_right); "
    "return 0; }\n"
)
PRIMITIVE_INTEGER_FAILURE_SOURCES = (
    ("i8-add", "i8", "127", "+", "1", "i8 addition overflow"),
    ("u8-sub", "u8", "0", "-", "1", "u8 subtraction overflow"),
    ("i32-mul", "i32", "50000", "*", "50000", "i32 multiplication overflow"),
    ("u64-add", "u64", "18446744073709551615", "+", "1", "u64 addition overflow"),
    ("i64-div-zero", "i64", "7", "/", "0", "division by zero"),
    ("i64-div-overflow", "i64", "-9223372036854775808", "/", "-1", "division overflow"),
)
SIGNED_DIVISION_SOURCE = (
    "module main\nfn main()->i32 { "
    "let negative:i64=-7; let positive:i64=7; let divisor:i64=3; "
    "print(negative/divisor); print(positive/-3); print(negative/-3); "
    "return 0; }\n"
)
CHECKED_PRIMITIVE_BUILTIN_SOURCE = (
    "module main\nfn main()->i32 { "
    "let left:i16=300; let right:i16=7; "
    "let added:i16=checked_add(left,right); "
    "let subtracted:i16=checked_sub(left,right); "
    "let multiplied:i16=checked_mul(left,right); "
    "print(added); print(subtracted); print(multiplied); return 0; }\n"
)
PRIMITIVE_COMPARISON_SOURCE = (
    "module main\nfn main()->i32 { "
    "let signed_left:i8=-3; let signed_right:i8=2; "
    "print(signed_left<signed_right); print(signed_left<=signed_right); "
    "print(signed_left>signed_right); print(signed_left>=signed_right); "
    "print(signed_left==signed_right); print(signed_left!=signed_right); "
    "let unsigned_left:u64=18446744073709551615; let unsigned_right:u64=1; "
    "print(unsigned_left>unsigned_right); print(unsigned_left<unsigned_right); "
    "return 0; }\n"
)
NUMERIC_DESCRIPTOR_SOURCE = (
    "module main\n"
    "decimal USD(18,2,half_even);\n"
    "bounded Sequence(u64,0,9999999999999999999);\n"
    "bounded Offset(i64,-9223372036854775808,9223372036854775807);\n"
    "fn main()->i32 { return 0; }\n"
)
EXACT_NUMERIC_LITERAL_SOURCE = (
    "module main\n"
    "decimal USD(18,2,half_even);\n"
    "bounded Sequence(u64,0,9999999999999999999);\n"
    "fn main()->i32 { let amount:USD=1.25; let sequence:Sequence=9999999999999999999; "
    "print(amount); print(sequence); return 0; }\n"
)
EXACT_NUMERIC_ARITHMETIC_SOURCE = """module main
decimal HalfEven(12,2,half_even);
decimal HalfUp(12,2,half_up);
decimal Down(12,2,down);
decimal Ceiling(12,2,ceiling);
decimal Floor(12,2,floor);
bounded Window(i32,-600,600);
fn main()->i32 {
    let even_left:HalfEven=1.00; let even_right:HalfEven=8.00; print(even_left/even_right);
    let up_left:HalfUp=1.00; let up_right:HalfUp=8.00; print(up_left/up_right);
    let down_left:Down=1.00; let down_right:Down=8.00; print(down_left/down_right);
    let ceiling_left:Ceiling=1.00; let ceiling_right:Ceiling=8.00; print(ceiling_left/ceiling_right);
    let floor_left:Floor=1.00; let floor_right:Floor=8.00; print(floor_left/floor_right);
    let negative_ceiling:Ceiling=-1.00; print(negative_ceiling/ceiling_right);
    let negative_floor:Floor=-1.00; print(negative_floor/floor_right);
    let decimal_left:HalfEven=1.25; let decimal_right:HalfEven=2.00;
    print(checked_add(decimal_left,decimal_right)); print(checked_sub(decimal_left,decimal_right));
    print(checked_mul(decimal_left,decimal_right)); print(decimal_div(even_left,even_right));
    let bounded_left:Window=299; let bounded_one:Window=1; let bounded_negative:Window=-13;
    print(bounded_left+bounded_one); print(-299-bounded_one); print(12*bounded_negative);
    print(-299/2); print(bounded_left>bounded_one); print(bounded_left==bounded_one);
    return 0;
}
"""
EXACT_NUMERIC_FAILURE_SOURCES = (
    (
        "decimal-overflow",
        "decimal Small(5,2,half_even);",
        "let left:Small=999.99; let right:Small=0.01; print(left+right);",
        70,
        "decimal range violation",
    ),
    (
        "bounded-overflow",
        "bounded Window(i32,-300,300);",
        "let left:Window=300; let right:Window=1; print(left+right);",
        70,
        "bounded range violation",
    ),
    (
        "decimal-division-zero",
        "decimal Money(12,2,half_even);",
        "let left:Money=1.00; let right:Money=0.00; print(left/right);",
        72,
        "division by zero",
    ),
    (
        "bounded-division-zero",
        "bounded Window(i32,-300,300);",
        "let left:Window=1; let right:Window=0; print(left/right);",
        72,
        "division by zero",
    ),
)
EXACT_NUMERIC_AGGREGATE_SOURCE = """module main
decimal Money(18,2,half_even);
bounded Sequence(u64,1,9999999999999999999);
struct Invoice { amount:Money; sequence:Sequence; }
fn main()->i32 {
    let invoice:Invoice=Invoice { sequence:9999999999999999999, amount:12.50 };
    print(invoice.amount); print(invoice.sequence);
    let increment:Money=0.25; print(invoice.amount+increment);
    drop(invoice); return 0;
}
"""
STRING_SURFACE_SOURCE = """module main
fn main()->i32 {
    let text:String="Aé";
    print(text); print(string_len(text)); print(string_byte(text,0)); print(string_byte(text,1)); print(string_byte(text,2)); print(string_byte(text,3));
    return 0;
}
"""
BUFFER_SURFACE_SOURCE = """module main
capability allocate;
fn main()->i32 {
    with capability allocate {
        let system:Allocator=system_allocator();
        let same:Allocator=system_allocator();
        let portable:Allocator=portable_allocator();
        print(allocator_compatible(system,same));
        print(allocator_compatible(system,portable));
        var data:Buffer=buffer_from_string(portable,"abc");
        let bang:u8=33; buffer_push(data,bang);
        print(allocator_compatible(buffer_allocator(data),portable));
        print(buffer_len(data)); print(buffer_get(data,1)); print(data);
        let view:ByteSlice=buffer_slice(data,1,2);
        print(slice_len(view)); print(slice_get(view,0)); print(slice_get(view,1));
        let empty:Buffer=buffer_new(system,4); print(buffer_len(empty));
        drop(empty); drop(data);
    }
    return 0;
}
"""
TEXT_BUFFER_FAILURE_SOURCES = (
    ("negative-capacity", "capability allocate; fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_new(a,-1); drop(b); } return 0; }", 81, "negative capacity"),
    ("buffer-index", 'capability allocate; fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_from_string(a,"a"); print(buffer_get(b,1)); drop(b); } return 0; }', 82, "buffer index out of bounds"),
    ("slice-range", 'capability allocate; fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_from_string(a,"a"); let s:ByteSlice=buffer_slice(b,1,1); print(slice_len(s)); drop(b); } return 0; }', 85, "slice out of bounds"),
    ("slice-index", 'capability allocate; fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_from_string(a,"a"); let s:ByteSlice=buffer_slice(b,0,1); print(slice_get(s,1)); drop(b); } return 0; }', 85, "slice index out of bounds"),
)
BUFFER_CAPABILITY_FAILURE_SOURCES = (
    ("buffer-new", "let data:Buffer=buffer_new(allocator,1); drop(data);"),
    ("buffer-from-string", 'let data:Buffer=buffer_from_string(allocator,"x"); drop(data);'),
    ("buffer-push", "var data:Buffer=buffer_new(allocator,1); let byte:u8=1; buffer_push(data,byte); drop(data);"),
)
CAPABILITY_SOURCE = (
    "module main\n"
    "capability clock;\n"
    "fn main()->i32 { with capability clock { return 7; } }\n"
)
UNKNOWN_CAPABILITY_SOURCE = (
    "module main\n"
    "fn main()->i32 { with capability clock { return 7; } }\n"
)
ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Left, Right }\n"
    "fn main()->i32 { let flag:Choice=0; match (flag) { Left => { return 7; } Right => { } } return 8; }\n"
)
MULTI_ENUM_TYPED_SOURCE = (
    "module main\n"
    "enum OtherChoice { First, Second }\n"
    "enum Choice { Left, Right }\n"
    "fn main()->i32 { let flag:Choice=0; match (flag) { Left => { return 7; } Right => { } } return 8; }\n"
)
UNTYPED_MULTI_ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Left, Right }\n"
    "enum OtherChoice { First, Second }\n"
    "fn main()->i32 { let flag:i64=0; match (flag) { Left => { return 7; } Right => { } } return 8; }\n"
)
PAYLOAD_ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Left(i32), Right(i32) }\n"
    "fn main()->i32 { let flag:Choice=Left(7); match (flag) { Left(x) => { return x; } Right(y) => { return y; } } }\n"
)
OWNED_PAYLOAD_ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Data(Buffer) }\n"
    "fn main()->i32 { return 7; }\n"
)
OWNED_DESTRUCTOR_PAYLOAD_ENUM_SOURCES = (
    (
        "implicit-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:31 }; let value:Envelope=Full(marker); return 0; }\n",
        "31\n",
    ),
    (
        "explicit-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:37 }; let value:Envelope=Full(marker); drop(value); return 0; }\n",
        "37\n",
    ),
    (
        "move-no-double-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:41 }; let first:Envelope=Full(marker); let second:Envelope=first; drop(second); return 0; }\n",
        "41\n",
    ),
    (
        "early-return-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:43 }; let value:Envelope=Full(marker); if 1<2 { return 0; } else { return 1; } }\n",
        "43\n",
    ),
    (
        "replace",
        "fn main()->i32 { let first_marker:Marker=Marker { number:47 }; var target:Envelope=Full(first_marker); let second_marker:Marker=Marker { number:53 }; let replacement:Envelope=Full(second_marker); replace(target,replacement); drop(target); return 0; }\n",
        "47\n53\n",
    ),
    (
        "match-payload-transfer",
        "fn main()->i32 { let marker:Marker=Marker { number:59 }; let value:Envelope=Spare(marker); match (value) { Full(payload) => { drop(payload); } Spare(payload) => { drop(payload); } } return 0; }\n",
        "59\n",
    ),
)
OWNED_DESTRUCTOR_PAYLOAD_ENUM_PREFIX = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "enum Envelope { Full(Marker), Spare(Marker) }\n"
)
MIXED_OWNED_PAYLOAD_ENUM_SOURCE = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "enum Envelope { Full(Marker), Count(i64) }\n"
    "fn main()->i32 { let marker:Marker=Marker { number:61 }; let first:Envelope=Full(marker); "
    "match (first) { Full(payload) => { drop(payload); } Count(value) => { print(value); } } "
    "let second:Envelope=Count(67); match (second) { Full(payload) => { drop(payload); } "
    "Count(value) => { print(value); } } return 0; }\n"
)
MINIMAL_BUFFER_LIFECYCLE_SOURCE = (
    "module main\n"
    "capability allocate;\n"
    "fn main()->i32 { with capability allocate { "
    "let allocator:Allocator=system_allocator(); "
    "let value:Buffer=buffer_new(allocator,8); "
    "print(buffer_len(value)); drop(value); } return 0; }\n"
)
BUFFER_REPLACE_LIFECYCLE_SOURCE = (
    "module main\ncapability allocate;\n"
    "fn main()->i32 { with capability allocate { "
    "let allocator:Allocator=system_allocator(); "
    "var target:Buffer=buffer_new(allocator,4); "
    "let replacement:Buffer=buffer_new(allocator,8); "
    "replace(target,replacement); print(buffer_len(target)); drop(target); } return 0; }\n"
)
BORROWED_BUFFER_FIELD_REPLACE_SOURCE = (
    "module main\ncapability allocate;\n"
    "struct Resource { data:Buffer; }\n"
    "fn expose_mut(borrow_mut value:Resource)->borrow_mut Resource { print(1); return value; }\n"
    "fn main()->i32 { with capability allocate { "
    "let allocator:Allocator=system_allocator(); "
    "let initial:Buffer=buffer_new(allocator,4); "
    "var resource:Resource=Resource { data:initial }; "
    "let replacement:Buffer=buffer_new(allocator,8); "
    "replace(expose_mut(resource).data,replacement); "
    "print(buffer_len(resource.data)); drop(resource); } return 0; }\n"
)
BUFFER_STRUCT_LIFECYCLE_SOURCE = (
    "module main\n"
    "capability allocate;\n"
    "struct Resource { data:Buffer; }\n"
    "fn main()->i32 { with capability allocate { "
    "let allocator:Allocator=system_allocator(); "
    "let data:Buffer=buffer_new(allocator,8); "
    "let resource:Resource=Resource { data:data }; "
    "print(buffer_len(resource.data)); drop(resource); } return 0; }\n"
)
FILESYSTEM_RESULT_LIFECYCLE_SOURCES = (
    (
        "read-ok-buffer",
        "module main\ncapability allocate;\n"
        "enum ReadLifecycleResult { LifecycleReadOk(Buffer), LifecycleReadErr(i32) }\n"
        "fn main()->i32 { with capability allocate { "
        "let allocator:Allocator=system_allocator(); "
        "let data:Buffer=buffer_new(allocator,8); "
        "let result:ReadLifecycleResult=LifecycleReadOk(data); "
        "match (result) { LifecycleReadOk(payload)=>{ print(buffer_len(payload)); drop(payload); } "
        "LifecycleReadErr(error)=>{ print(error); } } } return 0; }\n",
        "0\n",
    ),
    (
        "read-error-copy-payload",
        "module main\nenum ReadLifecycleResult { LifecycleReadOk(Buffer), LifecycleReadErr(i32) }\n"
        "fn main()->i32 { let result:ReadLifecycleResult=LifecycleReadErr(17); "
        "match (result) { LifecycleReadOk(payload)=>{ drop(payload); } LifecycleReadErr(error)=>{ print(error); } } return 0; }\n",
        "17\n",
    ),
    (
        "write-result-copy-schema",
        "module main\nenum WriteLifecycleResult { LifecycleWriteOk(i64), LifecycleWriteErr(i32) }\n"
        "fn main()->i32 { let result:WriteLifecycleResult=LifecycleWriteOk(23); "
        "match (result) { LifecycleWriteOk(count)=>{ print(count); } LifecycleWriteErr(error)=>{ print(error); } } return 0; }\n",
        "23\n",
    ),
)
PREDEFINED_FILESYSTEM_RESULT_SOURCES = (
    (
        "file-read-result-direct-drop",
        "module main\ncapability allocate;\n"
        "fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); "
        "let data:Buffer=buffer_new(allocator,4); let result:FileReadResult=ReadOk(data); "
        "drop(result); } return 0; }\n",
        "",
    ),
    (
        "file-read-result",
        "module main\ncapability allocate;\n"
        "fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); "
        "let data:Buffer=buffer_new(allocator,6); let result:FileReadResult=ReadOk(data); "
        "match (result) { ReadOk(payload)=>{ print(buffer_len(payload)); drop(payload); } "
        "ReadErr(error)=>{ } } } return 0; }\n",
        "0\n",
    ),
    (
        "file-write-result",
        "module main\nfn main()->i32 { let result:FileWriteResult=WriteOk(23); "
        "match (result) { WriteOk(count)=>{ print(count); } WriteErr(error)=>{ } } return 0; }\n",
        "23\n",
    ),
)
OWNED_TRY_PREFIX = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "enum Outcome { Ok(Marker), Err(i64) }\n"
    "fn consume(value:Outcome)->Outcome { let marker:Marker=try relay(value); "
    "drop(marker); return Err(7); }\n"
    "fn relay(value:Outcome)->Outcome { return value; }\n"
)
OWNED_TRY_SOURCES = (
    (
        "success",
        "fn main()->i32 { let marker:Marker=Marker { number:71 }; "
        "let input:Outcome=Ok(marker); let result:Outcome=consume(input); "
        "match (result) { Ok(payload) => { drop(payload); } Err(error) => { print(error); } } "
        "return 0; }\n",
        "71\n7\n",
    ),
    (
        "error",
        "fn main()->i32 { let input:Outcome=Err(11); let result:Outcome=consume(input); "
        "match (result) { Ok(payload) => { drop(payload); } Err(error) => { print(error); } } "
        "return 0; }\n",
        "11\n",
    ),
)
INVALID_OWNED_TRY_SOURCES = (
    (
        "reused-subject",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "enum Outcome { Ok(Marker), Err(i64) }\n"
        "fn consume(value:Outcome)->Outcome { let marker:Marker=try value; "
        "print(value); drop(marker); return Err(0); }\n"
        "fn main()->i32 { return 0; }\n",
    ),
    (
        "non-result-shape",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "enum Choice { Left(Marker), Right(i64) }\n"
        "fn consume(value:Choice)->Choice { let marker:Marker=try value; "
        "drop(marker); return Right(0); }\n"
        "fn main()->i32 { return 0; }\n",
    ),
)
RECURSIVE_OWNED_AGGREGATE_PREFIX = (
    "module main\n"
    "struct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "struct Wrapper { marker:Marker; }\n"
    "struct Outer { wrapper:Wrapper; }\n"
    "enum Parcel { Wrapped(Outer), Spare(Outer) }\n"
)
RECURSIVE_OWNED_AGGREGATE_SOURCES = (
    (
        "implicit-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:101 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; return 0; }\n",
        "101\n",
    ),
    (
        "explicit-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:103 }; let wrapper:Wrapper=Wrapper { marker:marker }; drop(wrapper); return 0; }\n",
        "103\n",
    ),
    (
        "move-no-double-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:107 }; let first:Wrapper=Wrapper { marker:marker }; let second:Wrapper=first; drop(second); return 0; }\n",
        "107\n",
    ),
    (
        "early-return-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:109 }; let wrapper:Wrapper=Wrapper { marker:marker }; if 1<2 { return 0; } else { return 1; } }\n",
        "109\n",
    ),
    (
        "replace",
        "fn main()->i32 { let first_marker:Marker=Marker { number:113 }; var target:Wrapper=Wrapper { marker:first_marker }; let second_marker:Marker=Marker { number:127 }; let replacement:Wrapper=Wrapper { marker:second_marker }; replace(target,replacement); drop(target); return 0; }\n",
        "113\n127\n",
    ),
    (
        "enum-match-transfer",
        "fn main()->i32 { let marker:Marker=Marker { number:131 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Spare(outer); match (parcel) { Wrapped(value) => { drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "131\n",
    ),
)
RECURSIVE_OWNED_AGGREGATE_CYCLE = (
    "module main\nstruct First { second:Second; }\nstruct Second { first:First; }\n"
    "fn main()->i32 { return 0; }\n"
)

MULTI_FIELD_OWNED_AGGREGATE_PREFIX = (
    "module main\n"
    "struct Marker { prefix:i64; number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "struct Pair { left:Marker; code:i64; right:Marker; }\n"
    "enum Packet { Full(Pair), Spare(Pair) }\n"
)
MULTI_FIELD_OWNED_AGGREGATE_SOURCES = (
    (
        "implicit-cleanup",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:233 }; let right:Marker=Marker { prefix:2, number:239 }; let pair:Pair=Pair { left:left, code:3, right:right }; return 0; }\n",
        "233\n239\n",
    ),
    (
        "explicit-drop",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:241 }; let right:Marker=Marker { prefix:2, number:251 }; let pair:Pair=Pair { left:left, code:3, right:right }; drop(pair); return 0; }\n",
        "241\n251\n",
    ),
    (
        "move-no-double-drop",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:257 }; let right:Marker=Marker { prefix:2, number:263 }; let first:Pair=Pair { left:left, code:3, right:right }; let second:Pair=first; drop(second); return 0; }\n",
        "257\n263\n",
    ),
    (
        "replace",
        "fn main()->i32 { let old_left:Marker=Marker { prefix:1, number:269 }; let old_right:Marker=Marker { prefix:2, number:271 }; var target:Pair=Pair { left:old_left, code:3, right:old_right }; let new_left:Marker=Marker { prefix:4, number:277 }; let new_right:Marker=Marker { prefix:5, number:281 }; let replacement:Pair=Pair { left:new_left, code:6, right:new_right }; replace(target,replacement); drop(target); return 0; }\n",
        "269\n271\n277\n281\n",
    ),
    (
        "enum-match-transfer",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:283 }; let right:Marker=Marker { prefix:2, number:293 }; let pair:Pair=Pair { left:left, code:3, right:right }; let packet:Packet=Spare(pair); match (packet) { Full(value) => { drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "283\n293\n",
    ),
)
MULTI_FIELD_SCALAR_AGGREGATE_SOURCE = (
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i64 { let pair:Pair=Pair { right:2, left:1 }; return pair.left*10+pair.right; }\n"
)
NESTED_MULTI_FIELD_AGGREGATE_SOURCE = (
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "struct Wrapper { pair:Pair; }\n"
    "fn main()->i64 { let pair:Pair=Pair { right:7, left:3 }; "
    "let wrapper:Wrapper=Wrapper { pair:pair }; drop(wrapper); return 37; }\n"
)
INVALID_MULTI_FIELD_AGGREGATE_SOURCES = (
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i32 { let pair:Pair=Pair { left:1, left:2 }; return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i32 { let pair:Pair=Pair { left:1 }; return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i32 { let pair:Pair=Pair { left:1, missing:2 }; return 0; }\n",
    "module main\nstruct First { value:i64; second:Second; }\n"
    "struct Second { value:i64; first:First; }\nfn main()->i32 { return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "destructor Pair { print(self.missing); }\nfn main()->i32 { return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "destructor Pair { print(self.left); }\ndestructor Pair { print(self.right); }\n"
    "fn main()->i32 { return 0; }\n",
)

PATH_SENSITIVE_OWNED_SOURCES = (
    (
        "scoped-if-explicit-drop",
        "fn main()->i32 { if 1<2 { let marker:Marker=Marker { number:137 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); } else {} return 0; }\n",
        "137\n",
    ),
    (
        "scoped-while-explicit-drop",
        "fn main()->i32 { var flag:i64=0; while flag<1 { let marker:Marker=Marker { number:139 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); flag=flag+1; } return 0; }\n",
        "139\n",
    ),
    (
        "outer-drop-converges",
        "fn main()->i32 { let marker:Marker=Marker { number:141 }; let owned:Wrapper=Wrapper { marker:marker }; if 1<2 { drop(owned); } else { drop(owned); } return 0; }\n",
        "141\n",
    ),
    (
        "drop-or-early-return",
        "fn main()->i32 { let marker:Marker=Marker { number:149 }; let owned:Wrapper=Wrapper { marker:marker }; if 1<2 { drop(owned); } else { return 0; } return 0; }\n",
        "149\n",
    ),
    (
        "scoped-replacement-transfer",
        "fn main()->i32 { let first:Marker=Marker { number:179 }; var target:Wrapper=Wrapper { marker:first }; if 1<2 { let second:Marker=Marker { number:181 }; let replacement:Wrapper=Wrapper { marker:second }; replace(target,replacement); } else {} drop(target); return 0; }\n",
        "179\n181\n",
    ),
    (
        "scoped-else-explicit-drop",
        "fn main()->i32 { if 2<1 {} else { let marker:Marker=Marker { number:193 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); } return 0; }\n",
        "193\n",
    ),
    (
        "scoped-drop-before-early-return",
        "fn main()->i32 { if 1<2 { let marker:Marker=Marker { number:199 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); return 0; } else {} return 1; }\n",
        "199\n",
    ),
    (
        "scoped-match-arm-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:211 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Wrapped(outer); match (parcel) { Wrapped(value) => { let inner_marker:Marker=Marker { number:223 }; let arm_owned:Wrapper=Wrapper { marker:inner_marker }; drop(arm_owned); drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "223\n211\n",
    ),
)

PATH_SENSITIVE_CAPABILITY_OWNED_SOURCES = (
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "capability allocate;\n"
        + "fn main()->i32 { if 1<2 { with capability allocate { let marker:Marker=Marker { number:191 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); } } else {} return 0; }\n",
        "191\n",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "capability allocate;\n"
        + "fn main()->i32 { with capability allocate { let marker:Marker=Marker { number:197 }; let function_owned:Wrapper=Wrapper { marker:marker }; } return 0; }\n",
        "197\n",
    ),
)

PATH_SENSITIVE_OWNED_REJECTIONS = (
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { if 1<2 { let marker:Marker=Marker { number:151 }; let leaked:Wrapper=Wrapper { marker:marker }; } else {} return 0; }\n",
        "M5212: scoped owned binding leaked",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:157 }; let owned:Wrapper=Wrapper { marker:marker }; if 1<2 { drop(owned); } else {} drop(owned); return 0; }\n",
        "M5101: binding owned already consumed",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:163 }; let owned:Wrapper=Wrapper { marker:marker }; drop(owned); drop(owned); return 0; }\n",
        "M5101: binding owned already consumed",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:167 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Wrapped(outer); match (parcel) { Wrapped(value) => { print(1); } Spare(value) => { drop(value); } } return 0; }\n",
        "M5211: owned match payload value",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { var flag:i64=0; while flag<1 { let marker:Marker=Marker { number:173 }; let leaked:Wrapper=Wrapper { marker:marker }; flag=flag+1; } return 0; }\n",
        "M5212: scoped owned binding leaked",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:227 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Wrapped(outer); match (parcel) { Wrapped(value) => { let inner_marker:Marker=Marker { number:229 }; let leaked:Wrapper=Wrapper { marker:inner_marker }; drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "M5212: scoped owned binding leaked",
    ),
)
SINGLE_I64_STRUCT_SOURCE = (
    "module main\n"
    "struct Box { value:i64; }\n"
    "fn main()->i64 { let box:Box=Box { value:7 }; return box.value; }\n"
)
INVALID_SINGLE_I64_STRUCT_FIELD_SOURCE = (
    "module main\n"
    "struct Box { value:i64; }\n"
    "fn main()->i64 { let box:Box=Box { wrong:7 }; return box.value; }\n"
)
INVALID_SINGLE_I64_STRUCT_REPLACE_SOURCE = (
    "module main\nstruct Box { value:i64; }\n"
    "fn main()->i64 { var target:Box=Box { value:1 }; let replacement:Box=Box { value:7 }; replace(target,replacement); return target.value; }\n"
)
SINGLE_I64_STRUCT_LIFECYCLE_SOURCES = (
    (
        "explicit-drop",
        "module main\nstruct Box { value:i64; }\n"
        "fn main()->i64 { let box:Box=Box { value:7 }; drop(box); return 7; }\n",
    ),
    (
        "move",
        "module main\nstruct Box { value:i64; }\n"
        "fn main()->i64 { let first:Box=Box { value:7 }; let second:Box=first; return second.value; }\n",
    ),
)
DESTRUCTOR_I64_STRUCT_LIFECYCLE_SOURCES = (
    (
        "implicit-cleanup",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let marker:Marker=Marker { number:7 }; return 0; }\n",
        "7\n",
    ),
    (
        "explicit-drop",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let marker:Marker=Marker { number:11 }; drop(marker); return 0; }\n",
        "11\n",
    ),
    (
        "move-no-double-drop",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let first:Marker=Marker { number:13 }; let second:Marker=first; drop(second); return 0; }\n",
        "13\n",
    ),
    (
        "early-return-cleanup",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let marker:Marker=Marker { number:17 }; if 1<2 { return 0; } else { return 1; } }\n",
        "17\n",
    ),
    (
        "replace",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { var target:Marker=Marker { number:1 }; let replacement:Marker=Marker { number:19 }; replace(target,replacement); drop(target); return 0; }\n",
        "1\n19\n",
    ),
    (
        "copy-field-mutation-and-control-flow",
        "module main\nstruct Counter { number:i64; }\n"
        "destructor Counter { if self.number != 0 { self.number=checked_add(self.number,1); } "
        "else { self.number=10; } while self.number < 3 { "
        "self.number=checked_add(self.number,1); } print(self.number); }\n"
        "fn main()->i32 { let first:Counter=Counter { number:1 }; "
        "let second:Counter=Counter { number:0 }; return 0; }\n",
        "10\n3\n",
    ),
)
CONSTANT_EXPRESSION_DESTRUCTOR_I64_STRUCT_SOURCE = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { print(23); }\n"
    "fn main()->i32 { let marker:Marker=Marker { number:23 }; return 0; }\n"
)
OWNERSHIP_CHANGING_DESTRUCTOR_SOURCE = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { let copy:i64=self.number; print(copy); }\n"
    "fn main()->i32 { return 0; }\n"
)
OWNED_CALLABLE_LIFECYCLE_SOURCE = (
    "module main\n"
    "struct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "fn relay(value:Marker)->Marker { return value; }\n"
    "fn main()->i64 { let marker:Marker=Marker { number:31 }; "
    "let returned:Marker=relay(marker); drop(returned); return 0; }\n"
)
BORROWED_CALLABLE_LIFECYCLE_SOURCE = (
    "module main\n"
    "struct Value { number:i64; }\n"
    "fn expose(borrow value:Value)->borrow Value { return value; }\n"
    "fn relay(borrow value:Value)->borrow Value { return expose(value); }\n"
    "fn read(borrow value:Value)->i64 { return value.number; }\n"
    "fn main()->i64 { let value:Value=Value { number:23 }; "
    "return read(relay(value)); }\n"
)
MUTABLE_BORROW_CALLABLE_SOURCE = (
    "module main\n"
    "struct Value { number:i64; }\n"
    "fn expose_mut(borrow_mut value:Value)->borrow_mut Value { print(1); return value; }\n"
    "fn update(borrow_mut value:Value)->i64 { value.number=23; return value.number; }\n"
    "fn main()->i64 { var value:Value=Value { number:1 }; "
    "expose_mut(value).number=23; return value.number; }\n"
)
INVALID_CALLABLE_OWNERSHIP_SOURCES = (
    (
        "immutable-mutable-borrow",
        "module main\nstruct Value { number:i64; }\n"
        "fn update(borrow_mut value:Value)->i64 { return value.number; }\n"
        "fn main()->i64 { let value:Value=Value { number:1 }; return update(value); }\n",
        "not mutable",
    ),
    (
        "shared-to-mutable-escalation",
        "module main\nstruct Value { number:i64; }\n"
        "fn expose(borrow value:Value)->borrow Value { return value; }\n"
        "fn update(borrow_mut value:Value)->i64 { return value.number; }\n"
        "fn main()->i64 { var value:Value=Value { number:1 }; return update(expose(value)); }\n",
        "shared borrowed return cannot satisfy borrow_mut",
    ),
    (
        "conflicting-loans",
        "module main\nstruct Value { number:i64; }\n"
        "fn collide(borrow_mut left:Value,borrow right:Value)->i64 { return left.number; }\n"
        "fn main()->i64 { var value:Value=Value { number:1 }; return collide(value,value); }\n",
        "conflicting loans",
    ),
    (
        "move-while-loaned",
        "module main\nstruct Value { number:i64; }\n"
        "fn expose(borrow value:Value)->borrow Value { return value; }\n"
        "fn observe_and_consume(borrow view:Value,owned:Value)->i64 { return view.number; }\n"
        "fn main()->i64 { let value:Value=Value { number:1 }; return observe_and_consume(expose(value),value); }\n",
        "cannot move value while its borrowed result is live",
    ),
    (
        "stored-borrowed-return",
        "module main\nstruct Value { number:i64; }\n"
        "fn expose(borrow value:Value)->borrow Value { return value; }\n"
        "fn main()->i64 { let value:Value=Value { number:1 }; let alias:Value=expose(value); return alias.number; }\n",
        "borrowed return cannot be stored",
    ),
    (
        "borrowed-return-by-value",
        "module main\nstruct Value { number:i64; }\n"
        "fn expose(borrow value:Value)->borrow Value { return value; }\n"
        "fn consume(value:Value)->i64 { return value.number; }\n"
        "fn main()->i64 { let value:Value=Value { number:1 }; return consume(expose(value)); }\n",
        "borrowed return cannot be passed by value",
    ),
    (
        "inconsistent-return-origin",
        "module main\nstruct Value { number:i64; }\n"
        "fn choose(borrow left:Value,borrow right:Value)->borrow Value { if left.number { return left; } else { return right; } }\n"
        "fn main()->i64 { return 0; }\n",
        "one consistent parameter origin",
    ),
    (
        "drop-borrowed-parameter",
        "module main\nstruct Value { number:i64; }\n"
        "fn invalid(borrow value:Value)->i64 { drop(value); return 0; }\n"
        "fn main()->i64 { return 0; }\n",
        "cannot drop borrowed parameter",
    ),
)
CONTROL_FLOW_SOURCES = (
    (
        "if-else",
        "module main\nfn main()->i32 { if 2<3 { return 17; } else { return 18; } }\n",
        17,
        "",
    ),
    (
        "nested-early-return",
        "module main\nfn main()->i32 { if 1<2 { if 4>3 { return 19; } else { return 20; } } else { return 21; } }\n",
        19,
        "",
    ),
    (
        "loop-early-return",
        "module main\nfn main()->i32 { while 1<2 { if 3==3 { return 22; } else { return 23; } } return 24; }\n",
        22,
        "",
    ),
    (
        "skipped-loop",
        "module main\nfn main()->i32 { while 2<1 { return 25; } return 26; }\n",
        26,
        "",
    ),
    (
        "branch-loop-assignment",
        "module main\nfn main()->i32 { var x:i32=1; if 2<3 { x=x+4; } else { x=9; } while x<7 { x=x+1; } x+100; return x+20; }\n",
        27,
        "",
    ),
    (
        "loop-print",
        "module main\nfn main()->i32 { var x:i32=0; while x<3 { print(x); x=x+1; } return x; }\n",
        3,
        "0\n1\n2\n",
    ),
)
INVALID_CONTROL_FLOW_SOURCE = (
    "module main\nfn main()->i32 { if 1<2 { return 7; } else { return 8; }\n"
)
IMMUTABLE_ASSIGNMENT_SOURCE = (
    "module main\nfn main()->i32 { let x:i32=1; x=2; return x; }\n"
)


def _project(tmp_path: Path, source: str = SOURCE) -> Path:
    root = tmp_path / "native_driver_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname = "native_driver_project"\nentry = "src/main.mrt"\nsources = ["src/**/*.mrt"]\n\n'
        '[build]\nc_flags = ["-O2"]\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(source, encoding="utf-8")
    return root


@pytest.fixture(scope="session")
def driver(
    tmp_path_factory: pytest.TempPathFactory,
) -> NativeReplacementDriver:
    """Build the immutable frontend driver once for isolated behavior tests."""

    output_directory = tmp_path_factory.mktemp("concrete-native-replacement-driver")
    return build_native_replacement_driver(output_directory / "merit-native-replacement-driver")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_build_concrete_native_driver_reaches_replacement_executable_without_python_semantic_lowering(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")

    completed = subprocess.run(
        [str(driver.executable)],
        input=SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1
    assert len(bundle.encoded_snapshots) == 1

    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-driver")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_lowers_each_function_into_one_bundle_item(tmp_path: Path, driver: NativeReplacementDriver) -> None:

    completed = subprocess.run(
        [str(driver.executable)],
        input=MULTI_FUNCTION_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 2
    assert len(bundle.encoded_snapshots) == 2

    root = _project(tmp_path, MULTI_FUNCTION_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 2

    artifact = build_replacement_project(project, root / "build" / "replacement-native-multifunction")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_monomorphizes_generic_function_before_mir(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=GENERIC_FUNCTION_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=GENERIC_FUNCTION_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert len(bundle.functions) == 2
    assert all(snapshot.effective_source_bytes for snapshot in bundle.functions)
    effective_source = bytes(bundle.functions[0].effective_source_bytes).decode("utf-8")
    assert "fn identity__i64(value:i64)->i64" in effective_source
    assert "identity<i64>" not in effective_source

    root = _project(tmp_path, GENERIC_FUNCTION_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-generic-function")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True, check=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-generic-function")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert replacement.returncode == 0, (replacement.returncode, replacement.stdout, replacement.stderr)
    assert (replacement.returncode, replacement.stdout, replacement.stderr) == (
        reference.returncode, reference.stdout, reference.stderr,
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_monomorphizes_generic_struct_and_payload_enum_before_mir(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=GENERIC_AGGREGATE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=GENERIC_AGGREGATE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert len(bundle.functions) == 1
    effective_source = bytes(bundle.functions[0].effective_source_bytes).decode("utf-8")
    assert "struct Pair__i64__i32" in effective_source
    assert "enum Option__i64" in effective_source
    assert "Option__i64__Some(i64)" in effective_source

    root = _project(tmp_path, GENERIC_AGGREGATE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-generic-aggregate")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True, check=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-generic-aggregate")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True, check=True)
    assert (replacement.returncode, replacement.stdout, replacement.stderr) == (
        reference.returncode, reference.stdout, reference.stderr,
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_uses_static_user_trait_dispatch_before_mir(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=GENERIC_TRAIT_DISPATCH_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=GENERIC_TRAIT_DISPATCH_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert len(bundle.functions) == 3
    effective_source = bytes(bundle.functions[0].effective_source_bytes).decode("utf-8")
    assert "impl__Summarized__Point__score" in effective_source
    assert "summarize__Point" in effective_source

    root = _project(tmp_path, GENERIC_TRAIT_DISPATCH_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-generic-trait")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True, check=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-generic-trait")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True, check=True)
    assert (replacement.returncode, replacement.stdout, replacement.stderr) == (
        reference.returncode, reference.stdout, reference.stderr,
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_vec_i64_lifecycle_before_mir(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=GENERIC_VEC_I64_SOURCE,
        text=True, capture_output=True,
    )
    assert first.returncode == 0, (first.returncode, first.stdout, first.stderr)
    second = subprocess.run(
        [str(driver.executable)], input=GENERIC_VEC_I64_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert len(bundle.functions) == 1
    effective_source = bytes(bundle.functions[0].effective_source_bytes).decode("utf-8")
    assert "Vec__i64" in effective_source
    assert "vec_new__i64" in effective_source

    root = _project(tmp_path, GENERIC_VEC_I64_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-vec-i64")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True, check=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-vec-i64")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True, check=True)
    assert (replacement.returncode, replacement.stdout, replacement.stderr) == (
        reference.returncode, reference.stdout, reference.stderr,
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_uses_ordinary_ownership_for_generic_calls(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run([str(driver.executable)], input=GENERIC_OWNERSHIP_SOURCE, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=GENERIC_OWNERSHIP_SOURCE, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    effective_source = bytes(bundle.functions[0].effective_source_bytes).decode("utf-8")
    assert "fn forward__Buffer(value:Buffer)->Buffer" in effective_source
    assert "fn observe__Buffer(borrow value:Buffer)->i32" in effective_source

    root = _project(tmp_path, GENERIC_OWNERSHIP_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-generic-ownership")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True, check=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-generic-ownership")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True, check=True)
    assert (replacement.returncode, replacement.stdout, replacement.stderr) == (
        reference.returncode, reference.stdout, reference.stderr,
    ) == (0, "1\n5\n", "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_owned_and_nested_vec_lifecycle_before_mir(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run([str(driver.executable)], input=GENERIC_VEC_OWNED_SOURCE, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=GENERIC_VEC_OWNED_SOURCE, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    effective_source = bytes(bundle.functions[0].effective_source_bytes).decode("utf-8")
    assert "Vec__Marker" in effective_source
    assert "Vec__Vec__Marker" in effective_source

    root = _project(tmp_path, GENERIC_VEC_OWNED_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-vec-owned")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True, check=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-vec-owned")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert replacement.returncode == 0, (replacement.returncode, replacement.stdout, replacement.stderr)
    assert (replacement.returncode, replacement.stdout, replacement.stderr) == (
        reference.returncode, reference.stdout, reference.stderr,
    ) == (0, "41\n1\n43\n43\n1\n53\n", "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,source", M4_REJECTED_SOURCES)
def test_concrete_native_driver_fails_closed_for_invalid_generic_trait_and_vec_semantics(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, source: str,
) -> None:
    with pytest.raises((CompileError, UnexpectedInput)):
        Checker(parse(source)).check()

    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode, second.stdout, second.stderr,
    )

    root = _project(tmp_path / case_name, source)
    try:
        project = load_project(root / "Merit.toml")
    except ProjectError:
        assert not (root / ".merit" / "replacement-build-v1.json").exists()
        return
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_complete_primitive_integer_success_surface(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=PRIMITIVE_INTEGER_SURFACE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=PRIMITIVE_INTEGER_SURFACE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=PRIMITIVE_INTEGER_SURFACE_SOURCE,
        module_name="main",
        snapshot=bundle.functions[0],
        capability_names={},
    )
    represented = {local.type.name for local in module.functions[0].locals}
    assert {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"} <= represented

    root = _project(tmp_path, PRIMITIVE_INTEGER_SURFACE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-primitive-integers")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-primitive-integers")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert replacement.stdout == "127\n29877\n2000000\n2\n255\n61000\n2000000000\n3000000000000000000\n"


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_resolves_exact_numeric_declaration_descriptors(
    driver: NativeReplacementDriver,
) -> None:
    Checker(parse(NUMERIC_DESCRIPTOR_SOURCE)).check()
    first = subprocess.run(
        [str(driver.executable)], input=NUMERIC_DESCRIPTOR_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=NUMERIC_DESCRIPTOR_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert bundle.functions[0].numeric_type_descriptors == (
        (1_300_000, 1, 0, 0, 0, 18, 2, 0, 0, 0, 0),
        (1_400_000, 2, 0, 11, 0, 0, 0, 1, 9_999_999_999, 999_999_999, 0),
        (1_400_001, 2, 1, 1, -1, 9_223_372_036, 854_775_808, 1, 9_223_372_036, 854_775_807, 0),
    )
    materialize_resolved_source_function_snapshot(
        source=NUMERIC_DESCRIPTOR_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={},
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_exact_numeric_literals(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=EXACT_NUMERIC_LITERAL_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=EXACT_NUMERIC_LITERAL_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=EXACT_NUMERIC_LITERAL_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={},
    )
    assert {local.type.name for local in module.functions[0].locals} >= {
        "decimal_0_18_2_0", "bounded_0_11_0_9999999999999999999",
    }

    root = _project(tmp_path, EXACT_NUMERIC_LITERAL_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert replacement.stdout == "1.25\n9999999999999999999\n"


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_exact_numeric_arithmetic_and_rounding(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=EXACT_NUMERIC_ARITHMETIC_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=EXACT_NUMERIC_ARITHMETIC_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    materialize_resolved_source_function_snapshot(
        source=EXACT_NUMERIC_ARITHMETIC_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={},
    )

    root = _project(tmp_path, EXACT_NUMERIC_ARITHMETIC_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert replacement.stdout == (
        "0.12\n0.13\n0.12\n0.13\n0.12\n-0.12\n-0.13\n"
        "3.25\n-0.75\n2.50\n0.12\n300\n-300\n-156\n-149\n1\n0\n"
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,declaration,body,expected_status,message", EXACT_NUMERIC_FAILURE_SOURCES)
def test_concrete_native_driver_preserves_exact_numeric_runtime_failures(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str,
    declaration: str, body: str, expected_status: int, message: str,
) -> None:
    source = f"module main\n{declaration}\nfn main()->i32 {{ {body} return 0; }}\n"
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert replacement.returncode == reference.returncode == expected_status
    assert replacement.stdout == reference.stdout == ""
    assert message in replacement.stderr


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_exact_numeric_aggregate_fields(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=EXACT_NUMERIC_AGGREGATE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=EXACT_NUMERIC_AGGREGATE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=EXACT_NUMERIC_AGGREGATE_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={},
    )
    invoice_type = next(local.type for local in module.functions[0].locals if local.name == "invoice")
    assert [field.name for field in invoice_type.arguments] == [
        "decimal_0_18_2_0", "bounded_0_11_1_9999999999999999999",
    ]

    root = _project(tmp_path, EXACT_NUMERIC_AGGREGATE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert replacement.stdout == "12.50\n9999999999999999999\n12.75\n"


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_utf8_string_surface(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=STRING_SURFACE_SOURCE, text=True,
        encoding="utf-8", errors="strict", capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=STRING_SURFACE_SOURCE, text=True,
        encoding="utf-8", errors="strict", capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=STRING_SURFACE_SOURCE, module_name="main", snapshot=bundle.functions[0], capability_names={},
    )
    assert "String" in {local.type.name for local in module.functions[0].locals}

    root = _project(tmp_path, STRING_SURFACE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert replacement.stdout == "Aé\n3\n65\n195\n169\n0\n"


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_buffer_and_slice_surface(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    first = subprocess.run([str(driver.executable)], input=BUFFER_SURFACE_SOURCE, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=BUFFER_SURFACE_SOURCE, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=BUFFER_SURFACE_SOURCE, module_name="main", snapshot=bundle.functions[0], capability_names={0: "allocate"},
    )
    assert {"Allocator", "Buffer", "ByteSlice"} <= {local.type.name for local in module.functions[0].locals}

    root = _project(tmp_path, BUFFER_SURFACE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert replacement.stdout == "1\n0\n1\n4\n98\nabc!\n2\n98\n99\n0\n"


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_status,message", TEXT_BUFFER_FAILURE_SOURCES)
def test_concrete_native_driver_preserves_text_buffer_runtime_failures(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, body: str,
    expected_status: int, message: str,
) -> None:
    source = f"module main\n{body}\n"
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert replacement.returncode == reference.returncode == expected_status
    assert replacement.stdout == reference.stdout == ""
    assert message in replacement.stderr


@pytest.mark.parametrize("case_name,operation", BUFFER_CAPABILITY_FAILURE_SOURCES)
def test_concrete_native_driver_rejects_buffer_allocation_without_lexical_capability(
    driver: NativeReplacementDriver, case_name: str, operation: str,
) -> None:
    source = (
        "module main\ncapability allocate;\nfn main()->i32 { "
        f"let allocator:Allocator=system_allocator(); {operation} return 0; }}\n"
    )
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (second.returncode, second.stdout, second.stderr) == (first.returncode, first.stdout, first.stderr)
    assert "replacement driver status" in first.stderr


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize(
    "case_name,source,expected",
    [
        ("signed-division", SIGNED_DIVISION_SOURCE, "-2\n-2\n2\n"),
        ("checked-primitive-builtins", CHECKED_PRIMITIVE_BUILTIN_SOURCE, "307\n293\n2100\n"),
        ("primitive-comparisons", PRIMITIVE_COMPARISON_SOURCE, "1\n1\n0\n0\n0\n1\n1\n0\n"),
    ],
)
def test_concrete_native_driver_executes_remaining_primitive_operations(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, source: str, expected: str,
) -> None:
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert replacement.stdout == expected


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,type_name,left,operator,right,message", PRIMITIVE_INTEGER_FAILURE_SOURCES)
def test_concrete_native_driver_preserves_primitive_integer_failure_policy(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, type_name: str,
    left: str, operator: str, right: str, message: str,
) -> None:
    source = (
        "module main\nfn main()->i32 { "
        f"let left:{type_name}={left}; let right:{type_name}={right}; "
        f"print(left{operator}right); return 0; }}\n"
    )
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert f"Merit {message}" in replacement.stderr


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_closes_branch_loop_and_early_return_control_flow(tmp_path: Path, driver: NativeReplacementDriver) -> None:

    for case_name, source, expected_status, expected_stdout in CONTROL_FLOW_SOURCES:
        root = _project(tmp_path / case_name, source)
        project = load_project(root / "Merit.toml")

        _, _, reference_executable = build(project, root / "build" / "reference")
        reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
        assert reference.returncode == expected_status
        assert reference.stdout == expected_stdout

        first = subprocess.run(
            [str(driver.executable)], input=source, text=True, capture_output=True, check=True
        )
        second = subprocess.run(
            [str(driver.executable)], input=source, text=True, capture_output=True, check=True
        )
        assert first.stdout == second.stdout
        bundle = decode_resolved_source_function_bundle(
            tuple(int(line) for line in first.stdout.splitlines())
        )
        assert len(bundle.functions) == 1

        prepared = prepare_replacement_artifacts(project, driver)
        assert len(prepared.snapshot_paths) == 1
        artifact = build_replacement_project(project, root / "build" / "replacement")
        replacement = subprocess.run(
            [str(artifact.executable)], text=True, capture_output=True
        )
        assert replacement.returncode == reference.returncode
        assert replacement.stdout == reference.stdout


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_rejects_malformed_control_flow_deterministically(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    with pytest.raises(UnexpectedInput):
        parse(INVALID_CONTROL_FLOW_SOURCE)

    first = subprocess.run(
        [str(driver.executable)], input=INVALID_CONTROL_FLOW_SOURCE, text=True, capture_output=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=INVALID_CONTROL_FLOW_SOURCE, text=True, capture_output=True
    )
    assert first.returncode != 0
    assert first.stderr.startswith("replacement driver status ")
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )
    assert first.stderr.startswith("replacement driver status ")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_rejects_immutable_assignment_deterministically(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    root = _project(tmp_path, IMMUTABLE_ASSIGNMENT_SOURCE)
    project = load_project(root / "Merit.toml")
    with pytest.raises(CompileError, match="cannot assign to immutable"):
        build(project, root / "build" / "reference")

    first = subprocess.run(
        [str(driver.executable)], input=IMMUTABLE_ASSIGNMENT_SOURCE, text=True, capture_output=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=IMMUTABLE_ASSIGNMENT_SOURCE, text=True, capture_output=True
    )
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_derives_capability_catalog_from_source(tmp_path: Path, driver: NativeReplacementDriver) -> None:

    completed = subprocess.run(
        [str(driver.executable)],
        input=CAPABILITY_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1

    root = _project(tmp_path, CAPABILITY_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-capability")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_undeclared_capability(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    root = _project(tmp_path, UNKNOWN_CAPABILITY_SOURCE)
    project = load_project(root / "Merit.toml")

    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_derives_payload_free_enum_catalog_from_source(tmp_path: Path, driver: NativeReplacementDriver) -> None:

    completed = subprocess.run(
        [str(driver.executable)],
        input=ENUM_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1

    root = _project(tmp_path, ENUM_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-enum")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_derives_match_enum_identity_from_declared_subject_type(tmp_path: Path, driver: NativeReplacementDriver) -> None:

    completed = subprocess.run(
        [str(driver.executable)],
        input=MULTI_ENUM_TYPED_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1

    root = _project(tmp_path, MULTI_ENUM_TYPED_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-typed-match")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_when_match_subject_type_is_not_an_enum(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    root = _project(tmp_path, UNTYPED_MULTI_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")

    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_copy_payload_enum_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run([str(driver.executable)], input=PAYLOAD_ENUM_SOURCE, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=PAYLOAD_ENUM_SOURCE, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=PAYLOAD_ENUM_SOURCE,
        module_name="main",
        snapshot=bundle.functions[0],
        capability_names={},
    )
    instructions = [instruction for block in module.functions[0].blocks for instruction in block.instructions]
    assert [instruction.kind for instruction in instructions].count("construct") == 1
    assert [instruction.symbol for instruction in instructions if instruction.kind == "load_field"] == [
        "tag", "payload_0", "payload_1"
    ]
    root = _project(tmp_path, PAYLOAD_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")

    _, _, reference_executable = build(project, root / "build" / "reference-copy-payload-enum")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement-copy-payload-enum")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (7, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_represents_owned_buffer_payload_enum_catalog(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=OWNED_PAYLOAD_ENUM_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=OWNED_PAYLOAD_ENUM_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=OWNED_PAYLOAD_ENUM_SOURCE, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    assert len(bundle.functions[0].type_descriptors) == 1
    assert module.functions[0].name == "main"
    root = _project(tmp_path, OWNED_PAYLOAD_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", OWNED_DESTRUCTOR_PAYLOAD_ENUM_SOURCES)
def test_concrete_native_driver_executes_owned_destructor_payload_enum_lifecycle(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, body: str, expected_stdout: str
) -> None:
    source = OWNED_DESTRUCTOR_PAYLOAD_ENUM_PREFIX + body
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    assert any(local.type.name.startswith("enum_owned_payload_") for local in module.functions[0].locals)

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_mixed_owned_payload_enum_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=MIXED_OWNED_PAYLOAD_ENUM_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=MIXED_OWNED_PAYLOAD_ENUM_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=MIXED_OWNED_PAYLOAD_ENUM_SOURCE,
        module_name="main",
        snapshot=bundle.functions[0],
        capability_names={},
    )
    enum_type = next(
        local.type
        for local in module.functions[0].locals
        if local.type.name.startswith("enum_owned_payload_") and local.type.arguments
    )
    assert [payload.name for payload in enum_type.arguments] == ["struct_i64_destructor_0", "i64"]
    root = _project(tmp_path, MIXED_OWNED_PAYLOAD_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-mixed-payload-enum")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-mixed-payload-enum")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, "61\n67\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_minimal_buffer_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=MINIMAL_BUFFER_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=MINIMAL_BUFFER_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=MINIMAL_BUFFER_LIFECYCLE_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={0: "allocate"},
    )
    assert any(local.type.name == "Buffer" for local in module.functions[0].locals)
    root = _project(tmp_path, MINIMAL_BUFFER_LIFECYCLE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-buffer")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-buffer")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, "0\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_buffer_replace_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=BUFFER_REPLACE_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=BUFFER_REPLACE_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    function = materialize_resolved_source_function_snapshot(
        source=BUFFER_REPLACE_LIFECYCLE_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={0: "allocate"},
    ).functions[0]
    instructions = [instruction for block in function.blocks for instruction in block.instructions]
    target_local = next(local.local_id for local in function.locals if local.name == "target")
    replacement_local = next(local.local_id for local in function.locals if local.name == "replacement")
    replace_move = next(
        index for index, instruction in enumerate(instructions)
        if instruction.kind == "move"
        and instruction.result == target_local
        and instruction.operands == (replacement_local,)
    )
    assert any(
        instruction.kind == "drop" and instruction.operands == (target_local,)
        for instruction in instructions[:replace_move]
    )
    root = _project(tmp_path, BUFFER_REPLACE_LIFECYCLE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-buffer-replace")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-buffer-replace")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, "0\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_borrowed_buffer_field_replace_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=BORROWED_BUFFER_FIELD_REPLACE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=BORROWED_BUFFER_FIELD_REPLACE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert len(bundle.functions) == 2
    main = materialize_resolved_source_function_snapshot(
        source=BORROWED_BUFFER_FIELD_REPLACE_SOURCE, module_name="main",
        snapshot=bundle.functions[1], capability_names={0: "allocate"},
    ).functions[0]
    instructions = [instruction for block in main.blocks for instruction in block.instructions]
    field_store = next(index for index, instruction in enumerate(instructions) if instruction.kind == "store_field")
    assert sum(instruction.kind == "call" and instruction.symbol == "expose_mut" for instruction in instructions) == 1
    assert instructions[field_store].ownership == "moved"
    root = _project(tmp_path, BORROWED_BUFFER_FIELD_REPLACE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-borrowed-buffer-field")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-borrowed-buffer-field")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, "1\n0\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_buffer_struct_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=BUFFER_STRUCT_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=BUFFER_STRUCT_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=BUFFER_STRUCT_LIFECYCLE_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={0: "allocate"},
    )
    resource_type = next(local.type for local in module.functions[0].locals if local.type.name.startswith("struct_owned_field_"))
    assert resource_type.arguments == (next(local.type for local in module.functions[0].locals if local.type.name == "Buffer"),)
    root = _project(tmp_path, BUFFER_STRUCT_LIFECYCLE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-buffer-struct")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-buffer-struct")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, "0\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,source,expected_stdout", FILESYSTEM_RESULT_LIFECYCLE_SOURCES)
def test_concrete_native_driver_executes_filesystem_result_lifecycle_shapes(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, source: str, expected_stdout: str
) -> None:
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0],
        capability_names={0: "allocate"} if "capability allocate" in source else {},
    )
    assert any(local.type.name.startswith("enum_") for local in module.functions[0].locals)
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,source,expected_stdout", PREDEFINED_FILESYSTEM_RESULT_SOURCES)
def test_concrete_native_driver_executes_predefined_filesystem_result_lifecycle(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, source: str, expected_stdout: str
) -> None:
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0],
        capability_names={0: "allocate"} if "capability allocate" in source else {},
    )
    assert any(local.type.name.startswith("enum_") for local in module.functions[0].locals)
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", OWNED_TRY_SOURCES)
def test_concrete_native_driver_executes_owned_try_lifecycle(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, body: str, expected_stdout: str
) -> None:
    source = OWNED_TRY_PREFIX + body
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    consume = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    ).functions[0]
    assert any(block.terminator.kind == "switch" for block in consume.blocks)
    assert sum(block.terminator.kind == "return" for block in consume.blocks) == 2

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,source", INVALID_OWNED_TRY_SOURCES)
def test_concrete_native_driver_rejects_invalid_owned_try_lifecycle(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, source: str
) -> None:
    with pytest.raises(CompileError):
        Checker(parse(source)).check()
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode, second.stdout, second.stderr
    )
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", RECURSIVE_OWNED_AGGREGATE_SOURCES)
def test_concrete_native_driver_executes_recursive_owned_aggregate_lifecycle(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, body: str, expected_stdout: str
) -> None:
    source = RECURSIVE_OWNED_AGGREGATE_PREFIX + body
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert bundle.functions[0].type_descriptors
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    assert any(local.type.name.startswith("struct_owned_field_") for local in module.functions[0].locals)

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_recursive_owned_aggregate_cycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run([str(driver.executable)], input=RECURSIVE_OWNED_AGGREGATE_CYCLE, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=RECURSIVE_OWNED_AGGREGATE_CYCLE, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)
    root = _project(tmp_path, RECURSIVE_OWNED_AGGREGATE_CYCLE)
    project = load_project(root / "Merit.toml")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", MULTI_FIELD_OWNED_AGGREGATE_SOURCES)
def test_concrete_native_driver_executes_multi_field_owned_aggregate_lifecycle(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, body: str, expected_stdout: str
) -> None:
    source = MULTI_FIELD_OWNED_AGGREGATE_PREFIX + body
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    aggregate_types = [
        local.type for local in module.functions[0].locals
        if local.type.name.startswith("struct_aggregate_")
    ]
    assert aggregate_types
    assert any(len(type_.arguments) == 3 for type_ in aggregate_types)

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_named_multi_field_scalar_aggregate(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    source = MULTI_FIELD_SCALAR_AGGREGATE_SOURCE
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout

    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout) == (12, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_one_field_wrapper_around_multi_field_aggregate(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    source = NESTED_MULTI_FIELD_AGGREGATE_SOURCE
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout

    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout) == (37, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source", INVALID_MULTI_FIELD_AGGREGATE_SOURCES)
def test_concrete_native_driver_fails_closed_for_invalid_multi_field_aggregate(
    tmp_path: Path, driver: NativeReplacementDriver, source: str
) -> None:
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)
    root = _project(tmp_path, source)
    try:
        project = load_project(root / "Merit.toml")
    except ProjectError:
        project = None
    if project is not None:
        with pytest.raises((CompileError, ReplacementProjectError)):
            prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", PATH_SENSITIVE_OWNED_SOURCES)
def test_concrete_native_driver_executes_path_sensitive_owned_aggregate_control_flow(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, body: str, expected_stdout: str
) -> None:
    source = RECURSIVE_OWNED_AGGREGATE_PREFIX + body
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")

    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    first = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    assert first.stdout == second.stdout
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)

    assert (replacement.returncode, replacement.stdout) == (
        reference.returncode,
        reference.stdout,
    )
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source,expected_stdout", PATH_SENSITIVE_CAPABILITY_OWNED_SOURCES)
def test_concrete_native_driver_tracks_enclosing_owned_scope_through_capability_region(
    tmp_path: Path, driver: NativeReplacementDriver, source: str, expected_stdout: str
) -> None:
    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")

    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    first = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    assert first.stdout == second.stdout
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)

    assert (replacement.returncode, replacement.stdout) == (
        reference.returncode,
        reference.stdout,
    )
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source,reference_error", PATH_SENSITIVE_OWNED_REJECTIONS)
def test_concrete_native_driver_fails_closed_for_invalid_path_sensitive_ownership(
    tmp_path: Path, driver: NativeReplacementDriver, source: str, reference_error: str
) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True
    )
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )
    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    with pytest.raises(CompileError, match=reference_error):
        build(project, root / "build" / "reference-invalid-ownership")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_non_copy_single_i64_struct_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run([str(driver.executable)], input=SINGLE_I64_STRUCT_SOURCE, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=SINGLE_I64_STRUCT_SOURCE, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=SINGLE_I64_STRUCT_SOURCE,
        module_name="main",
        snapshot=bundle.functions[0],
        capability_names={},
    )
    instructions = [instruction for block in module.functions[0].blocks for instruction in block.instructions]
    assert [instruction.kind for instruction in instructions].count("construct") == 1
    assert [instruction.symbol for instruction in instructions if instruction.kind == "load_field"] == ["field_0"]
    drops = [instruction for instruction in instructions if instruction.kind == "drop"]
    assert len(drops) == 1
    assert drops[0].ownership == "owned"

    root = _project(tmp_path, SINGLE_I64_STRUCT_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-single-i64-struct")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement-single-i64-struct")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (7, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_owned_callable_transfer_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=OWNED_CALLABLE_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=OWNED_CALLABLE_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert len(bundle.functions) == 2
    relay = materialize_resolved_source_function_snapshot(
        source=OWNED_CALLABLE_LIFECYCLE_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={},
    ).functions[0]
    assert [(parameter.local_id, parameter.mode) for parameter in relay.parameters] == [(0, "value")]
    assert relay.return_type.name.startswith("struct_")

    root = _project(tmp_path, OWNED_CALLABLE_LIFECYCLE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-owned-callable")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 2
    artifact = build_replacement_project(project, root / "build" / "replacement-owned-callable")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, "31\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_relayed_borrowed_callable_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=BORROWED_CALLABLE_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=BORROWED_CALLABLE_LIFECYCLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert len(bundle.functions) == 4
    expose = materialize_resolved_source_function_snapshot(
        source=BORROWED_CALLABLE_LIFECYCLE_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={},
    ).functions[0]
    assert expose.return_mode == "borrowed"
    assert expose.borrowed_origin == 0
    assert [(parameter.local_id, parameter.mode) for parameter in expose.parameters] == [(0, "borrowed")]
    relay = materialize_resolved_source_function_snapshot(
        source=BORROWED_CALLABLE_LIFECYCLE_SOURCE, module_name="main",
        snapshot=bundle.functions[1], capability_names={},
    ).functions[0]
    assert (relay.return_mode, relay.borrowed_origin) == ("borrowed", 0)

    root = _project(tmp_path, BORROWED_CALLABLE_LIFECYCLE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-borrowed-callable")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 4
    artifact = build_replacement_project(project, root / "build" / "replacement-borrowed-callable")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (23, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_mutable_borrowed_callable_lifecycle(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=MUTABLE_BORROW_CALLABLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=MUTABLE_BORROW_CALLABLE_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    expose = materialize_resolved_source_function_snapshot(
        source=MUTABLE_BORROW_CALLABLE_SOURCE, module_name="main",
        snapshot=bundle.functions[0], capability_names={},
    ).functions[0]
    assert expose.return_mode == "mutable_borrow"
    assert expose.parameters[0].mode == "mutable_borrow"

    root = _project(tmp_path, MUTABLE_BORROW_CALLABLE_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-mutable-callable")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement-mutable-callable")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (23, "1\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,source,reference_error", INVALID_CALLABLE_OWNERSHIP_SOURCES)
def test_concrete_native_driver_fails_closed_for_invalid_callable_ownership(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, source: str, reference_error: str,
) -> None:
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    with pytest.raises(CompileError, match=reference_error):
        build(project, root / "build" / "reference-invalid-callable")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source", [
    INVALID_SINGLE_I64_STRUCT_FIELD_SOURCE,
    INVALID_SINGLE_I64_STRUCT_REPLACE_SOURCE,
])
def test_concrete_native_driver_fails_closed_for_unrepresented_struct_shapes(tmp_path: Path, driver: NativeReplacementDriver, source: str) -> None:
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)

    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    if source == INVALID_SINGLE_I64_STRUCT_REPLACE_SOURCE:
        with pytest.raises(CompileError, match="replace requires owned storage"):
            build(project, root / "build" / "reference-invalid-replace")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_single_i64_struct_drop_and_move(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    for case_name, source in SINGLE_I64_STRUCT_LIFECYCLE_SOURCES:
        root = _project(tmp_path / case_name, source)
        project = load_project(root / "Merit.toml")
        _, _, reference_executable = build(project, root / "build" / "reference")
        reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)

        first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
        second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
        assert first.stdout == second.stdout
        prepared = prepare_replacement_artifacts(project, driver)
        assert len(prepared.snapshot_paths) == 1
        artifact = build_replacement_project(project, root / "build" / "replacement")
        replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
        assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
        assert (replacement.returncode, replacement.stdout) == (7, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,source,expected_stdout", DESTRUCTOR_I64_STRUCT_LIFECYCLE_SOURCES)
def test_concrete_native_driver_executes_observable_i64_struct_destructor_lifecycle(
    tmp_path: Path, driver: NativeReplacementDriver, case_name: str, source: str, expected_stdout: str
) -> None:
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)

    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    assert any(local.type.name.startswith("struct_i64_destructor_") for local in module.functions[0].locals)

    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_constant_expression_destructor(tmp_path: Path, driver: NativeReplacementDriver) -> None:
    first = subprocess.run(
        [str(driver.executable)], input=CONSTANT_EXPRESSION_DESTRUCTOR_I64_STRUCT_SOURCE,
        text=True, capture_output=True, check=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=CONSTANT_EXPRESSION_DESTRUCTOR_I64_STRUCT_SOURCE,
        text=True, capture_output=True, check=True,
    )
    assert first.stdout == second.stdout
    root = _project(tmp_path, CONSTANT_EXPRESSION_DESTRUCTOR_I64_STRUCT_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, "23\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_ownership_changing_destructor_body(
    tmp_path: Path, driver: NativeReplacementDriver,
) -> None:
    root = _project(tmp_path, OWNERSHIP_CHANGING_DESTRUCTOR_SOURCE)
    project = load_project(root / "Merit.toml")
    with pytest.raises(CompileError, match="M5502"):
        Checker(project.program).check()

    first = subprocess.run(
        [str(driver.executable)], input=OWNERSHIP_CHANGING_DESTRUCTOR_SOURCE,
        text=True, capture_output=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=OWNERSHIP_CHANGING_DESTRUCTOR_SOURCE,
        text=True, capture_output=True,
    )
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()
