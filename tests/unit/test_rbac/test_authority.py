"""Tests for the authority engine."""

from decimal import Decimal

from openinsure.rbac.authority import AuthorityDecision, AuthorityEngine, AuthorityResult
from openinsure.rbac.roles import Role


class TestAuthorityResult:
    def test_auto_execute(self):
        r = AuthorityResult(decision=AuthorityDecision.AUTO_EXECUTE, reason="ok")
        assert r.decision == AuthorityDecision.AUTO_EXECUTE
        assert r.required_role is None
        assert r.escalation_chain == []


class TestQuoteAuthority:
    engine = AuthorityEngine()

    def test_auto_below_limit(self):
        result = self.engine.check_quote_authority(Decimal("30000"), Role.UW_ANALYST)
        assert result.decision == AuthorityDecision.AUTO_EXECUTE

    def test_auto_at_limit(self):
        result = self.engine.check_quote_authority(Decimal("50000"), Role.UW_ANALYST)
        assert result.decision == AuthorityDecision.AUTO_EXECUTE

    def test_analyst_escalates_above_auto(self):
        result = self.engine.check_quote_authority(Decimal("80000"), Role.UW_ANALYST)
        assert result.decision == AuthorityDecision.ESCALATE
        assert result.required_role == Role.SENIOR_UNDERWRITER

    def test_sr_uw_recommends_within_limit(self):
        result = self.engine.check_quote_authority(Decimal("200000"), Role.SENIOR_UNDERWRITER)
        assert result.decision == AuthorityDecision.RECOMMEND

    def test_sr_uw_escalates_above_limit(self):
        result = self.engine.check_quote_authority(Decimal("500000"), Role.SENIOR_UNDERWRITER)
        assert result.decision == AuthorityDecision.ESCALATE
        assert result.required_role == Role.LOB_HEAD

    def test_lob_head_recommends_within_limit(self):
        result = self.engine.check_quote_authority(Decimal("800000"), Role.LOB_HEAD)
        assert result.decision == AuthorityDecision.RECOMMEND

    def test_lob_head_escalates_above_limit(self):
        result = self.engine.check_quote_authority(Decimal("2000000"), Role.LOB_HEAD)
        assert result.decision == AuthorityDecision.ESCALATE
        assert result.required_role == Role.CUO

    def test_cuo_approves_large(self):
        result = self.engine.check_quote_authority(Decimal("5000000"), Role.CUO)
        assert result.decision == AuthorityDecision.REQUIRE_APPROVAL

    def test_ceo_approves_any(self):
        result = self.engine.check_quote_authority(Decimal("50000000"), Role.CEO)
        assert result.decision == AuthorityDecision.REQUIRE_APPROVAL

    def test_unknown_role_escalates(self):
        result = self.engine.check_quote_authority(Decimal("100000"), Role.BROKER)
        assert result.decision == AuthorityDecision.ESCALATE


class TestBindAuthority:
    engine = AuthorityEngine()

    def test_auto_below_limit(self):
        result = self.engine.check_bind_authority(Decimal("20000"), Role.UW_ANALYST, limit=Decimal("100000"))
        assert result.decision == AuthorityDecision.AUTO_EXECUTE

    def test_sr_uw_recommends(self):
        result = self.engine.check_bind_authority(Decimal("80000"), Role.SENIOR_UNDERWRITER, limit=Decimal("500000"))
        assert result.decision == AuthorityDecision.RECOMMEND

    def test_analyst_escalates_bind(self):
        result = self.engine.check_bind_authority(Decimal("60000"), Role.UW_ANALYST, limit=Decimal("200000"))
        assert result.decision == AuthorityDecision.ESCALATE

    def test_cuo_approves_large_bind(self):
        result = self.engine.check_bind_authority(Decimal("600000"), Role.CUO, limit=Decimal("2000000"))
        assert result.decision == AuthorityDecision.REQUIRE_APPROVAL


