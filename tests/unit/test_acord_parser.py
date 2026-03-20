"""Tests for the ACORD 125/126 XML parser."""

from __future__ import annotations

from openinsure.services.acord_parser import parse_acord_xml

# ---------------------------------------------------------------------------
# Sample ACORD XML fragments
# ---------------------------------------------------------------------------

ACORD_125_FULL = """\
<?xml version="1.0" encoding="UTF-8"?>
<ACORD>
  <InsuranceSvcRq>
    <CommlPkgPolicyQuoteInqRq>
      <InsuredOrPrincipal>
        <NameInfo>
          <CommlName>
            <CommercialName>Meridian Healthcare Group</CommercialName>
          </CommlName>
          <TaxIdentity>
            <TaxId>12-3456789</TaxId>
          </TaxIdentity>
        </NameInfo>
        <Addr>
          <Addr1>123 Medical Drive</Addr1>
          <City>Boston</City>
          <StateProvCd>MA</StateProvCd>
          <PostalCode>02101</PostalCode>
          <CountryCd>US</CountryCd>
        </Addr>
        <Communications>
          <EmailInfo>
            <EmailAddr>risk@meridianhg.com</EmailAddr>
          </EmailInfo>
          <PhoneInfo>
            <PhoneNumber>617-555-0100</PhoneNumber>
          </PhoneInfo>
          <WebsiteURL>https://meridianhg.com</WebsiteURL>
        </Communications>
      </InsuredOrPrincipal>
      <CommlSubLocation>
        <AnnualRevenue>85000000</AnnualRevenue>
        <NumEmployees>1200</NumEmployees>
        <SICCd>8011</SICCd>
        <NAICSCd>621111</NAICSCd>
        <IndustryDesc>Healthcare</IndustryDesc>
        <YearEstablished>1995</YearEstablished>
      </CommlSubLocation>
      <CommlPolicy>
        <LOBCd>CYBER</LOBCd>
        <ContractTerm>
          <EffectiveDt>2026-01-01</EffectiveDt>
          <ExpirationDt>2027-01-01</ExpirationDt>
        </ContractTerm>
        <Limit>
          <FormatCurrencyAmt>
            <Amt>5000000</Amt>
          </FormatCurrencyAmt>
        </Limit>
        <Deductible>
          <FormatCurrencyAmt>
            <Amt>50000</Amt>
          </FormatCurrencyAmt>
        </Deductible>
      </CommlPolicy>
      <Coverage>
        <CoverageCd>BREACH-RESP</CoverageCd>
      </Coverage>
      <Coverage>
        <CoverageCd>THIRD-PARTY</CoverageCd>
      </Coverage>
      <Coverage>
        <CoverageCd>RANSOMWARE</CoverageCd>
      </Coverage>
      <LossInfo>
        <LossDt>2024-03-15</LossDt>
        <LossType>data_breach</LossType>
        <LossAmt>125000</LossAmt>
        <Description>Patient records exposed via phishing attack</Description>
      </LossInfo>
      <PriorPolicy>
        <InsurerName>Legacy Cyber Insurance Co</InsurerName>
        <PolicyNumber>LCY-2024-001</PolicyNumber>
        <EffectiveDt>2025-01-01</EffectiveDt>
        <ExpirationDt>2026-01-01</ExpirationDt>
        <Premium>42000</Premium>
      </PriorPolicy>
    </CommlPkgPolicyQuoteInqRq>
  </InsuranceSvcRq>
</ACORD>
"""

ACORD_SIMPLE = """\
<?xml version="1.0" encoding="UTF-8"?>
<ACORD>
  <InsuranceSvcRq>
    <CommlPkgPolicyQuoteInqRq>
      <GeneralPartyInfo>
        <CommercialName>NovaTech Solutions</CommercialName>
        <Addr>
          <City>San Francisco</City>
          <StateProvCd>CA</StateProvCd>
        </Addr>
        <Communications>
          <Email>ciso@novatech.io</Email>
        </Communications>
      </GeneralPartyInfo>
      <AnnualRevenue>15000000</AnnualRevenue>
      <NumEmployees>200</NumEmployees>
      <LOBCd>cyber</LOBCd>
      <PolicyLimit>2000000</PolicyLimit>
      <Deductible>25000</Deductible>
    </CommlPkgPolicyQuoteInqRq>
  </InsuranceSvcRq>
</ACORD>
"""

