# KYC Onboarding Platform — Project Brain

<project>
Global KYC onboarding for fund management companies. Covers individual investors and
corporate/institutional entities across all jurisdictions. Modular, compliance-first,
production-grade.
</project>

<before_any_task>
1. Read DECISIONS.md — all prior architecture choices are final unless explicitly revisited.
2. Read GUARDRAILS.md — compliance invariants must never be broken.
3. Identify the module being touched. Match its patterns exactly.
4. Never touch more than one module per branch/PR.
</before_any_task>

<mandate>
- Every file must stay under 600 lines. If approaching the limit, split immediately.
- Every module is a single-responsibility unit. No cross-domain imports except through core/domain.
- core/domain has zero infrastructure or framework dependencies.
- All compliance logic lives in src/compliance/ — never inline in API handlers or domain models.
</mandate>

<architecture>
src/
  core/domain/       — Pure domain models. No DB, no HTTP, no framework.
  core/workflow/     — KYC state machine. Transition rules only.
  config/countries/  — Per-country rule registry. YAML-driven.
  kyc/individual/    — Identity, address, PEP, sanctions, risk scoring, suitability.
  kyc/corporate/     — Entity verification, UBO, signatories, group structure.
  compliance/        — AML, rule engine, GDPR, reporting, re-KYC.
  fund/              — Eligibility, subscription gates, jurisdiction matrix.
  api/               — REST handlers. No business logic — delegates to services.
  infra/             — Storage, audit, notifications. Framework code lives here.
  portal/            — UI entry points only.
</architecture>

<compliance_invariants>
- Every KYC case transition must be logged to the audit trail.
- Sanctions screening is mandatory before any case reaches APPROVED.
- UBO resolution is mandatory for all corporate cases before APPROVED.
- PEP-confirmed cases require Enhanced Due Diligence before approval.
- High-risk jurisdiction cases require manual reviewer sign-off.
- No document may be marked VERIFIED without a reviewer_id recorded.
</compliance_invariants>

<testing>
- Every screening function must have a test with: clean pass, confirmed hit, false positive flow.
- State machine tests must cover every valid and every invalid transition.
- Country rule tests must cover: standard, high-risk, and enhanced-DD countries.
</testing>

<git>
- Branch naming: feature/<short-description> or fix/<short-description>
- Never commit directly to main. Branch protection is enforced.
- Every PR must pass CI (lint + type check + tests + 600-line check).
- Conventional commits: feat: fix: refactor: docs: test: chore:
</git>

<layered_config>
Read ENGINEERING_BRAIN.md in ~/code/engineering-brain/ for global principles.
This CLAUDE.md extends and overrides globals for this project only.
</layered_config>
