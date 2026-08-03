# Numeric semantics in alpha.3

## Exact decimal

`decimal Name(precision, scale, rounding);` defines a fixed-scale exact decimal represented by a scaled integer. Literals exceeding the declared scale are rejected rather than silently rounded.

Implemented rounding policies are `half_even`, `half_up`, `down`, `ceiling`, and `floor`. Division uses the destination decimal policy. Checked integer and decimal addition/subtraction trap on overflow in both interpreted and native execution.

Signed integer division truncates toward zero in both execution paths. Division by zero and the `i64` minimum divided by negative one overflow case terminate deterministically rather than relying on host C behavior.

## Bounded values

`bounded Name(base, minimum, maximum);` creates a semantic integer subtype. Literal construction is checked statically. Runtime arithmetic results are range checked in both execution paths.

Primitive signed and unsigned integer operators and `checked_add`, `checked_sub`, and `checked_mul` use type-specific native helpers. Narrow overflow, unsigned underflow, multiplication overflow, bounded-domain overflow, and division failures therefore match interpreter behavior instead of relying on C wrapping or undefined behavior.

Built-in arithmetic and comparison operators accept numeric domains only. Distinct nominal numeric types do not compare implicitly, and comparison operands retain their numeric type even though the result is `i32`.

## Domain boundary rule

Lossy numeric conversions are not yet implemented. When introduced, exact-to-approximate and approximate-to-exact conversion will require explicit operations and policies. No implicit decimal/float conversion will be added.
