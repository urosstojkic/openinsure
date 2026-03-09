"""Deployment type configuration: Carrier vs MGA.

Carrier deployment enables all modules. MGA disables actuarial, reinsurance,
MGA oversight, and statutory reporting modules.
"""

from __future__ import annotations

from pydantic import BaseModel


class ModuleConfig(BaseModel):
    """Feature-flag set for platform modules."""

    underwriting: bool = True
    policy_admin: bool = True
    claims: bool = True
    billing: bool = True
    compliance: bool = True
    actuarial: bool = False  # CARRIER only
    reinsurance: bool = False  # CARRIER only
    mga_oversight: bool = False  # CARRIER only
    statutory_reporting: bool = False  # CARRIER only


class DeploymentConfig(BaseModel):
    """Top-level deployment profile."""

    deployment_type: str = "mga"
    enabled_modules: ModuleConfig = ModuleConfig()
    multi_lob: bool = False
    lines_of_business: list[str] = ["cyber"]
    territories: list[str] = ["US"]


CARRIER_PROFILE = DeploymentConfig(
    deployment_type="carrier",
    enabled_modules=ModuleConfig(
        actuarial=True,
        reinsurance=True,
        mga_oversight=True,
        statutory_reporting=True,
    ),
    multi_lob=True,
    lines_of_business=["cyber", "property", "professional_liability"],
    territories=["US", "EU"],
)

MGA_PROFILE = DeploymentConfig(
    deployment_type="mga",
    enabled_modules=ModuleConfig(),
    multi_lob=False,
    lines_of_business=["cyber"],
    territories=["US"],
)
