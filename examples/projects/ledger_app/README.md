# Multi-module ledger application

```bash
merit-project graph .
merit-project check .
merit-project verify .
merit-project run .
```

Expected output:

```text
1100.25
2
10
1001
1100.25
```

The application uses five source modules, exact `USD`, bounded account IDs, typed ledger errors, explicit allocation, and capability-gated audit-file output. Its public stable `Account` plus `deposit` and `account_balance` functions are verified from a foreign C-compatible caller.
