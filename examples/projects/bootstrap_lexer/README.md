# Bootstrap lexer

This is the first non-Python replacement-compiler slice. It tokenizes an owned
UTF-8 source buffer into typed, byte-spanned tokens using only the accepted
Merit alpha surface. Interpreter/native verification establishes the bootstrap
rule that source locations are deterministic byte offsets.

Token kinds are identifiers/keywords (`1`), exact numerics (`2`), strings (`3`), punctuation
(`4`), and invalid unterminated strings (`5`). Whitespace and line comments are
discarded. The accepted two-byte punctuation sequences are emitted as maximal
spans: `->`, `=>`, `==`, `!=`, `>=`, `<=`, and `::`.

The project also produces the first typed syntax boundary: byte-spanned module,
function, struct, enum, capability, numeric-type, trait, impl, and destructor
declaration records. Brace-depth tracking excludes nested impl methods from the
top-level declaration index.

Typed parse diagnostics currently cover missing declaration names, unexpected
closing braces, unclosed bodies, and invalid unterminated strings with stable
byte locations.

The syntax index recognizes `let`, `var`, `return`, `print`, `drop`, `if`,
`while`, `match`, `with capability`, and `replace` statement introducers at any
nested body depth. Typed operand records now sit behind those deterministic
envelopes.

Simple statement envelopes extend through their semicolon; control statements
extend through the opening body brace. Missing terminators produce a stable
end-of-input envelope for deterministic recovery.

## Typed statement operands

`bootstrap-statement-v1` adds flat `StatementRecord` and `StatementOperand`
streams without embedding recursive expression ownership into statement
storage. Each statement record points at a contiguous operand range, so the
physical representation remains deterministic and stage-0-friendly.

Operands distinguish binding names, declared types, expression sources, and
capability names. The accepted statement families map to operands in language
order: `let`/`var` bind name/type/initializer, `return`/`print`/`drop` carry one
expression, `if`/`while`/`match` carry their controlling expression, `with
capability` carries its capability name, and `replace` carries target then
replacement expressions.

Delimiter discovery tracks nested parentheses, brackets, and braces. In
particular, commas inside nested calls or indexing forms do not split a
`replace` operand. Differential tests compare the complete record and operand
streams against an independent Python token-level oracle in both the Merit
interpreter and generated native executable.

Expression operands remain source boundaries at this contract layer; the
`bootstrap-expression-span-v1` adapter described below connects kind-3 operands
to the versioned expression/AST pipeline without changing statement storage.

## Typed function clause operands

`bootstrap-clause-v1` adds the same flat, deterministic operand boundary for
function-level `effects`, `requires_caps`, `requires`, and `ensures` clauses.
`ClauseRecord` values point into one shared `ClauseOperand` stream, preserving
source order without introducing semantic ownership or recursive expression
storage.

Effect-list items are kind-1 operands, required-capability names are kind-2
operands, and pre/postcondition expression sources are kind-3 operands. Empty
lists remain valid zero-operand records. Contract expression termination tracks
parentheses, brackets, and braces, so nested calls and direct constructors do
not truncate the outer contract at an internal delimiter.

Clause discovery follows the existing syntax-index brace-depth rule: only
introducers at depth zero are indexed, while clause-like identifiers inside
function bodies are ignored. Differential tests compare complete records and
operand streams against an independent Python token oracle through both the
Merit interpreter and generated native C executable.

This checkpoint defines source roles and boundaries only. Effect validation,
capability authorization, boolean contract typing, `old()` rules, and contract
execution remain semantic responsibilities of the later HIR/checking stages.

## Expression span integration

`bootstrap-expression-span-v1` composes the statement/clause source-boundary
contracts with the existing expression parser and native AST lowerer. The
adapter filters the complete source token stream to tokens fully contained in a
kind-3 operand span, preserving absolute byte offsets, and then delegates to
`parse_expression_tokens`.

The filtered-token boundary prevents tokens belonging to the enclosing syntax
from changing expression meaning. For example, the body brace following
`if value != limit {` is outside the condition span and cannot be interpreted
as a direct-constructor postfix on `limit`.

`validate_expression_span_ast` and `lower_expression_span_ast` delegate to the
existing `bootstrap-ast-v1` validation and lowering functions. No second
expression grammar or AST semantics are introduced. Differential integration
tests obtain spans from the independent statement/clause token oracles, parse
the isolated source with the independent expression oracle, restore absolute
source offsets, and compare complete expression and flat AST streams through
both Merit interpretation and generated native execution.

## Native AST boundary

`bootstrap-expression-v1` expression records now have a Merit-native lowering
boundary for `bootstrap-ast-v1`. `AstNodeRecord` is deterministic postorder
storage using the existing numeric expression kinds plus source spans and child
indices. Explicit parser group nodes are removed from semantic AST meaning.
Their source spans are retained as grouping provenance through `group_start`,
`group_length`, and `group_parent` links, allowing arbitrarily nested grouping
without recursive owned stage-0 storage.

`validate_expression_ast_records` rejects malformed postorder streams before
AST lowering: negative spans, unknown kinds, malformed groups, atom children,
forward required/optional child references, and empty streams have stable
contract codes. These are bootstrap contract failures rather than source parse
diagnostics.

`lower_expression_ast_records` requires the `allocate` capability and emits one
flat physical record for every parser record. Differential tests reconstruct an
independent flat oracle from the Python reference parser and compare both Merit
interpreter and generated-native output across the manifest expression corpus,
including nested grouping provenance.

The same tests independently reconstruct the canonical recursive
`bootstrap-ast-v1` tree from those native flat records and compare it with the
Python `ast_contract` oracle, including stable compact JSON serialization. The
native checkpoint therefore proves both the stage-0 storage representation and
the versioned external AST meaning; later HIR work can consume the canonical
meaning without depending on the physical flat layout.
