# Security Policy

Do not report credentials, API tokens, customer data, or other secrets in public issues.

For a suspected vulnerability, provide a minimal reproducible description privately to the repository owner rather than publishing exploit details.

Production requirements:
- real token verification
- tenant isolation
- branch authorization
- scoped idempotency
- encrypted transport
- managed database credentials stored outside Git
- audit logging
