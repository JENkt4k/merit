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
nested body depth. Statement operands remain a subsequent parser slice.

Simple statement envelopes extend through their semicolon; control statements
extend through the opening body brace. Missing terminators produce a stable
end-of-input envelope for deterministic recovery.

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