class TestSettlementAuthority:
    engine = AuthorityEngine()

    def test_adjuster_recommends_small(self):
        result = self.engine.check_settlement_authority(Decimal("10000"), Role.CLAIMS_ADJUSTER)
        assert result.decision == AuthorityDecision.RECOMMEND

    def test_adjuster_escalates_medium(self):
        result = self.engine.check_settlement_authority(Decimal("100000"), Role.CLAIMS_ADJUSTER)
        assert result.decision == AuthorityDecision.ESCALATE
        assert result.required_role == Role.CLAIMS_MANAGER

    def test_cco_recommends_medium(self):
        result = self.engine.check_settlement_authority(Decimal("100000"), Role.CLAIMS_MANAGER)
        assert result.decision == AuthorityDecision.RECOMMEND

    def test_cco_escalates_large(self):
        result = self.engine.check_settlement_authority(Decimal("500000"), Role.CLAIMS_MANAGER)
        assert result.decision == AuthorityDecision.ESCALATE
        assert result.required_role == Role.CUO

    def test_cuo_approves_large(self):
        result = self.engine.check_settlement_authority(Decimal("800000"), Role.CUO)
        assert result.decision == AuthorityDecision.REQUIRE_APPROVAL

    def test_ceo_approves_very_large(self):
        result = self.engine.check_settlement_authority(Decimal("5000000"), Role.CEO)
        assert result.decision == AuthorityDecision.REQUIRE_APPROVAL

    def test_unknown_role_escalates(self):
        result = self.engine.check_settlement_authority(Decimal("10000"), Role.BROKER)
        assert result.decision == AuthorityDecision.ESCALATE


class TestReserveAuthority:
    engine = AuthorityEngine()

    def test_auto_below_limit(self):
        result = self.engine.check_reserve_authority(Decimal("15000"), Role.CLAIMS_ADJUSTER)
        assert result.decision == AuthorityDecision.AUTO_EXECUTE

    def test_adjuster_recommends(self):
        result = self.engine.check_reserve_authority(Decimal("60000"), Role.CLAIMS_ADJUSTER)
        assert result.decision == AuthorityDecision.RECOMMEND

    def test_adjuster_escalates_large(self):
        result = self.engine.check_reserve_authority(Decimal("200000"), Role.CLAIMS_ADJUSTER)
        assert result.decision == AuthorityDecision.ESCALATE
        assert result.required_role == Role.CLAIMS_MANAGER

    def test_cco_approves_large(self):
        result = self.engine.check_reserve_authority(Decimal("200000"), Role.CLAIMS_MANAGER)
        assert result.decision == AuthorityDecision.REQUIRE_APPROVAL


class TestCustomConfig:
    def test_custom_limits(self):
        custom = {
            "quote": {
                "auto_limit": Decimal("10000"),
                "sr_uw_limit": Decimal("50000"),
                "lob_head_limit": Decimal("100000"),
            },
            "bind": {
                "auto_limit": Decimal("5000"),
                "sr_uw_limit": Decimal("20000"),
                "lob_head_limit": Decimal("50000"),
            },
            "settlement": {
                "adjuster_limit": Decimal("5000"),
                "cco_limit": Decimal("50000"),
                "cuo_limit": Decimal("200000"),
            },
            "reserve": {
                "auto_limit": Decimal("5000"),
                "adjuster_limit": Decimal("20000"),
            },
        }
        engine = AuthorityEngine(config=custom)
        # With tighter limits, $30k quote should escalate for analyst
        result = engine.check_quote_authority(Decimal("30000"), Role.UW_ANALYST)
        assert result.decision == AuthorityDecision.ESCALATE


class TestEscalationChain:
    engine = AuthorityEngine()

    def test_analyst_escalation_chain(self):
        result = self.engine.check_quote_authority(Decimal("100000"), Role.UW_ANALYST)
        assert result.decision == AuthorityDecision.ESCALATE
        assert Role.SENIOR_UNDERWRITER in result.escalation_chain
        assert Role.CUO in result.escalation_chain

    def test_adjuster_settlement_chain(self):
        result = self.engine.check_settlement_authority(Decimal("100000"), Role.CLAIMS_ADJUSTER)
        assert result.decision == AuthorityDecision.ESCALATE
        assert Role.CLAIMS_MANAGER in result.escalation_chain
