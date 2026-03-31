"""ACORD 125/126 XML parser for OpenInsure.

Extracts commercial insurance application data from ACORD 125 (Commercial
Insurance Application) and ACORD 126 (Commercial General Liability) forms
and maps them to the OpenInsure submission model.

ACORD XML reference:
  - ACORD 125: Commercial Insurance Application
    Root element: <ACORD> → <InsuranceSvcRq> → <CommlPkgPolicyQuoteInqRq>
  - ACORD 126: Commercial General Liability Section
    Additional section under the same package request

The parser handles both full ACORD XML and simplified subsets.
Namespace-aware: supports ``urn:ACORD`` namespace or no namespace.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# Namespace patterns for ACORD XML
_ACORD_NS = {"ac": "urn:ACORD"}
_NS_PATTERN = re.compile(r"\{[^}]+\}")


def _strip_ns(tag: str) -> str:
    """Remove namespace prefix from an XML tag."""
    return _NS_PATTERN.sub("", tag)


def _find(elem: ET.Element, path: str) -> ET.Element | None:
    """Find a child element, trying both namespaced and plain paths."""
    # Try without namespace first
    result = elem.find(path)
    if result is not None:
        return result
    # Try with ACORD namespace
    ns_path = "/".join(f"ac:{p}" if p and not p.startswith("@") else p for p in path.split("/"))
    return elem.find(ns_path, _ACORD_NS)


def _text(elem: ET.Element, path: str, default: str = "") -> str:
    """Get text content of a child element."""
    child = _find(elem, path)
    return (child.text or "").strip() if child is not None else default


def _float_val(elem: ET.Element, path: str, default: float = 0.0) -> float:
    """Get float value from a child element."""
    text = _text(elem, path)
    if not text:
        return default
    try:
        return float(re.sub(r"[,$]", "", text))
    except ValueError:
        return default


def _int_val(elem: ET.Element, path: str, default: int = 0) -> int:
    """Get integer value from a child element."""
    text = _text(elem, path)
    if not text:
        return default
    try:
        return int(re.sub(r"[,]", "", text))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


class ACORDParseResult:
    """Result of parsing an ACORD 125/126 form."""

    def __init__(self) -> None:
        self.applicant_name: str = ""
        self.applicant_email: str = ""
        self.applicant_phone: str = ""
        self.applicant_website: str = ""
        self.dba_name: str = ""
        self.tax_id: str = ""
        self.sic_code: str = ""
        self.naics_code: str = ""
        self.industry: str = ""
        self.address: dict[str, str] = {}
        self.annual_revenue: float = 0.0
        self.employee_count: int = 0
        self.year_established: int = 0
        self.effective_date: str = ""
        self.expiration_date: str = ""
        self.line_of_business: str = "cyber"
        self.requested_limit: float = 0.0
        self.requested_deductible: float = 0.0
        self.prior_insurance: dict[str, Any] = {}
        self.loss_history: list[dict[str, Any]] = []
        self.coverages_requested: list[str] = []
        self.additional_data: dict[str, Any] = {}
        self.parse_warnings: list[str] = []

    def to_submission(self) -> dict[str, Any]:
        """Convert to OpenInsure submission creation payload."""
        risk_data: dict[str, Any] = {}
        if self.annual_revenue:
            risk_data["annual_revenue"] = self.annual_revenue
        if self.employee_count:
            risk_data["employee_count"] = self.employee_count
        if self.sic_code:
            risk_data["sic_code"] = self.sic_code
        if self.naics_code:
            risk_data["naics_code"] = self.naics_code
        if self.industry:
            risk_data["industry"] = self.industry
        if self.year_established:
            risk_data["year_established"] = self.year_established
        if self.loss_history:
            risk_data["loss_history"] = self.loss_history
        if self.prior_insurance:
            risk_data["prior_insurance"] = self.prior_insurance

        metadata: dict[str, Any] = {
            "source": "acord_xml",
            "acord_form": "125/126",
        }
        if self.address:
            metadata["address"] = self.address
        if self.dba_name:
            metadata["dba_name"] = self.dba_name
        if self.tax_id:
            metadata["tax_id"] = self.tax_id
        if self.applicant_website:
            metadata["website"] = self.applicant_website
        if self.coverages_requested:
            metadata["coverages_requested"] = self.coverages_requested
        if self.parse_warnings:
            metadata["parse_warnings"] = self.parse_warnings
        if self.additional_data:
            metadata.update(self.additional_data)

        cyber_risk_data: dict[str, Any] = {}
        if self.requested_limit:
            cyber_risk_data["requested_limit"] = self.requested_limit
        if self.requested_deductible:
            cyber_risk_data["requested_deductible"] = self.requested_deductible

        return {
            "applicant_name": self.applicant_name or "Unknown Applicant",
            "applicant_email": self.applicant_email or None,
            "channel": "api",
            "line_of_business": self.line_of_business,
            "risk_data": risk_data,
            "cyber_risk_data": cyber_risk_data,
            "metadata": metadata,
        }


def parse_acord_xml(xml_content: str | bytes) -> ACORDParseResult:
    """Parse ACORD 125/126 XML and extract submission data.

    Handles both namespaced and non-namespaced ACORD XML.  Extracts:
    - Applicant info (name, address, contact, tax ID)
    - Business profile (revenue, employees, SIC/NAICS, year established)
    - Policy details (effective/expiration dates, limits, deductibles)
    - Loss history
    - Prior insurance
    - Requested coverages

    Parameters
    ----------
    xml_content : str or bytes
        Raw ACORD XML content.

    Returns
    -------
    ACORDParseResult
        Parsed data with a ``to_submission()`` method for pipeline integration.
    """
    result = ACORDParseResult()

    try:
        root = ET.fromstring(  # noqa: S314  # nosec B314
            xml_content if isinstance(xml_content, str) else xml_content.decode("utf-8")
        )
    except ET.ParseError as e:
        result.parse_warnings.append(f"XML parse error: {e}")
        return result

    # Navigate to the main request element
    # ACORD 125: ACORD → InsuranceSvcRq → CommlPkgPolicyQuoteInqRq
    svc_rq = _find(root, "InsuranceSvcRq")
    if svc_rq is None:
        # Try flat structure
        svc_rq = root

    pkg_rq = _find(svc_rq, "CommlPkgPolicyQuoteInqRq") if svc_rq is not None else None
    if pkg_rq is None:
        pkg_rq = _find(svc_rq, "PersAutoPolicyQuoteInqRq")
    if pkg_rq is None:
        pkg_rq = svc_rq if svc_rq is not None else root

    # --- Applicant / Insured Info ---
    _parse_applicant(pkg_rq, result)

    # --- Policy-level info ---
    _parse_policy(pkg_rq, result)

    # --- Coverages ---
    _parse_coverages(pkg_rq, result)

    # --- Loss history ---
    _parse_loss_history(pkg_rq, result)

    # --- Prior insurance ---
    _parse_prior_insurance(pkg_rq, result)

    logger.info(  # type: ignore[call-arg]
        "acord.parsed",
        applicant=result.applicant_name,
        lob=result.line_of_business,
        warnings=len(result.parse_warnings),
    )
    return result


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_applicant(pkg: ET.Element, result: ACORDParseResult) -> None:
    """Extract applicant/insured information."""
    # Try multiple possible parent elements
    for parent_tag in ("CommlPolicy", "InsuredOrPrincipal", "GeneralPartyInfo", ""):
        parent = _find(pkg, parent_tag) if parent_tag else pkg
        if parent is None:
            continue

        # Name info
        for name_tag in ("NameInfo", "CommlName", "PersonName"):
            name_elem = _find(parent, name_tag)
            if name_elem is not None:
                commercial = _text(name_elem, "CommlName/CommercialName")
                surname = _text(name_elem, "PersonName/Surname")
                given = _text(name_elem, "PersonName/GivenName")
                org = _text(name_elem, "CommercialName")
                if not org:
                    org = _text(name_elem, "LegalName")

                if commercial:
                    result.applicant_name = commercial
                elif org:
                    result.applicant_name = org
                elif surname:
                    result.applicant_name = f"{given} {surname}".strip()

                result.dba_name = _text(name_elem, "DBAName") or _text(name_elem, "TradeName")
                result.tax_id = _text(name_elem, "TaxIdentity/TaxId") or _text(name_elem, "TaxId")

        # Simple applicant name fallback
        if not result.applicant_name:
            result.applicant_name = (
                _text(parent, "CommercialName")
                or _text(parent, "InsuredName")
                or _text(parent, "ApplicantName")
                or _text(parent, "Name")
            )

        # Address
        addr = _find(parent, "Addr")
        if addr is not None:
            result.address = {
                "street": _text(addr, "Addr1"),
                "street2": _text(addr, "Addr2"),
                "city": _text(addr, "City"),
                "state": _text(addr, "StateProvCd"),
                "zip": _text(addr, "PostalCode"),
                "country": _text(addr, "CountryCd", "US"),
            }

        # Contact info
        for comm_tag in ("Communications", "ContactInfo"):
            comm = _find(parent, comm_tag)
            if comm is not None:
                result.applicant_email = (
                    _text(comm, "EmailInfo/EmailAddr") or _text(comm, "Email") or _text(comm, "EmailAddr")
                )
                result.applicant_phone = _text(comm, "PhoneInfo/PhoneNumber") or _text(comm, "Phone")
                result.applicant_website = _text(comm, "WebsiteURL") or _text(comm, "Website")

        if result.applicant_name:
            break

    # Business info
    for biz_tag in ("CommlSubLocation", "BusinessInfo", "RiskInfo"):
        biz = _find(pkg, biz_tag)
        if biz is not None:
            result.annual_revenue = _float_val(biz, "AnnualRevenue") or _float_val(biz, "Revenue")
            result.employee_count = _int_val(biz, "NumEmployees") or _int_val(biz, "EmployeeCount")
            result.sic_code = _text(biz, "SICCd") or _text(biz, "SIC")
            result.naics_code = _text(biz, "NAICSCd") or _text(biz, "NAICS")
            result.industry = _text(biz, "IndustryDesc") or _text(biz, "Industry")
            yr = _text(biz, "YearEstablished") or _text(biz, "BusinessStartDt")
            if yr:
                with contextlib.suppress(ValueError):
                    result.year_established = int(yr[:4])
            if result.annual_revenue or result.employee_count:
                break

    # Also try top-level business fields
    if not result.annual_revenue:
        result.annual_revenue = _float_val(pkg, "AnnualRevenue") or _float_val(pkg, "Revenue")
    if not result.employee_count:
        result.employee_count = _int_val(pkg, "NumEmployees") or _int_val(pkg, "EmployeeCount")
    if not result.sic_code:
        result.sic_code = _text(pkg, "SICCd")
    if not result.naics_code:
        result.naics_code = _text(pkg, "NAICSCd")


def _parse_policy(pkg: ET.Element, result: ACORDParseResult) -> None:
    """Extract policy-level details."""
    pol_elem = _find(pkg, "CommlPolicy")
    if pol_elem is None:
        pol_elem = _find(pkg, "Policy")
    pol = pol_elem if pol_elem is not None else pkg

    # Dates
    eff = _text(pol, "ContractTerm/EffectiveDt") or _text(pol, "EffectiveDt") or _text(pol, "EffectiveDate")
    exp = _text(pol, "ContractTerm/ExpirationDt") or _text(pol, "ExpirationDt") or _text(pol, "ExpirationDate")
    result.effective_date = eff
    result.expiration_date = exp

    # LOB detection
    lob_code = (_text(pol, "LOBCd") or _text(pol, "LineOfBusinessCd") or _text(pkg, "LOBCd")).lower()
    if lob_code in ("cyber", "cyb", "cybr"):
        result.line_of_business = "cyber"
    elif lob_code in ("techeo", "tech_eo", "eao"):
        result.line_of_business = "tech_eo"
    elif lob_code in ("mpl", "profliab"):
        result.line_of_business = "mpl"
    elif lob_code in ("property", "prop", "commprop", "commercial_property", "cp"):
        result.line_of_business = "commercial_property"
    elif lob_code:
        result.line_of_business = "cyber"
        result.parse_warnings.append(f"Unknown LOB code '{lob_code}', defaulting to cyber")

    # Limits / deductibles
    result.requested_limit = (
        _float_val(pol, "LiabilityInfo/GeneralLiabilityClassification/Limit/FormatCurrencyAmt/Amt")
        or _float_val(pol, "Limit/FormatCurrencyAmt/Amt")
        or _float_val(pol, "PolicyLimit")
        or _float_val(pol, "Limit")
        or _float_val(pkg, "PolicyLimit")
    )
    result.requested_deductible = (
        _float_val(pol, "Deductible/FormatCurrencyAmt/Amt")
        or _float_val(pol, "Deductible")
        or _float_val(pkg, "Deductible")
    )


def _parse_coverages(pkg: ET.Element, result: ACORDParseResult) -> None:
    """Extract requested coverages."""
    for _cov_tag in ("Coverage", "LineBusiness", "CoveragePart"):
        for cov in pkg.iter():
            tag = _strip_ns(cov.tag)
            if tag == "Coverage" or tag == "CoveragePart":
                desc = _text(cov, "CoverageCd") or _text(cov, "CoverageDesc") or _text(cov, "Description")
                if desc and desc not in result.coverages_requested:
                    result.coverages_requested.append(desc)


def _parse_loss_history(pkg: ET.Element, result: ACORDParseResult) -> None:
    """Extract loss/claim history."""
    for elem in pkg.iter():
        tag = _strip_ns(elem.tag)
        if tag in ("LossInfo", "ClaimInfo", "PriorLoss"):
            entry: dict[str, Any] = {
                "date": _text(elem, "LossDt") or _text(elem, "ClaimDt") or _text(elem, "Date"),
                "type": _text(elem, "LossType") or _text(elem, "ClaimType") or _text(elem, "Type"),
                "amount": _float_val(elem, "LossAmt") or _float_val(elem, "ClaimAmt") or _float_val(elem, "Amount"),
                "description": _text(elem, "Description") or _text(elem, "LossDesc"),
                "status": _text(elem, "Status", "closed"),
            }
            if entry["date"] or entry["amount"]:
                result.loss_history.append(entry)


def _parse_prior_insurance(pkg: ET.Element, result: ACORDParseResult) -> None:
    """Extract prior insurance information."""
    for elem in pkg.iter():
        tag = _strip_ns(elem.tag)
        if tag in ("PriorPolicy", "PriorInsurance", "PriorCarrier"):
            result.prior_insurance = {
                "carrier": _text(elem, "InsurerName") or _text(elem, "CarrierName") or _text(elem, "Name"),
                "policy_number": _text(elem, "PolicyNumber") or _text(elem, "PolicyNum"),
                "effective_date": _text(elem, "EffectiveDt") or _text(elem, "EffectiveDate"),
                "expiration_date": _text(elem, "ExpirationDt") or _text(elem, "ExpirationDate"),
                "premium": _float_val(elem, "Premium") or _float_val(elem, "PremiumAmt"),
                "limit": _float_val(elem, "Limit") or _float_val(elem, "PolicyLimit"),
            }
            break
