# Phase 1 — Foundation: Auth, Roles, Branches, Settings

Status: **implemented domain foundation + tests**.

## Scope
- Users, roles, branch membership and permission overrides.
- Branch creation/deactivation and unique branch code.
- Branch-level authorization.
- Global/branch settings shape.
- EGP as primary currency.
- Repository boundary ready for Firebase implementation.

## Source-of-truth constraints
The Master Specification requires Firebase Authentication, Firestore and server-side functions; multi-branch support from the beginning; granular permissions; backend authorization; and owner-controlled settings. See the Master Specification for authoritative business rules.

## Deliberate boundary
The repository in this phase uses an in-memory adapter for deterministic unit tests. This is **not** the production persistence layer. The next backend step is the Firebase adapter and Firestore transaction boundary.
