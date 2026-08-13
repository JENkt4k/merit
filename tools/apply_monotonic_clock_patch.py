from pathlib import Path

path = Path("merit/compiler.py")
source = path.read_text(encoding="utf-8")

replacements = [
    (
        "import argparse, contextlib, dataclasses, hashlib, io, json, os, re, subprocess, sys, tempfile",
        "import argparse, contextlib, dataclasses, hashlib, io, json, os, re, subprocess, sys, tempfile, time",
    ),
    (
        "    'file_write':BuiltinSig((('value','String'),('borrow','Buffer')), 'FileWriteResult', 'file_write', 'filesystem_write', ('allocate',)),\n}",
        "    'file_write':BuiltinSig((('value','String'),('borrow','Buffer')), 'FileWriteResult', 'file_write', 'filesystem_write', ('allocate',)),\n    'monotonic_ns':BuiltinSig((), 'i64', 'clock', 'monotonic_clock'),\n}",
    ),
    (
        "    'foreign_call':CapabilityPolicy('foreign_call','foreign_call','ffi-boundary','lexical'),\n}",
        "    'foreign_call':CapabilityPolicy('foreign_call','foreign_call','ffi-boundary','lexical'),\n    'clock':CapabilityPolicy('clock','monotonic_clock','time-read','lexical'),\n}",
    ),
    (
        "            if n=='system_allocator': return TypedValue('Allocator','system')\n",
        "            if n=='monotonic_ns': return TypedValue('i64',time.monotonic_ns())\n            if n=='system_allocator': return TypedValue('Allocator','system')\n",
    ),
    (
        "        o=['#include <stdint.h>','#include <stddef.h>','#include <stdio.h>','#include <stdlib.h>','#include <string.h>','#include <errno.h>','#if defined(__GNUC__) || defined(__clang__)','#define MERIT_UNUSED __attribute__((unused))','#else','#define MERIT_UNUSED','#endif','']",
        "        o=['#if !defined(_WIN32)','#ifndef _POSIX_C_SOURCE','#define _POSIX_C_SOURCE 200809L','#endif','#endif','#include <stdint.h>','#include <stddef.h>','#include <stdio.h>','#include <stdlib.h>','#include <string.h>','#include <errno.h>','#if defined(_WIN32)','#include <windows.h>','#else','#include <time.h>','#endif','#if defined(__GNUC__) || defined(__clang__)','#define MERIT_UNUSED __attribute__((unused))','#else','#define MERIT_UNUSED','#endif','']",
    ),
    (
        "              r'''static merit_Allocator merit_system_allocator(void){return (merit_Allocator){0};}''',",
        "              r'''static int64_t merit_monotonic_ns(void){\n#if defined(_WIN32)\nLARGE_INTEGER frequency,counter;\nif(!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0||!QueryPerformanceCounter(&counter))merit_fail(\"monotonic clock failed\",74);\nint64_t seconds=(int64_t)(counter.QuadPart/frequency.QuadPart);\nint64_t remainder=(int64_t)(counter.QuadPart%frequency.QuadPart);\nif(seconds>INT64_MAX/1000000000LL)merit_fail(\"monotonic clock overflow\",74);\nreturn seconds*1000000000LL+(int64_t)(((long double)remainder*1000000000.0L)/(long double)frequency.QuadPart);\n#else\nstruct timespec value;\nif(clock_gettime(CLOCK_MONOTONIC,&value)!=0)merit_fail(\"monotonic clock failed\",74);\nif(value.tv_sec<0||(uint64_t)value.tv_sec>(uint64_t)(INT64_MAX/1000000000LL))merit_fail(\"monotonic clock overflow\",74);\nreturn (int64_t)value.tv_sec*1000000000LL+(int64_t)value.tv_nsec;\n#endif\n}''',\n              r'''static merit_Allocator merit_system_allocator(void){return (merit_Allocator){0};}''',",
    ),
    (
        "            if n=='system_allocator': return 'merit_system_allocator()'\n",
        "            if n=='monotonic_ns': return 'merit_monotonic_ns()'\n            if n=='system_allocator': return 'merit_system_allocator()'\n",
    ),
]

for old, new in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one replacement anchor, got {count}: {old[:80]!r}")
    source = source.replace(old, new, 1)

path.write_text(source, encoding="utf-8")
