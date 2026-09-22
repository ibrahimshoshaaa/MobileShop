# Firebase security deployment contract

1. Verify Firebase ID tokens with the Admin SDK on the server.
2. Build `CommandContext` only from verified claims/server-side user data.
3. Never accept `permissions` or `branch_ids` from the client payload.
4. Clients call commands; they do not directly mutate sales, payments, ledger,
   stock movements, wallets, returns, expenses, installments, or audit logs.
5. Deploy Firestore rules and indexes to staging first and test with the
   Firebase Emulator Suite before production.
6. Keep development/staging/production projects separate.
