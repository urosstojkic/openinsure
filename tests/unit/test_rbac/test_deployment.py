"""Tests for deployment profiles."""

from openinsure.rbac.deployment import CARRIER_PROFILE, MGA_PROFILE, DeploymentConfig, ModuleConfig


class TestModuleConfig:
    def test_defaults_are_mga_style(self):
        cfg = ModuleConfig()
        assert cfg.underwriting is True
        assert cfg.policy_admin is True
        assert cfg.claims is True
        assert cfg.billing is True
        assert cfg.compliance is True
        assert cfg.actuarial is False
        assert cfg.reinsurance is False
        assert cfg.mga_oversight is False
        assert cfg.statutory_reporting is False

    def test_carrier_modules_can_be_enabled(self):
        cfg = ModuleConfig(actuarial=True, reinsurance=True)
        assert cfg.actuarial is True
        assert cfg.reinsurance is True


class TestMGAProfile:
    def test_type(self):
        assert MGA_PROFILE.deployment_type == "mga"

    def test_single_lob(self):
        assert MGA_PROFILE.multi_lob is False
        assert MGA_PROFILE.lines_of_business == ["cyber"]

    def test_territories(self):
        assert MGA_PROFILE.territories == ["US"]

    def test_carrier_modules_disabled(self):
        m = MGA_PROFILE.enabled_modules
        assert m.actuarial is False
        assert m.reinsurance is False
        assert m.mga_oversight is False
        assert m.statutory_reporting is False

    def test_core_modules_enabled(self):
        m = MGA_PROFILE.enabled_modules
        assert m.underwriting is True
        assert m.claims is True
        assert m.billing is True


class TestCarrierProfile:
    def test_type(self):
        assert CARRIER_PROFILE.deployment_type == "carrier"

    def test_multi_lob(self):
        assert CARRIER_PROFILE.multi_lob is True
        assert len(CARRIER_PROFILE.lines_of_business) >= 3

    def test_multi_territory(self):
        assert len(CARRIER_PROFILE.territories) >= 2

    def test_all_modules_enabled(self):
        m = CARRIER_PROFILE.enabled_modules
        assert m.actuarial is True
        assert m.reinsurance is True
        assert m.mga_oversight is True
        assert m.statutory_reporting is True
        assert m.underwriting is True
        assert m.claims is True


class TestDeploymentConfig:
    def test_default_is_mga(self):
        cfg = DeploymentConfig()
        assert cfg.deployment_type == "mga"
        assert cfg.multi_lob is False

    def test_custom_config(self):
        cfg = DeploymentConfig(
            deployment_type="carrier",
            multi_lob=True,
            lines_of_business=["cyber", "property"],
            territories=["US", "UK"],
        )
        assert cfg.deployment_type == "carrier"
        assert len(cfg.lines_of_business) == 2
