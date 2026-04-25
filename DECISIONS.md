# Decision Record

## DR-001: Python as primary language
Chose Python / Over Java or Go / Why: fastest iteration for compliance-heavy domain logic,
rich ecosystem (Pydantic, FastAPI), team familiarity / Constraint: performance-critical paths
may need async or Go microservices in Phase 6.

## DR-002: Modular monorepo, not microservices at start
Chose monorepo / Over microservices / Why: compliance domains are tightly coupled (UBO feeds
risk scoring feeds AML); splitting prematurely adds network failure modes to regulatory workflows /
Constraint: re-evaluate at 10+ engineers or if screening latency > 2s SLA is breached.

## DR-003: Country rules as code + YAML, not database
Chose registry.py + YAML / Over DB-driven rules / Why: rules change at compliance review cycles
(quarterly), not at runtime; code review for rule changes is a compliance control in itself /
Constraint: hot-patching country rules requires a deployment.

## DR-004: Sanctions/PEP providers as integration stubs
Chose stub pattern with clear integration points / Over hardcoding a single provider /
Why: provider choice varies by jurisdiction and fund manager; stubs let us test without
live credentials / Constraint: must swap stubs before any production deployment.

## DR-005: UBO threshold at 25%
Chose 25% / Over 10% or 50% / Why: FATF recommendation, adopted by EU 4AMLD, UK MLR 2017,
SEBI / Constraint: some jurisdictions (e.g. US FinCEN) use 25% but may require lower at
fund manager discretion — check fund's compliance policy.

## DR-006: Epic 5 started ahead of Epic 3 & 4 completion (2026-04-25)
Chose run Epic 5 in parallel / Over wait for Epic 3 (DB) and Epic 4 (Auth) / Why: explicit
user override after initial "wait" directive; Epic 5 adapters are pure provider integrations
that don't depend on persistence or auth — they expose Provider Protocols consumed by services
that will be wired up once Epic 3/4 land / Constraint: no end-to-end screening flow can persist
results until Epic 3 ORM + repositories ship; adapters must remain side-effect-free at
import time so they don't break test runs without env credentials.
