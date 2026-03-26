"""Centralized business-critical thresholds for OpenInsure.

All authority limits, reserve guidelines, premium bounds, and rating
parameters live here.  Every service or agent that needs a threshold
must import from this module — never hardcode values inline.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Authority limits (used by AuthorityEngine in rbac/authority.py)
# ---------------------------------------------------------------------------


class QuoteAuthorityLimits(BaseModel):
    """Tiered authority limits for quoting."""

    auto_limit: Decimal = Decimal("50000")
    sr_uw_limit: Decimal = Decimal("250000")
    lob_head_limit: Decimal = Decimal("1000000")


class BindAuthorityLimits(BaseModel):
    """Tiered authority limits for binding."""

    auto_limit: Decimal = Decimal("25000")
    sr_uw_limit: Decimal = Decimal("100000")
    lob_head_limit: Decimal = Decimal("500000")


class SettlementAuthorityLimits(BaseModel):
    """Tiered authority limits for claim settlements."""

    adjuster_limit: Decimal = Decimal("25000")
    cco_limit: Decimal = Decimal("250000")
    cuo_limit: Decimal = Decimal("1000000")


class ReserveAuthorityLimits(BaseModel):
    """Tiered authority limits for setting reserves."""

    auto_limit: Decimal = Decimal("25000")
    adjuster_limit: Decimal = Decimal("100000")


class AuthorityLimitsConfig(BaseModel):
    """Full authority limits configuration."""

    quote: QuoteAuthorityLimits = Field(default_factory=QuoteAuthorityLimits)
    bind: BindAuthorityLimits = Field(default_factory=BindAuthorityLimits)
    settlement: SettlementAuthorityLimits = Field(default_factory=SettlementAuthorityLimits)
    reserve: ReserveAuthorityLimits = Field(default_factory=ReserveAuthorityLimits)

    def to_engine_config(self) -> dict[str, dict[str, Decimal]]:
        """Convert to the dict format expected by :class:`AuthorityEngine`."""
        return {
            "quote": {
                "auto_limit": self.quote.auto_limit,
                "sr_uw_limit": self.quote.sr_uw_limit,
                "lob_head_limit": self.quote.lob_head_limit,
            },
            "bind": {
                "auto_limit": self.bind.auto_limit,
                "sr_uw_limit": self.bind.sr_uw_limit,
                "lob_head_limit": self.bind.lob_head_limit,
            },
            "settlement": {
                "adjuster_limit": self.settlement.adjuster_limit,
                "cco_limit": self.settlement.cco_limit,
                "cuo_limit": self.settlement.cuo_limit,
            },
            "reserve": {
                "auto_limit": self.reserve.auto_limit,
                "adjuster_limit": self.reserve.adjuster_limit,
            },
        }


# ---------------------------------------------------------------------------
# Reserve guidelines (used by ClaimsProcessingService)
# ---------------------------------------------------------------------------


class SeverityReserveRange(BaseModel):
    """Reserve range for a severity tier."""

    low: Decimal
    high: Decimal


class ReserveGuidelines(BaseModel):
    """Reserve recommendations by severity tier."""

    simple: SeverityReserveRange = Field(
        default_factory=lambda: SeverityReserveRange(low=Decimal("5000"), high=Decimal("25000"))
    )
    moderate: SeverityReserveRange = Field(
        default_factory=lambda: SeverityReserveRange(low=Decimal("25000"), high=Decimal("100000"))
    )
    complex: SeverityReserveRange = Field(
        default_factory=lambda: SeverityReserveRange(low=Decimal("100000"), high=Decimal("500000"))
    )
    catastrophe: SeverityReserveRange = Field(
        default_factory=lambda: SeverityReserveRange(low=Decimal("500000"), high=Decimal("2000000"))
    )

    def for_tier(self, tier: str) -> tuple[Decimal, Decimal]:
        """Return ``(low, high)`` for a severity tier name."""
        mapping: dict[str, SeverityReserveRange] = {
            "simple": self.simple,
            "moderate": self.moderate,
            "complex": self.complex,
            "catastrophe": self.catastrophe,
        }
        r = mapping.get(tier, self.moderate)
        return (r.low, r.high)


# ---------------------------------------------------------------------------
# Premium bounds (used by CyberRatingEngine)
# ---------------------------------------------------------------------------


class PremiumBounds(BaseModel):
    """Rating engine premium bounds."""

    base_rate_per_thousand: Decimal = Decimal("1.50")
    min_premium: Decimal = Decimal("2500")
    max_premium: Decimal = Decimal("500000")

    default_requested_limit: Decimal = Decimal("1000000")
    default_requested_deductible: Decimal = Decimal("10000")


# ---------------------------------------------------------------------------
# Agent authority limits
# ---------------------------------------------------------------------------


class AgentAuthorityLimits(BaseModel):
    """Authority limits for each AI agent."""

    claims_agent: Decimal = Decimal("250000")
    underwriting_agent: Decimal = Decimal("1000000")
    policy_agent: Decimal = Decimal("5000000")
    submission_agent: Decimal = Decimal("0")
    compliance_agent: Decimal = Decimal("0")
    document_agent: Decimal = Decimal("0")
    knowledge_agent: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Singleton configuration
# ---------------------------------------------------------------------------


class PlatformLimits(BaseModel):
    """Top-level container for all platform thresholds."""

    authority: AuthorityLimitsConfig = Field(default_factory=AuthorityLimitsConfig)
    reserves: ReserveGuidelines = Field(default_factory=ReserveGuidelines)
    premium: PremiumBounds = Field(default_factory=PremiumBounds)
    agents: AgentAuthorityLimits = Field(default_factory=AgentAuthorityLimits)


# Module-level singleton — import and use directly
PLATFORM_LIMITS = PlatformLimits()
