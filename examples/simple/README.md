# Simple Merit programs

Each file is a complete, single-module program.

```bash
merit check examples/simple/hello.mrt
merit run examples/simple/hello.mrt       # interpreter
merit build examples/simple/hello.mrt     # emits C, header, native executable
merit exec examples/simple/hello.mrt      # builds and runs native executable
merit verify examples/simple/hello.mrt    # compares interpreter and native output
```

Programs:

- `hello.mrt`: prints an integer.
- `calculator.mrt`: functions and checked arithmetic.
- `countdown.mrt`: bounded values and a loop.
- `invoice.mrt`: exact decimal arithmetic and contracts.
- `account.mrt`: stable structs and mutable borrowing.
