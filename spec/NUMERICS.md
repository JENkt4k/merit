# Numeric semantics in alpha.3

## Exact decimal

`decimal Name(precision, scale, rounding);` defines a fixed-scale exact decimal represented by a scaled integer. Literals exceeding the declared scale are rejected rather than silently rounded.

Implemented rounding policies are `half_even`, `half_up`, `down`, `ceiling`, and `floor`. Division uses the destination decimal policy. Checked integer and decimal addition/subtraction trap on overflow in both interpreted and native execution.

## Bounded values

`bounded Name(base, minimum, maximum);` creates a semantic integer subtype. Literal construction is checked statically. Runtime arithmetic results are range checked by the interpreter; complete native runtime range checks remain a tracked limitation.

## Domain boundary rule

Lossy numeric conversions are not yet implemented. When introduced, exact-to-approximate and approximate-to-exact conversion will require explicit operations and policies. No implicit decimal/float conversion will be added.
