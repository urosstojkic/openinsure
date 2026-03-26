"""Authority engine for human-agent collaboration.

Implements the complexity × consequence authority matrix from the operating model.
Determines whether an action can be auto-executed, needs recommendation, or requires
approval.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from openinsure.domain.limits import PLATFORM_LIMITS
from openinsure.rbac.roles import Role

if TYPE_CHECKING:
    from decimal import Decimal


class AuthorityDecision(StrEnum):
    AUTO_EXECUTE = "auto_execute"
    RECOMMEND = "recommend"  # Agent recommends, human confirms
    REQUIRE_APPROVAL = "require_approval"  # Human must approve
    ESCALATE = "escalate"  # Route to higher authority


class AuthorityResult(BaseModel):
    """Result of an authority check."""

    decision: AuthorityDecision
    reason: str
    required_role: str | None = None
    escalation_chain: list[str] = []


# ---------------------------------------------------------------------------
# Role hierarchy helpers
# ---------------------------------------------------------------------------

_UW_HIERARCHY: list[str] = [
    Role.UW_ANALYST,
    Role.SENIOR_UNDERWRITER,
    Role.LOB_HEAD,
    Role.CUO,
    Role.CEO,
]

_CLAIMS_HIERARCHY: list[str] = [
    Role.CLAIMS_ADJUSTER,
    Role.CLAIMS_MANAGER,
    Role.CUO,
    Role.CEO,
]


def _role_level(role: str, hierarchy: list[str]) -> int:
    """Return the position of *role* in *hierarchy* (-1 if absent)."""
    try:
        return hierarchy.index(role)
    except ValueError:
        return -1


def _escalation_above(role: str, hierarchy: list[str]) -> list[str]:
    """Return hierarchy members strictly above *role*."""
    level = _role_level(role, hierarchy)
    if level < 0:
        return list(hierarchy)
    return hierarchy[level + 1 :]


# ---------------------------------------------------------------------------
# Default authority configuration — sourced from centralized limits
# ---------------------------------------------------------------------------

DEFAULT_AUTHORITY_CONFIG: dict[str, dict[str, Decimal]] = PLATFORM_LIMITS.authority.to_engine_config()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AuthorityEngine:
    """Configurable authority engine.

    Uses a tiered limits configuration to decide whether an action can be
    auto-executed by an agent, recommended for human confirmation, or must be
    escalated to a higher authority.
    """

    def __init__(self, config: dict[str, dict[str, Decimal]] | None = None) -> None:
        self.config = config or DEFAULT_AUTHORITY_CONFIG

    # -- Underwriting -------------------------------------------------------

    def check_quote_authority(self, premium: Decimal, user_role: str) -> AuthorityResult:
        """Check if the user/agent can issue a quote at *premium*."""
        cfg = self.config["quote"]
        level = _role_level(user_role, _UW_HIERARCHY)

        if premium <= cfg["auto_limit"]:
            return AuthorityResult(decision=AuthorityDecision.AUTO_EXECUTE, reason="Premium within auto-quote limit.")

        if premium <= cfg["sr_uw_limit"]:
            needed = Role.SENIOR_UNDERWRITER
            if level >= _role_level(needed, _UW_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.RECOMMEND,
                    reason="Premium within Sr UW authority.",
                    required_role=needed,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Premium exceeds analyst authority.",
                required_role=needed,
                escalation_chain=_escalation_above(user_role, _UW_HIERARCHY),
            )

        if premium <= cfg["lob_head_limit"]:
            needed = Role.LOB_HEAD
            if level >= _role_level(needed, _UW_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.RECOMMEND,
                    reason="Premium within LOB Head authority.",
                    required_role=needed,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Premium exceeds Sr UW authority.",
                required_role=needed,
                escalation_chain=_escalation_above(user_role, _UW_HIERARCHY),
            )

        # Above LOB head limit → CUO required
        needed = Role.CUO
        if level >= _role_level(needed, _UW_HIERARCHY):
            return AuthorityResult(
                decision=AuthorityDecision.REQUIRE_APPROVAL,
                reason="Premium requires CUO approval.",
                required_role=needed,
            )
        return AuthorityResult(
            decision=AuthorityDecision.ESCALATE,
            reason="Premium exceeds LOB Head authority.",
            required_role=needed,
            escalation_chain=_escalation_above(user_role, _UW_HIERARCHY),
        )

    def check_bind_authority(self, premium: Decimal, user_role: str, limit: Decimal) -> AuthorityResult:
        """Check if the user/agent can bind a policy at *premium* / *limit*."""
        cfg = self.config["bind"]
        level = _role_level(user_role, _UW_HIERARCHY)
        # Authority decisions are based on premium; limit is logged for audit
        _ = limit

        if premium <= cfg["auto_limit"]:
            return AuthorityResult(decision=AuthorityDecision.AUTO_EXECUTE, reason="Premium within auto-bind limit.")

        if premium <= cfg["sr_uw_limit"]:
            needed = Role.SENIOR_UNDERWRITER
            if level >= _role_level(needed, _UW_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.RECOMMEND,
                    reason="Bind within Sr UW authority.",
                    required_role=needed,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Bind exceeds analyst authority.",
                required_role=needed,
                escalation_chain=_escalation_above(user_role, _UW_HIERARCHY),
            )

        if premium <= cfg["lob_head_limit"]:
            needed = Role.LOB_HEAD
            if level >= _role_level(needed, _UW_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.RECOMMEND,
                    reason="Bind within LOB Head authority.",
                    required_role=needed,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Bind exceeds Sr UW authority.",
                required_role=needed,
                escalation_chain=_escalation_above(user_role, _UW_HIERARCHY),
            )

        needed = Role.CUO
        if level >= _role_level(needed, _UW_HIERARCHY):
            return AuthorityResult(
                decision=AuthorityDecision.REQUIRE_APPROVAL,
                reason="Bind requires CUO approval.",
                required_role=needed,
            )
        return AuthorityResult(
            decision=AuthorityDecision.ESCALATE,
            reason="Bind exceeds LOB Head authority.",
            required_role=needed,
            escalation_chain=_escalation_above(user_role, _UW_HIERARCHY),
        )

    # -- Claims -------------------------------------------------------------

    def check_settlement_authority(self, amount: Decimal, user_role: str) -> AuthorityResult:
        """Check if the user/agent can settle a claim at *amount*."""
        cfg = self.config["settlement"]
        level = _role_level(user_role, _CLAIMS_HIERARCHY)

        if amount <= cfg["adjuster_limit"]:
            if level >= _role_level(Role.CLAIMS_ADJUSTER, _CLAIMS_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.RECOMMEND,
                    reason="Settlement within adjuster authority.",
                    required_role=Role.CLAIMS_ADJUSTER,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Role lacks settlement authority.",
                required_role=Role.CLAIMS_ADJUSTER,
                escalation_chain=list(_CLAIMS_HIERARCHY),
            )

        if amount <= cfg["cco_limit"]:
            needed = Role.CLAIMS_MANAGER
            if level >= _role_level(needed, _CLAIMS_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.RECOMMEND,
                    reason="Settlement within CCO authority.",
                    required_role=needed,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Settlement exceeds adjuster authority.",
                required_role=needed,
                escalation_chain=_escalation_above(user_role, _CLAIMS_HIERARCHY),
            )

        if amount <= cfg["cuo_limit"]:
            needed = Role.CUO
            if level >= _role_level(needed, _CLAIMS_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.REQUIRE_APPROVAL,
                    reason="Settlement requires CUO approval.",
                    required_role=needed,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Settlement exceeds CCO authority.",
                required_role=needed,
                escalation_chain=_escalation_above(user_role, _CLAIMS_HIERARCHY),
            )

        # Above CUO limit → CEO
        needed = Role.CEO
        if level >= _role_level(needed, _CLAIMS_HIERARCHY):
            return AuthorityResult(
                decision=AuthorityDecision.REQUIRE_APPROVAL,
                reason="Settlement requires CEO approval.",
                required_role=needed,
            )
        return AuthorityResult(
            decision=AuthorityDecision.ESCALATE,
            reason="Settlement exceeds CUO authority.",
            required_role=needed,
            escalation_chain=_escalation_above(user_role, _CLAIMS_HIERARCHY),
        )

    def check_reserve_authority(self, amount: Decimal, user_role: str) -> AuthorityResult:
        """Check if the user/agent can set a reserve at *amount*."""
        cfg = self.config["reserve"]
        level = _role_level(user_role, _CLAIMS_HIERARCHY)

        if amount <= cfg["auto_limit"]:
            return AuthorityResult(decision=AuthorityDecision.AUTO_EXECUTE, reason="Reserve within auto-set limit.")

        if amount <= cfg["adjuster_limit"]:
            needed = Role.CLAIMS_ADJUSTER
            if level >= _role_level(needed, _CLAIMS_HIERARCHY):
                return AuthorityResult(
                    decision=AuthorityDecision.RECOMMEND,
                    reason="Reserve within adjuster authority.",
                    required_role=needed,
                )
            return AuthorityResult(
                decision=AuthorityDecision.ESCALATE,
                reason="Role lacks reserve authority.",
                required_role=needed,
                escalation_chain=list(_CLAIMS_HIERARCHY),
            )

        # Above adjuster limit → CCO
        needed = Role.CLAIMS_MANAGER
        if level >= _role_level(needed, _CLAIMS_HIERARCHY):
            return AuthorityResult(
                decision=AuthorityDecision.REQUIRE_APPROVAL,
                reason="Reserve requires CCO approval.",
                required_role=needed,
            )
        return AuthorityResult(
            decision=AuthorityDecision.ESCALATE,
            reason="Reserve exceeds adjuster authority.",
            required_role=needed,
            escalation_chain=_escalation_above(user_role, _CLAIMS_HIERARCHY),
        )
