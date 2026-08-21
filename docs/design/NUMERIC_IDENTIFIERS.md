# Numeric Identifiers and Semantic Numeric Values

## Purpose

Merit must avoid unexplained semantic numeric literals while preserving explicit numeric values where those values are part of a stable representation, compatibility contract, bootstrap format, ABI, serialization format, or other intentional encoding.

The goal is not to eliminate numeric literals. The goal is to ensure that semantic meaning is represented symbolically and that each semantic numeric value has one authoritative definition.

## Core rule

Every semantic numeric value must have exactly one authoritative symbolic definition.

Raw numeric values may appear at canonical representation boundaries when the numeric value itself is part of the contract. Ordinary compiler logic should consume symbolic names rather than duplicate those raw values.

For example:

```merit
enum StatementKind : i32 {
    Let = 20,
    Var = 21,
    Return = 22,
    Print = 23,
}
```

Implementation code should use:

```merit
if kind == StatementKind.Print {
    ...
}
```

rather than:

```merit
if kind == 23 {
    ...
}
```

A compatibility test may intentionally verify the representation:

```merit
assert StatementKind.Print == 23;
```

because the numeric value itself is what the test is asserting.

---

## Classification

Before introducing or replacing a numeric literal, classify its role.

### 1. Semantic discriminants

Examples:

- token kinds
- statement kinds
- expression kinds
- MIR instruction kinds
- MIR terminator kinds
- ownership kinds
- capability/effect kinds
- source/provenance kinds
- policy IDs
- serialized variant tags

Preferred representation:

- typed enum when supported and appropriate
- otherwise a named domain-specific constant
- explicit numeric discriminants when stable representation is required

Example:

```merit
enum StatementOperandKind : i32 {
    BindingName = 1,
    DeclaredType = 2,
    Expression = 3,
    CapabilityName = 4,
}
```

Semantic implementation code must reference the symbolic member rather than the numeric discriminant.

Do not use numeric ranges when the intended meaning is a set of semantic variants unless the range itself is an explicitly documented invariant.

Avoid:

```merit
if kind >= 25 {
    if kind <= 28 {
        ...
    }
}
```

Prefer semantic membership or typed matching:

```merit
match kind {
    StatementKind.If |
    StatementKind.While |
    StatementKind.Match |
    StatementKind.With => {
        ...
    }
}
```

---

### 2. Error and status codes

Examples:

```merit
return 30;
return 40;
```

when those values represent specific failure conditions.

Preferred representation:

1. typed error/result representation where supported and appropriate
2. named error/status enum
3. named status constants as a temporary bootstrap representation

Example:

```merit
enum FunctionAssemblyStatus : i32 {
    Ok = 0,
    InvalidBindingCount = 1,
    InvalidLocalCount = 2,
    EmptyBody = 3,
    InvalidContractMir = 4,
    UnsupportedContractKind = 30,
    UnexpectedBodyInstruction = 40,
}
```

Callers should compare against symbolic values rather than raw integers.

Do not renumber established status values merely to make them contiguous.

---

### 3. Character and byte values

Examples:

- `40` for `(`
- `41` for `)`
- `59` for `;`
- `61` for `=`
- `123` for `{`

Preferred representation:

1. character or byte literal if Merit supports an appropriate literal form
2. otherwise a named character/byte constant when the meaning is not obvious at the point of use

Prefer:

```merit
if token_byte == '(' {
    ...
}
```

over:

```merit
if token_byte == 40 {
    ...
}
```

If character literals are unavailable at the relevant bootstrap stage:

```merit
const ASCII_OPEN_PAREN: i64 = 40;
```

The numeric encoding may remain in the canonical character/encoding definition.

---

### 4. Encoded or packed constants

Examples:

- packed keyword values
- hashes
- bit masks
- encoded identifiers
- compact bootstrap representations

Large encoded values must not appear repeatedly in semantic logic without explanation.

Avoid:

```merit
if packed == 500068610672 {
    ...
}
```

Prefer:

```merit
const PACKED_KEYWORD_PRINT: i64 = 500068610672;

if packed == PACKED_KEYWORD_PRINT {
    ...
}
```

Better still, encapsulate the encoding behind a symbolic operation when practical:

```merit
if packed_keyword_matches(packed, Keyword.Print) {
    ...
}
```

The encoding algorithm and canonical encoded value should live at the representation boundary rather than leaking into unrelated consumers.

---

### 5. Protocol, ABI, serialization, and compatibility values

These values may intentionally remain numeric at their canonical definition site.

Examples:

```merit
enum MirInstructionKind : i32 {
    Add = 4,
    Print = 23,
}
```

or explicit format/version definitions:

```merit
const MIR_FORMAT_VERSION: i32 = 3;
```

Rules:

- preserve established values unless a versioned format change explicitly requires renumbering
- do not infer a new value from enum order if representation stability matters
- do not silently renumber values to make them contiguous
- implementation code should use the symbolic definition
- tests should lock down externally significant numeric mappings

A raw numeric literal is acceptable in a compatibility test when the test is intentionally verifying the wire/ABI/serialized representation.

---

### 6. Sentinels

Examples:

- `-1` meaning not found
- `-1` meaning no clause
- `0` meaning no object or no identifier where zero is otherwise not valid

Preferred representation:

1. typed absence such as `Option<T>` where practical
2. explicit domain-specific sentinel constant when bootstrap constraints require numeric representation

Example:

```merit
const NO_CLAUSE_ORDINAL: i64 = -1;
```

Do not automatically replace every `-1`. First determine whether it represents:

- legitimate arithmetic
- a range boundary
- a sentinel
- an externally defined representation

---

### 7. Mathematical and structural literals

Ordinary numeric literals are allowed when their meaning is inherent in the operation.

Examples:

```merit
index = checked_add(index, 1);
if count == 0 { ... }
if value < 0 { ... }
let next = checked_add(current, 1);
```

These are not magic numbers merely because they are numeric.

Do not create unnecessary names such as:

```merit
const ONE: i64 = 1;
const ZERO: i64 = 0;
```

unless the value has an actual domain-specific meaning.

---

## Canonical placement

A symbolic numeric definition should live with the domain that owns its meaning.

Examples:

- `StatementKind` with statement representation
- `TokenKind` with token representation
- MIR kinds with canonical MIR definitions
- ownership kinds with ownership representation
- assembly errors with assembly error/status definitions
- character encodings with lexer/encoding infrastructure

Do not create a repository-wide bag of unrelated constants such as:

```text
constants.mrt
MAGIC_1
MAGIC_2
MIR_4
STMT_23
ERROR_40
```

Names and placement should preserve the semantic domain.

---

## Bootstrap and Python parity

Merit currently has native Merit bootstrap code and Python bootstrap/parity infrastructure that may represent the same semantic domains.

The same logical semantic value must not be independently invented in both implementations.

For each shared numeric domain:

- identify one canonical logical mapping
- use explicit symbolic names in both implementations
- preserve required numeric discriminants
- add parity or compatibility tests that prove both implementations agree
- avoid duplicating raw numeric literals in semantic code

Generation from a single schema may be introduced later if it materially reduces maintenance cost, but it is not required merely to satisfy this policy.

The minimum invariant is:

```text
one canonical logical mapping
+ symbolic use in semantic code
+ explicit parity/compatibility tests
```

---

## Tests

Tests should distinguish semantic behavior from representation compatibility.

Semantic tests should prefer symbolic values:

```python
assert record.kind == StatementKind.PRINT
```

Representation tests may intentionally assert raw values:

```python
assert int(StatementKind.PRINT) == 23
```

Use raw numeric assertions only when the numeric representation itself is part of what the test is intended to protect.

---

## Existing code

This document defines the preferred architecture for new and modified code.

It does not, by itself, authorize repository-wide cleanup of existing numeric literals.

Existing occurrences should be migrated through deliberate cleanup work according to the current project/milestone scope.

When modifying an existing area for unrelated work:

- do not introduce new unexplained semantic numeric literals
- use an existing symbolic definition if one exists
- if a new semantic value is required, add the appropriate symbolic definition
- do not opportunistically refactor nearby unrelated numeric debt unless the current task explicitly includes that cleanup

---

## Decision procedure

When adding or modifying a numeric literal, ask:

1. Does this number encode semantic identity?
   - Use an enum or named domain constant.

2. Is this an error/status code?
   - Use a typed error/status representation.

3. Is this a character or byte encoding?
   - Prefer a character/byte literal or named encoding constant.

4. Is this a packed/hash/encoded representation?
   - Encapsulate and name it at the encoding boundary.

5. Is this an ABI/protocol/serialization value?
   - Keep the explicit value at the canonical definition site and use its symbolic name elsewhere.

6. Is this a sentinel?
   - Prefer typed absence or a named sentinel.

7. Is this ordinary arithmetic, indexing, counting, or comparison?
   - Keep the literal if its meaning is self-evident.

If the classification is unclear, do not invent a new raw semantic number. Determine the owning domain first.
