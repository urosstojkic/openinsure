"""Tests for RBAC role definitions."""

from openinsure.rbac.roles import (
    CARRIER_ONLY_ROLES,
    CARRIER_ROLES,
    MGA_ROLES,
    ROLE_PERMISSIONS,
    DataAccess,
    DeploymentType,
    Permission,
    Role,
    RolePermissions,
)

# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------


class TestRoleEnum:
    def test_role_count(self):
        """There should be at least 23 roles."""
        assert len(Role) >= 23

    def test_role_values_are_strings(self):
        for role in Role:
            assert isinstance(role.value, str)
            assert role.value.startswith("openinsure-")

    def test_known_roles_exist(self):
        expected = {"CEO", "CUO", "SENIOR_UNDERWRITER", "UW_ANALYST", "BROKER", "PLATFORM_ADMIN"}
        actual_names = {r.name for r in Role}
        assert expected.issubset(actual_names)


# ---------------------------------------------------------------------------
# Deployment-scoped role sets
# ---------------------------------------------------------------------------


class TestDeploymentScoping:
    def test_carrier_only_roles_are_subset_of_all(self):
        assert CARRIER_ONLY_ROLES.issubset(set(Role))

    def test_mga_roles_exclude_carrier_only(self):
        assert CARRIER_ONLY_ROLES.isdisjoint(MGA_ROLES)

    def test_carrier_roles_include_all(self):
        assert set(Role) == CARRIER_ROLES

    def test_mga_plus_carrier_only_equals_all(self):
        assert set(Role) == MGA_ROLES | CARRIER_ONLY_ROLES

    def test_carrier_only_contains_expected(self):
        expected = {Role.LOB_HEAD, Role.CHIEF_ACTUARY, Role.REINSURER, Role.MGA_EXTERNAL}
        assert expected.issubset(CARRIER_ONLY_ROLES)

    def test_mga_contains_core_roles(self):
        core = {Role.CEO, Role.CUO, Role.SENIOR_UNDERWRITER, Role.CLAIMS_MANAGER, Role.BROKER}
        assert core.issubset(MGA_ROLES)


# ---------------------------------------------------------------------------
# DataAccess
# ---------------------------------------------------------------------------


class TestDataAccess:
    def test_all_levels_present(self):
        assert set(DataAccess) == {
            DataAccess.FULL,
            DataAccess.READ,
            DataAccess.OWN,
            DataAccess.SUMMARY,
            DataAccess.CONFIG,
            DataAccess.PROPOSE,
            DataAccess.NONE,
        }

    def test_values(self):
        assert DataAccess.FULL == "F"
        assert DataAccess.NONE == "-"


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------


class TestRolePermissions:
    def test_all_roles_have_permissions(self):
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"Missing permissions for {role}"

    def test_required_roles_have_full_permissions(self):
        """The 11 roles explicitly required in the spec must be present."""
        required = {
            Role.CEO,
            Role.CUO,
            Role.SENIOR_UNDERWRITER,
            Role.UW_ANALYST,
            Role.CLAIMS_MANAGER,
            Role.CLAIMS_ADJUSTER,
            Role.CFO,
            Role.COMPLIANCE_OFFICER,
            Role.PRODUCT_MANAGER,
            Role.PLATFORM_ADMIN,
            Role.BROKER,
        }
        for role in required:
            perms = ROLE_PERMISSIONS[role]
            assert isinstance(perms, RolePermissions)
            assert len(perms.data_permissions) > 0

    def test_cuo_has_full_submission_access(self):
        cuo = ROLE_PERMISSIONS[Role.CUO]
        sub_perm = next(p for p in cuo.data_permissions if p.resource == "submissions")
        assert sub_perm.access == DataAccess.FULL

    def test_broker_only_own_submissions(self):
        broker = ROLE_PERMISSIONS[Role.BROKER]
        sub_perm = next(p for p in broker.data_permissions if p.resource == "submissions")
        assert sub_perm.access == DataAccess.FULL
        assert sub_perm.scope == "own"

    def test_uw_analyst_proposes_quotes(self):
        analyst = ROLE_PERMISSIONS[Role.UW_ANALYST]
        quote_perm = next(p for p in analyst.data_permissions if p.resource == "quotes")
        assert quote_perm.access == DataAccess.PROPOSE

    def test_compliance_has_read_everywhere(self):
        co = ROLE_PERMISSIONS[Role.COMPLIANCE_OFFICER]
        for perm in co.data_permissions:
            assert perm.access in {DataAccess.FULL, DataAccess.READ}

    def test_carrier_only_role_deployment_types(self):
        for role in CARRIER_ONLY_ROLES:
            perms = ROLE_PERMISSIONS[role]
            assert DeploymentType.CARRIER in perms.deployment_types
            assert DeploymentType.MGA not in perms.deployment_types

    def test_permission_is_pydantic_model(self):
        p = Permission(resource="test", access=DataAccess.READ)
        assert p.resource == "test"
        assert p.scope == "all"  # default
