# Borrowed views acceptance project

This project verifies public cross-module shared and mutable borrowed returns, including functions that relay a validated borrow through another function. The shared view supports ephemeral field access, while the mutable view acts as a field lvalue without transferring ownership.

Run `merit-project verify examples/projects/borrowed_views` from the repository root.
