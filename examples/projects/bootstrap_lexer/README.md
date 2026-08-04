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
