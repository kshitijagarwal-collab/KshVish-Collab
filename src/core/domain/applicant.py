from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class ApplicantType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    CORPORATE = "CORPORATE"
    INSTITUTIONAL = "INSTITUTIONAL"


class InvestorClass(str, Enum):
    RETAIL = "RETAIL"
    PROFESSIONAL = "PROFESSIONAL"
    ELIGIBLE_COUNTERPARTY = "ELIGIBLE_COUNTERPARTY"
    INSTITUTIONAL = "INSTITUTIONAL"


@dataclass
class Address:
    line1: str
    city: str
    country_code: str
    postal_code: str
    line2: Optional[str] = None
    state: Optional[str] = None


@dataclass
class IndividualApplicant:
    first_name: str
    last_name: str
    date_of_birth: date
    nationality: str
    country_of_residence: str
    email: str
    id: UUID = field(default_factory=uuid4)
    middle_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None
    investor_class: Optional[InvestorClass] = None
    is_pep: bool = False
    is_sanctioned: bool = False
    tax_id: Optional[str] = None
    source_of_funds: Optional[str] = None

    @property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)

    def is_high_risk(self) -> bool:
        return self.is_pep or self.is_sanctioned


@dataclass
class CorporateApplicant:
    legal_name: str
    registration_number: str
    country_of_incorporation: str
    registered_address: Address
    id: UUID = field(default_factory=uuid4)
    trading_name: Optional[str] = None
    incorporation_date: Optional[date] = None
    business_type: Optional[str] = None
    regulated: bool = False
    regulator: Optional[str] = None
    lei_code: Optional[str] = None
    tax_id: Optional[str] = None
    is_sanctioned: bool = False
    ubo_complete: bool = False

    def is_high_risk(self) -> bool:
        return self.is_sanctioned or not self.ubo_complete
