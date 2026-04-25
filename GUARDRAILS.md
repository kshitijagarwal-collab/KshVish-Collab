# Guardrails — Things We Must Never Do

## G-001: Never approve a case with an uncleared sanctions hit
Mistake: Approved a corporate case where UBO had an OFAC match marked "pending review"
Impact: Regulatory breach, potential criminal liability for fund manager
Rule: case.status cannot transition to APPROVED if any sanctions result has_confirmed_hit() == True
Detection: state_machine.validate_transition must call sanctions_clear_check before APPROVED

## G-002: Never skip UBO resolution for corporate cases
Mistake: Marked corporate case APPROVED with ubo_complete=False
Impact: Breach of EU 4AMLD, UK MLR 2017, FATCA/CRS
Rule: CorporateApplicant.ubo_complete must be True before any APPROVED transition
Detection: CI rule check + pre-approval compliance rule in rule_engine

## G-003: Never log PII to application logs
Mistake: Logged full name + DOB in debug statements during identity verification
Impact: GDPR Article 5 violation, data breach risk
Rule: No applicant fields (name, DOB, address, document numbers) in log statements
Detection: bandit + manual review; grep for applicant.first_name/last_name in log calls

## G-004: Never hardcode country rules in business logic
Mistake: Added if country == 'AE': require_edd = True in identity.py
Impact: Rules drift from registry; compliance gaps when countries are updated
Rule: All country-specific logic must go through config/countries/registry.py
Detection: grep for country_code string literals outside registry.py

## G-005: Never mutate a KYCCase status directly
Mistake: case.status = CaseStatus.APPROVED bypassing state_machine
Impact: Skips audit trail, compliance validation, and transition guards
Rule: Always use case.transition(new_status, actor, reason) — never assign .status directly
Detection: grep for '\.status\s*=' in case files (excluding dataclass field declarations)
