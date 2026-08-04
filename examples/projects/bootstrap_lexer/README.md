# Bootstrap lexer

This is the first non-Python replacement-compiler slice. It tokenizes an owned
UTF-8 source buffer into typed, byte-spanned tokens using only the accepted
Merit alpha surface. Interpreter/native verification establishes the bootstrap
rule that source locations are deterministic byte offsets.

Token kinds are identifiers (`1`), numbers (`2`), strings (`3`), punctuation
(`4`), and invalid unterminated strings (`5`). Whitespace and line comments are
discarded.
