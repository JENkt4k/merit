# Gate Output Contract

`scripts/ci.sh` emits a small environment preamble before the authoritative test gate:

```text
== Merit clean-environment gate ==
repository: <absolute checkout path>
Python <version>
pip <version and location>
<c compiler identity>
```

It then runs `python -m pip check` followed by `scripts/test.sh`.

The environment preamble is diagnostic information, not a stable language or compiler interface. Test names, accepted/rejected corpus behavior, interpreter/native parity, and specification-defined diagnostics remain the meaningful evidence.

The script exits nonzero when:

- Python package dependencies are inconsistent
- no C compiler is available as `cc`
- pytest fails
- generated C does not compile
- an acceptance project's interpreter/native outputs disagree
- an acceptance command reports failure

The hosted workflow should expose this output directly rather than wrapping or translating failures into a second reporting system.
