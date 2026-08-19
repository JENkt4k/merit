# Capabilities and contracts

Merit makes hazardous authority and function obligations explicit. Capabilities answer **what authority may this code exercise?** Contracts answer **what must be true when the function is called, and what does it promise on return?**

## Declaring capabilities

A module may declare a capability:

```merit
capability allocate;
```

Operations that may allocate can require that capability:

```merit
fn build(...) -> i32
requires_caps [allocate]
{
    // allocation-capable work
    return 0;
}
```

The requirement is part of the function's semantic interface, not a comment.

## Entering a capability scope

Authority is made visible at the call site with a capability scope:

```merit
with capability allocate {
    let buffer: Buffer = buffer_new(system_allocator(), 64);
    // allocation-requiring operations are authorized here.
}
```

A capability scope does not erase normal ownership rules. Values allocated or moved inside the scope still have ordinary destruction obligations.

## Why capabilities exist

Capabilities are intended for operations whose effects deserve explicit authority: allocation, filesystem access, and similar hazardous/environmental behavior. Generic computational code can therefore stay free of ambient authority unless it explicitly requests it.

This is different from a conventional permission check hidden deep in a library. The requirement participates in source semantics, compiler auditing, and replacement-compiler IR.

## Auditing

`merit audit` and `merit-project audit` expose capability-oriented analysis for programs/projects. The goal is that a reviewer can answer where authority is introduced and which functions require it without reconstructing an implicit global environment.

## Contracts

Functions may carry preconditions and postconditions. Contracts are semantic obligations checked consistently by the established execution paths rather than optimizer hints.

Use preconditions for requirements the caller must satisfy and postconditions for properties the function guarantees on successful return. Contract expressions should describe program invariants, not perform hidden state mutation.

Contracts are integrated with function-local identity, ownership metadata, and native MIR. This matters because a contract that observes a value must observe the same value and ordering in interpreted and compiled execution.

## Capability requirements versus contracts

These mechanisms solve different problems:

| Mechanism | Question |
| --- | --- |
| Capability | Is this code authorized to perform this class of effect? |
| Precondition | What must be true before this call is valid? |
| Postcondition | What does the function guarantee when it returns? |
| Ownership | Who is responsible for this value/resource? |

They compose. A filesystem-writing function can require filesystem authority, require a valid input path, consume an owned buffer, and guarantee a result property without collapsing those concerns into one exception mechanism.

## Fail closed

During replacement-compiler development, unsupported capability/contract constructs must fail closed rather than silently losing authority or contract semantics. The language meaning is the contract; compiler implementations must preserve it.
