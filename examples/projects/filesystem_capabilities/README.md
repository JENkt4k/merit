# Filesystem capability acceptance project

This project writes deterministic bytes to `merit-filesystem-capabilities.bin`,
reads them back, and prints the write count, read length, and byte values.

Run it from a disposable directory so the generated data file remains confined:

```bash
temporary_directory="$(mktemp -d)"
cd "$temporary_directory"
merit-project verify /path/to/merit-lang/examples/projects/filesystem_capabilities
```

Expected program output:

```text
3
3
77
82
84
```