ACORD_MINIMAL = """\
<?xml version="1.0" encoding="UTF-8"?>
<ACORD>
  <InsuranceSvcRq>
    <CommlPkgPolicyQuoteInqRq>
      <ApplicantName>Test Corp</ApplicantName>
    </CommlPkgPolicyQuoteInqRq>
  </InsuranceSvcRq>
</ACORD>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestACORDParser:
    """Test ACORD 125/126 XML parsing."""

    def test_full_acord_125(self) -> None:
        result = parse_acord_xml(ACORD_125_FULL)
        assert result.applicant_name == "Meridian Healthcare Group"
        assert result.applicant_email == "risk@meridianhg.com"
        assert result.tax_id == "12-3456789"
        assert result.annual_revenue == 85_000_000
        assert result.employee_count == 1200
        assert result.sic_code == "8011"
        assert result.naics_code == "621111"
        assert result.industry == "Healthcare"
        assert result.year_established == 1995
        assert result.effective_date == "2026-01-01"
        assert result.expiration_date == "2027-01-01"
        assert result.line_of_business == "cyber"
        assert result.requested_limit == 5_000_000
        assert result.requested_deductible == 50_000
        assert result.address["city"] == "Boston"
        assert result.address["state"] == "MA"
        assert len(result.coverages_requested) >= 3
        assert len(result.loss_history) == 1
        assert result.loss_history[0]["amount"] == 125_000
        assert result.prior_insurance["carrier"] == "Legacy Cyber Insurance Co"
        assert len(result.parse_warnings) == 0

    def test_simple_format(self) -> None:
        result = parse_acord_xml(ACORD_SIMPLE)
        assert result.applicant_name == "NovaTech Solutions"
        assert result.applicant_email == "ciso@novatech.io"
        assert result.annual_revenue == 15_000_000
        assert result.employee_count == 200
        assert result.line_of_business == "cyber"
        assert result.requested_limit == 2_000_000
        assert result.requested_deductible == 25_000

    def test_minimal_form(self) -> None:
        result = parse_acord_xml(ACORD_MINIMAL)
        assert result.applicant_name == "Test Corp"

    def test_to_submission_payload(self) -> None:
        result = parse_acord_xml(ACORD_125_FULL)
        payload = result.to_submission()
        assert payload["applicant_name"] == "Meridian Healthcare Group"
        assert payload["applicant_email"] == "risk@meridianhg.com"
        assert payload["channel"] == "api"
        assert payload["line_of_business"] == "cyber"
        assert payload["risk_data"]["annual_revenue"] == 85_000_000
        assert payload["risk_data"]["employee_count"] == 1200
        assert payload["risk_data"]["industry"] == "Healthcare"
        assert payload["metadata"]["source"] == "acord_xml"
        assert payload["cyber_risk_data"]["requested_limit"] == 5_000_000

    def test_invalid_xml(self) -> None:
        result = parse_acord_xml("<not valid xml")
        assert len(result.parse_warnings) > 0

    def test_bytes_input(self) -> None:
        result = parse_acord_xml(ACORD_SIMPLE.encode("utf-8"))
        assert result.applicant_name == "NovaTech Solutions"

    def test_unknown_lob_defaults_to_cyber(self) -> None:
        xml = ACORD_SIMPLE.replace("<LOBCd>cyber</LOBCd>", "<LOBCd>PROPERTY</LOBCd>")
        result = parse_acord_xml(xml)
        assert result.line_of_business == "cyber"
        assert any("Unknown LOB" in w for w in result.parse_warnings)
