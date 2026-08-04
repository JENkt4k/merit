# Numeric semantics in v0.1.0-alpha.1

## Exact decimal

`decimal Name(precision, scale, rounding);` defines a fixed-scale exact decimal represented by a scaled integer. Literals exceeding the declared scale are rejected rather than silently rounded.

Implemented rounding policies are `half_even`, `half_up`, `down`, `ceiling`, and `floor`. Division uses the destination decimal policy. Checked integer and decimal addition/subtraction trap on overflow in both interpreted and native execution.

Signed integer division truncates toward zero in both execution paths. Division by zero and the `i64` minimum divided by negative one overflow case terminate deterministically rather than relying on host C behavior.

## Bounded values

`bounded Name(base, minimum, maximum);` creates a semantic integer subtype. Literal construction is checked statically. Runtime arithmetic results are range checked in both execution paths.

Primitive signed and unsigned integer operators and `checked_add`, `checked_sub`, and `checked_mul` use type-specific native helpers. Narrow overflow, unsigned underflow, multiplication overflow, bounded-domain overflow, and division failures therefore match interpreter behavior instead of relying on C wrapping or undefined behavior.

Built-in arithmetic and comparison operators accept numeric domains only. Distinct nominal numeric types do not compare implicitly, and comparison operands retain their numeric type even though the result is `i32`.
Destination typing propagates through compound literal expressions at binding, assignment, replacement, argument, and return boundaries, so runtime range behavior does not silently widen to `i64`.

## Reference verification

The first-alpha local gate compares every decimal rounding policy against Python `Decimal` with a 100-digit context and compares bounded arithmetic against unbounded Python integers. Signed ties, non-ties, multiplication, division, truncation toward zero, domain boundaries, runtime failures, and oversized compile-fail literals are covered. The same generated program output must match the independent reference in the interpreter and native C backend; generated C is also inspected for ordered operands, widened decimal intermediates, rounding-mode selection, checked primitive operations, and bounded-domain checks.

## Domain boundary rule

Lossy numeric conversions are not yet implemented. When introduced, exact-to-approximate and approximate-to-exact conversion will require explicit operations and policies. No implicit decimal/float conversion will be added.
