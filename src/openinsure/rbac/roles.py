"""OpenInsure RBAC role definitions.

Maps the operating model personas to role-based access control.
Supports carrier and MGA deployment types.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    """All platform roles. Tagged with deployment scope."""

    # Leadership
    CEO = "openinsure-ceo"
    CUO = "openinsure-cuo"

    # Underwriting
    LOB_HEAD = "openinsure-lob-head"  # CARRIER only
    SENIOR_UNDERWRITER = "openinsure-senior-underwriter"
    UW_ANALYST = "openinsure-uw-analyst"

    # Actuarial (CARRIER only)
    CHIEF_ACTUARY = "openinsure-chief-actuary"
    ACTUARY = "openinsure-actuary"

    # Claims
    CLAIMS_MANAGER = "openinsure-claims-manager"  # CCO
    CLAIMS_ADJUSTER = "openinsure-claims-adjuster"

    # Finance
    CFO = "openinsure-cfo"
    FINANCE = "openinsure-finance"
    REINSURANCE_MANAGER = "openinsure-reinsurance-manager"  # CARRIER only

    # Compliance
    COMPLIANCE_OFFICER = "openinsure-compliance"

    # Delegated Authority (CARRIER only)
    DA_MANAGER = "openinsure-da-manager"

    # Product & Tech
    PRODUCT_MANAGER = "openinsure-product-manager"
    PLATFORM_ADMIN = "openinsure-platform-admin"
    OPERATIONS = "openinsure-operations"

    # External
    BROKER = "openinsure-broker"
    MGA_EXTERNAL = "openinsure-mga-external"  # CARRIER only
    POLICYHOLDER = "openinsure-policyholder"
    REINSURER = "openinsure-reinsurer"  # CARRIER only
    AUDITOR = "openinsure-auditor"
    VENDOR = "openinsure-vendor"


class DeploymentType(StrEnum):
    CARRIER = "carrier"
    MGA = "mga"


# Which roles are available per deployment type
CARRIER_ONLY_ROLES: set[Role] = {
    Role.LOB_HEAD,
    Role.CHIEF_ACTUARY,
    Role.ACTUARY,
    Role.REINSURANCE_MANAGER,
    Role.DA_MANAGER,
    Role.MGA_EXTERNAL,
    Role.REINSURER,
}

MGA_ROLES: set[Role] = {r for r in Role if r not in CARRIER_ONLY_ROLES}
CARRIER_ROLES: set[Role] = set(Role)


class DataAccess(StrEnum):
    """Data access levels from the RBAC matrix."""

    FULL = "F"  # Full Read/Write
    READ = "R"  # Read only
    OWN = "O"  # Own/Assigned only
    SUMMARY = "S"  # Summary/Aggregated
    CONFIG = "C"  # Config access
    PROPOSE = "P"  # Propose (requires approval)
    NONE = "-"  # No Access


class Permission(BaseModel):
    """A specific permission grant."""

    resource: str  # e.g., "submissions", "policies", "claims"
    access: DataAccess
    scope: str = "all"  # "all", "own_lob", "own_queue", "assigned", "mga_only"


class RolePermissions(BaseModel):
    """Complete permission set for a role."""

    role: Role
    display_name: str
    description: str
    deployment_types: list[DeploymentType]
    data_permissions: list[Permission]
    authority_limits: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_BOTH = [DeploymentType.CARRIER, DeploymentType.MGA]
_CARRIER = [DeploymentType.CARRIER]

# ---------------------------------------------------------------------------
# Full permission matrix (Section 3.1)
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS: dict[Role, RolePermissions] = {
    # ── Leadership ────────────────────────────────────────────────────────
    Role.CEO: RolePermissions(
        role=Role.CEO,
        display_name="Chief Executive Officer",
        description="Full strategic oversight with summary-level operational data.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.SUMMARY),
            Permission(resource="quotes", access=DataAccess.SUMMARY),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.SUMMARY),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.FULL),
            Permission(resource="system", access=DataAccess.CONFIG),
        ],
    ),
    Role.CUO: RolePermissions(
        role=Role.CUO,
        display_name="Chief Underwriting Officer",
        description="Full underwriting authority across all lines.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.FULL),
            Permission(resource="quotes", access=DataAccess.FULL),
            Permission(resource="policies", access=DataAccess.FULL),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.FULL),
            Permission(resource="finance", access=DataAccess.SUMMARY),
            Permission(resource="system", access=DataAccess.CONFIG),
        ],
        authority_limits={"quote_limit": 10_000_000, "bind_limit": 5_000_000},
    ),
    # ── Underwriting ──────────────────────────────────────────────────────
    Role.LOB_HEAD: RolePermissions(
        role=Role.LOB_HEAD,
        display_name="Line of Business Head",
        description="Full authority for an assigned LOB (carrier only).",
        deployment_types=_CARRIER,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.FULL, scope="own_lob"),
            Permission(resource="quotes", access=DataAccess.FULL, scope="own_lob"),
            Permission(resource="policies", access=DataAccess.FULL, scope="own_lob"),
            Permission(resource="claims", access=DataAccess.READ, scope="own_lob"),
            Permission(resource="billing", access=DataAccess.READ, scope="own_lob"),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.FULL, scope="own_lob"),
            Permission(resource="finance", access=DataAccess.SUMMARY, scope="own_lob"),
            Permission(resource="system", access=DataAccess.NONE),
        ],
        authority_limits={"quote_limit": 1_000_000, "bind_limit": 500_000},
    ),
    Role.SENIOR_UNDERWRITER: RolePermissions(
        role=Role.SENIOR_UNDERWRITER,
        display_name="Senior Underwriter",
        description="Experienced underwriter with elevated authority.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.FULL, scope="own_lob"),
            Permission(resource="quotes", access=DataAccess.FULL, scope="own_lob"),
            Permission(resource="policies", access=DataAccess.FULL, scope="own_lob"),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.NONE),
        ],
        authority_limits={"quote_limit": 250_000, "bind_limit": 100_000},
    ),
    Role.UW_ANALYST: RolePermissions(
        role=Role.UW_ANALYST,
        display_name="Underwriting Analyst",
        description="Junior underwriter working assigned queue.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.FULL, scope="own_queue"),
            Permission(resource="quotes", access=DataAccess.PROPOSE),
            Permission(resource="policies", access=DataAccess.READ, scope="own_lob"),
            Permission(resource="claims", access=DataAccess.NONE),
            Permission(resource="billing", access=DataAccess.NONE),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.NONE),
        ],
        authority_limits={"quote_limit": 50_000, "bind_limit": 25_000},
    ),
    # ── Actuarial ─────────────────────────────────────────────────────────
    Role.CHIEF_ACTUARY: RolePermissions(
        role=Role.CHIEF_ACTUARY,
        display_name="Chief Actuary",
        description="Leads actuarial function (carrier only).",
        deployment_types=_CARRIER,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.NONE),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.FULL),
            Permission(resource="finance", access=DataAccess.READ),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    Role.ACTUARY: RolePermissions(
        role=Role.ACTUARY,
        display_name="Actuary",
        description="Actuarial analyst (carrier only).",
        deployment_types=_CARRIER,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.NONE),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    # ── Claims ────────────────────────────────────────────────────────────
    Role.CLAIMS_MANAGER: RolePermissions(
        role=Role.CLAIMS_MANAGER,
        display_name="Chief Claims Officer",
        description="Full claims management authority.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.NONE),
            Permission(resource="quotes", access=DataAccess.NONE),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.FULL),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.SUMMARY),
            Permission(resource="system", access=DataAccess.NONE),
        ],
        authority_limits={"settlement_limit": 250_000, "reserve_limit": 500_000},
    ),
    Role.CLAIMS_ADJUSTER: RolePermissions(
        role=Role.CLAIMS_ADJUSTER,
        display_name="Claims Adjuster",
        description="Handles assigned claims.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.NONE),
            Permission(resource="quotes", access=DataAccess.NONE),
            Permission(resource="policies", access=DataAccess.READ, scope="assigned"),
            Permission(resource="claims", access=DataAccess.FULL, scope="own_queue"),
            Permission(resource="billing", access=DataAccess.NONE),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.NONE),
        ],
        authority_limits={"settlement_limit": 25_000, "reserve_limit": 100_000},
    ),
    # ── Finance ───────────────────────────────────────────────────────────
    Role.CFO: RolePermissions(
        role=Role.CFO,
        display_name="Chief Financial Officer",
        description="Full finance and billing authority.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.SUMMARY),
            Permission(resource="quotes", access=DataAccess.SUMMARY),
            Permission(resource="policies", access=DataAccess.SUMMARY),
            Permission(resource="claims", access=DataAccess.SUMMARY),
            Permission(resource="billing", access=DataAccess.FULL),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.FULL),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    Role.FINANCE: RolePermissions(
        role=Role.FINANCE,
        display_name="Finance Analyst",
        description="Finance team member.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.NONE),
            Permission(resource="quotes", access=DataAccess.NONE),
            Permission(resource="policies", access=DataAccess.SUMMARY),
            Permission(resource="claims", access=DataAccess.SUMMARY),
            Permission(resource="billing", access=DataAccess.FULL),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.FULL),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    Role.REINSURANCE_MANAGER: RolePermissions(
        role=Role.REINSURANCE_MANAGER,
        display_name="Reinsurance Manager",
        description="Manages reinsurance treaties and cessions (carrier only).",
        deployment_types=_CARRIER,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.NONE),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.FULL, scope="reinsurance"),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    # ── Compliance ────────────────────────────────────────────────────────
    Role.COMPLIANCE_OFFICER: RolePermissions(
        role=Role.COMPLIANCE_OFFICER,
        display_name="Compliance Officer",
        description="Read access everywhere; full compliance management.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.FULL),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.READ),
            Permission(resource="system", access=DataAccess.READ),
        ],
    ),
    # ── Delegated Authority ───────────────────────────────────────────────
    Role.DA_MANAGER: RolePermissions(
        role=Role.DA_MANAGER,
        display_name="Delegated Authority Manager",
        description="Oversees MGA/DA relationships (carrier only).",
        deployment_types=_CARRIER,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ, scope="mga_only"),
            Permission(resource="quotes", access=DataAccess.READ, scope="mga_only"),
            Permission(resource="policies", access=DataAccess.READ, scope="mga_only"),
            Permission(resource="claims", access=DataAccess.READ, scope="mga_only"),
            Permission(resource="billing", access=DataAccess.READ, scope="mga_only"),
            Permission(resource="compliance", access=DataAccess.FULL, scope="mga_only"),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.SUMMARY),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    # ── Product & Tech ────────────────────────────────────────────────────
    Role.PRODUCT_MANAGER: RolePermissions(
        role=Role.PRODUCT_MANAGER,
        display_name="Product Manager",
        description="Manages product configuration and lifecycle.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.SUMMARY),
            Permission(resource="billing", access=DataAccess.SUMMARY),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.FULL),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.CONFIG),
        ],
    ),
    Role.PLATFORM_ADMIN: RolePermissions(
        role=Role.PLATFORM_ADMIN,
        display_name="Platform Administrator",
        description="System configuration and user management.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.READ),
            Permission(resource="system", access=DataAccess.FULL),
        ],
    ),
    Role.OPERATIONS: RolePermissions(
        role=Role.OPERATIONS,
        display_name="Operations",
        description="Day-to-day operational support.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.READ),
        ],
    ),
    # ── External ──────────────────────────────────────────────────────────
    Role.BROKER: RolePermissions(
        role=Role.BROKER,
        display_name="Broker",
        description="External broker submitting and tracking business.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.FULL, scope="own"),
            Permission(resource="quotes", access=DataAccess.READ, scope="own"),
            Permission(resource="policies", access=DataAccess.READ, scope="own"),
            Permission(resource="claims", access=DataAccess.READ, scope="own"),
            Permission(resource="billing", access=DataAccess.READ, scope="own"),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    Role.MGA_EXTERNAL: RolePermissions(
        role=Role.MGA_EXTERNAL,
        display_name="MGA (External)",
        description="External MGA operating under delegated authority (carrier only).",
        deployment_types=_CARRIER,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.FULL, scope="own"),
            Permission(resource="quotes", access=DataAccess.FULL, scope="own"),
            Permission(resource="policies", access=DataAccess.READ, scope="own"),
            Permission(resource="claims", access=DataAccess.OWN),
            Permission(resource="billing", access=DataAccess.READ, scope="own"),
            Permission(resource="compliance", access=DataAccess.READ, scope="own"),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    Role.POLICYHOLDER: RolePermissions(
        role=Role.POLICYHOLDER,
        display_name="Policyholder",
        description="Insured party accessing their own data.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.NONE),
            Permission(resource="quotes", access=DataAccess.NONE),
            Permission(resource="policies", access=DataAccess.READ, scope="own"),
            Permission(resource="claims", access=DataAccess.OWN),
            Permission(resource="billing", access=DataAccess.READ, scope="own"),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    Role.REINSURER: RolePermissions(
        role=Role.REINSURER,
        display_name="Reinsurer",
        description="Reinsurance partner with treaty-level access (carrier only).",
        deployment_types=_CARRIER,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.NONE),
            Permission(resource="quotes", access=DataAccess.NONE),
            Permission(resource="policies", access=DataAccess.SUMMARY),
            Permission(resource="claims", access=DataAccess.SUMMARY),
            Permission(resource="billing", access=DataAccess.NONE),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.READ, scope="reinsurance"),
            Permission(resource="system", access=DataAccess.NONE),
        ],
    ),
    Role.AUDITOR: RolePermissions(
        role=Role.AUDITOR,
        display_name="Auditor",
        description="Read-only audit access across the platform.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.READ),
            Permission(resource="quotes", access=DataAccess.READ),
            Permission(resource="policies", access=DataAccess.READ),
            Permission(resource="claims", access=DataAccess.READ),
            Permission(resource="billing", access=DataAccess.READ),
            Permission(resource="compliance", access=DataAccess.READ),
            Permission(resource="products", access=DataAccess.READ),
            Permission(resource="finance", access=DataAccess.READ),
            Permission(resource="system", access=DataAccess.READ),
        ],
    ),
    Role.VENDOR: RolePermissions(
        role=Role.VENDOR,
        display_name="Vendor",
        description="Third-party vendor with limited data access.",
        deployment_types=_BOTH,
        data_permissions=[
            Permission(resource="submissions", access=DataAccess.NONE),
            Permission(resource="quotes", access=DataAccess.NONE),
            Permission(resource="policies", access=DataAccess.NONE),
            Permission(resource="claims", access=DataAccess.NONE),
            Permission(resource="billing", access=DataAccess.NONE),
            Permission(resource="compliance", access=DataAccess.NONE),
            Permission(resource="products", access=DataAccess.NONE),
            Permission(resource="finance", access=DataAccess.NONE),
            Permission(resource="system", access=DataAccess.READ),
        ],
    ),
}
