"""Trigger escalations by creating submissions and claims that exceed authority limits.

The backend defaults to dev mode (no auth → CUO role), which never triggers
escalations.  This script:

1. Starts a backend instance with ``OPENINSURE_REQUIRE_AUTH=true`` so JWT-based
   role overrides are honoured.
2. Creates submissions using low-authority roles (UW Analyst, Claims Adjuster)
   with amounts that exceed their limits.
3. The authority engine returns ESCALATE → items appear in the escalation queue.

Usage::

    python -m src.scripts.trigger_escalations          # auto-start backend
    python -m src.scripts.trigger_escalations --url http://localhost:8000  # existing backend
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "trigger-escalation-key"


def _set_base_url(url: str) -> None:
    global BASE_URL  # noqa: PLW0603
    BASE_URL = url


# ---------------------------------------------------------------------------
# JWT helpers (backend decodes without signature verification)
# ---------------------------------------------------------------------------


def _make_jwt(payload: dict[str, Any]) -> str:
    """Craft a JWT token with the given payload (no signature verification)."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.nosig"


UW_ANALYST_TOKEN = _make_jwt(
    {
        "sub": "uw-analyst-user",
        "email": "analyst@openinsure.local",
        "name": "UW Analyst (escalation test)",
        "roles": ["openinsure-uw-analyst"],
    }
)

CLAIMS_ADJUSTER_TOKEN = _make_jwt(
    {
        "sub": "claims-adjuster-user",
        "email": "adjuster@openinsure.local",
        "name": "Claims Adjuster (escalation test)",
        "roles": ["openinsure-claims-adjuster"],
    }
)

CUO_TOKEN = _make_jwt(
    {
        "sub": "cuo-user",
        "email": "cuo@openinsure.local",
        "name": "CUO (escalation test)",
        "roles": ["openinsure-cuo"],
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(client: httpx.Client, path: str, *, body: dict | None = None, token: str | None = None) -> httpx.Response:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(f"{BASE_URL}/api/v1{path}", json=body, headers=headers, timeout=30)


def _get(client: httpx.Client, path: str, *, token: str | None = None) -> httpx.Response:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.get(f"{BASE_URL}/api/v1{path}", headers=headers, timeout=30)


def _wait_for_backend(timeout: int = 30) -> bool:
    """Poll the backend until it responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=3)
            if resp.status_code < 500:
                return True
        except httpx.ConnectError:
            pass
        time.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------


def run(base_url: str, *, start_backend: bool = True) -> None:
    _set_base_url(base_url)

    backend_proc: subprocess.Popen | None = None  # type: ignore[type-arg]

    if start_backend:
        print("▶ Starting backend with REQUIRE_AUTH=true …")
        env = {**os.environ, "OPENINSURE_REQUIRE_AUTH": "true", "OPENINSURE_API_KEY": API_KEY}
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "openinsure.main:app", "--host", "127.0.0.1", "--port", "8000"],
            env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        if not _wait_for_backend(30):
            stderr_out = ""
            if backend_proc.stderr:
                stderr_out = backend_proc.stderr.read().decode(errors="replace")[-500:]
            print(f"✗ Backend did not start in time\n{stderr_out}")
            backend_proc.terminate()
            sys.exit(1)
        print("  Backend ready on", BASE_URL)

    try:
        _run_workflow()
    finally:
        if backend_proc:
            print("\n▶ Stopping backend …")
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_proc.kill()
            print("  Backend stopped.")


def _run_workflow() -> None:
    with httpx.Client() as client:
        # ---------------------------------------------------------------
        # Phase 1: Create a small submission → bind → get policy for claims
        # ---------------------------------------------------------------
        print("\n── Phase 1: Create policy (small submission, CUO authority) ──")
        resp = _post(
            client,
            "/submissions",
            token=CUO_TOKEN,
            body={
                "applicant_name": "SmallCo Test LLC",
                "applicant_email": "test@smallco.local",
                "channel": "api",
                "line_of_business": "cyber",
                "risk_data": {
                    "annual_revenue": 500_000,
                    "employee_count": 10,
                    "industry": "Technology",
                    "security_score": 8,
                },
            },
        )
        resp.raise_for_status()
        small_sub = resp.json()
        small_sub_id = small_sub["id"]
        print(f"  Created submission {small_sub_id}")

        resp = _post(client, f"/submissions/{small_sub_id}/triage", token=CUO_TOKEN)
        if resp.status_code == 200:
            print(f"  Triaged → {resp.json().get('status', resp.json().get('recommendation', 'ok'))}")
        else:
            # In-memory repo state-machine bug: status updated before validation runs.
            # The submission IS in "underwriting" state despite the 500.
            print(f"  Triaged (status={resp.status_code}, continuing — in-memory state updated)")

        # Quote with CUO (no escalation for small premium)
        resp = _post(client, f"/submissions/{small_sub_id}/quote", token=CUO_TOKEN)
        if resp.status_code in (200, 201):
            quote_data = resp.json()
            premium = quote_data.get("premium", "?")
            print(f"  Quoted → premium=${premium}")
        else:
            print(f"  Quote returned {resp.status_code}: {resp.text[:200]}")

        # Bind with CUO
        resp = _post(client, f"/submissions/{small_sub_id}/bind", token=CUO_TOKEN)
        if resp.status_code in (200, 201):
            bind_data = resp.json()
            policy_id = bind_data.get("policy_id", "")
            print(f"  Bound → policy {policy_id}")
        else:
            print(f"  Bind returned {resp.status_code}: {resp.text[:200]}")
            policy_id = ""

        # ---------------------------------------------------------------
        # Phase 2: Large submission → quote as UW Analyst → ESCALATE
        # ---------------------------------------------------------------
        print("\n── Phase 2: Trigger quote escalation (large submission, UW Analyst) ──")
        resp = _post(
            client,
            "/submissions",
            token=CUO_TOKEN,
            body={
                "applicant_name": "MegaCorp International Ltd",
                "applicant_email": "risk@megacorp.global",
                "channel": "broker",
                "line_of_business": "cyber",
                "risk_data": {
                    "annual_revenue": 200_000_000,
                    "employee_count": 5_000,
                    "industry": "Financial Services",
                    "security_score": 6,
                    "prior_incidents": 1,
                    "requested_limit": 10_000_000,
                    "requested_deductible": 100_000,
                },
                "metadata": {"broker_id": "BRK-ESC-001", "source": "escalation_test"},
            },
        )
        resp.raise_for_status()
        large_sub = resp.json()
        large_sub_id = large_sub["id"]
        print(f"  Created submission {large_sub_id}")

        resp = _post(client, f"/submissions/{large_sub_id}/triage", token=CUO_TOKEN)
        if resp.status_code == 200:
            print(f"  Triaged → {resp.json().get('status', resp.json().get('recommendation', 'ok'))}")
        else:
            print(f"  Triaged (status={resp.status_code}, continuing)")

        # Quote with UW Analyst → premium should exceed $50K → ESCALATE
        # NOTE: without Foundry, local fallback returns $5K (below $50K threshold).
        # Escalation only triggers when Foundry is live and returns a realistic premium.
        resp = _post(client, f"/submissions/{large_sub_id}/quote", token=UW_ANALYST_TOKEN)
        if resp.status_code == 202:
            esc_data = resp.json()
            print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
            print(f"    Reason: {esc_data.get('reason', '?')}")
            print(f"    Required role: {esc_data.get('required_role', '?')}")
        else:
            data = resp.json()
            prem = data.get("premium", "?")
            print(f"  ℹ Quote returned ${prem} (below $50K threshold — Foundry not available)")

        # Second large submission (different LOB)
        resp = _post(
            client,
            "/submissions",
            token=CUO_TOKEN,
            body={
                "applicant_name": "GlobalTech Solutions Inc",
                "applicant_email": "underwriting@globaltech.io",
                "channel": "api",
                "line_of_business": "tech_eo",
                "risk_data": {
                    "annual_revenue": 150_000_000,
                    "employee_count": 3_000,
                    "industry": "Technology",
                    "security_score": 5,
                    "prior_incidents": 2,
                    "requested_limit": 5_000_000,
                },
                "metadata": {"source": "escalation_test"},
            },
        )
        resp.raise_for_status()
        sub2 = resp.json()
        sub2_id = sub2["id"]
        print(f"\n  Created submission {sub2_id} (Tech E&O)")

        resp = _post(client, f"/submissions/{sub2_id}/triage", token=CUO_TOKEN)
        if resp.status_code == 200:
            print(f"  Triaged → {resp.json().get('status', resp.json().get('recommendation', 'ok'))}")
        else:
            print(f"  Triaged (status={resp.status_code}, continuing)")

        resp = _post(client, f"/submissions/{sub2_id}/quote", token=UW_ANALYST_TOKEN)
        if resp.status_code == 202:
            esc_data = resp.json()
            print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
            print(f"    Reason: {esc_data.get('reason', '?')}")
        else:
            data = resp.json()
            prem = data.get("premium", "?")
            print(f"  ℹ Quote returned ${prem} (below $50K threshold — Foundry not available)")

        # ---------------------------------------------------------------
        # Phase 3: Claim with large reserve → Claims Adjuster → ESCALATE
        # ---------------------------------------------------------------
        print("\n── Phase 3: Trigger reserve escalation (large claim, Claims Adjuster) ──")
        if not policy_id:
            print("  ⚠ Skipping — no policy available from Phase 1")
        else:
            resp = _post(
                client,
                "/claims",
                token=CUO_TOKEN,
                body={
                    "policy_id": policy_id,
                    "claim_type": "ransomware",
                    "description": (
                        "Major ransomware attack encrypted all production databases and "
                        "backup systems. Business operations halted for 72+ hours. "
                        "Third-party forensics firm engaged. Estimated data exfiltration "
                        "of 500K customer records."
                    ),
                    "date_of_loss": "2026-06-15",
                    "reported_by": "CISO",
                    "contact_email": "security@smallco.local",
                    "metadata": {
                        "systems_affected": 25,
                        "estimated_downtime_hours": 72,
                        "data_records_exposed": 500_000,
                        "source": "escalation_test",
                    },
                },
            )
            resp.raise_for_status()
            claim = resp.json()
            claim_id = claim["id"]
            print(f"  Created claim {claim_id}")

            # Set reserve >$100K with Claims Adjuster → ESCALATE
            resp = _post(
                client,
                f"/claims/{claim_id}/reserve",
                token=CLAIMS_ADJUSTER_TOKEN,
                body={
                    "category": "indemnity",
                    "amount": 150_000,
                    "currency": "USD",
                    "notes": "Initial reserve based on ransomware severity and data exposure scope",
                },
            )
            if resp.status_code == 202:
                esc_data = resp.json()
                print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
                print(f"    Reason: {esc_data.get('reason', '?')}")
                print(f"    Required role: {esc_data.get('required_role', '?')}")
            else:
                print(f"  ⚠ Reserve returned {resp.status_code}: {resp.text[:200]}")

            # Second claim — business interruption
            resp = _post(
                client,
                "/claims",
                token=CUO_TOKEN,
                body={
                    "policy_id": policy_id,
                    "claim_type": "business_interruption",
                    "description": (
                        "Extended outage caused by ransomware attack. Revenue loss estimated "
                        "at $2M over 10-day recovery period. Customer SLA penalties triggered."
                    ),
                    "date_of_loss": "2026-06-15",
                    "reported_by": "CFO",
                    "metadata": {"source": "escalation_test"},
                },
            )
            resp.raise_for_status()
            claim2 = resp.json()
            claim2_id = claim2["id"]
            print(f"\n  Created claim {claim2_id} (business interruption)")

            resp = _post(
                client,
                f"/claims/{claim2_id}/reserve",
                token=CLAIMS_ADJUSTER_TOKEN,
                body={
                    "category": "indemnity",
                    "amount": 250_000,
                    "currency": "USD",
                    "notes": "Revenue loss reserve — 10-day outage at $200K/day",
                },
            )
            if resp.status_code == 202:
                esc_data = resp.json()
                print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
                print(f"    Reason: {esc_data.get('reason', '?')}")
            else:
                print(f"  ⚠ Reserve returned {resp.status_code}: {resp.text[:200]}")

        # ---------------------------------------------------------------
        # Phase 4: Verify escalation queue
        # ---------------------------------------------------------------
        print("\n── Phase 4: Verify escalation queue ──")
        resp = _get(client, "/escalations?status=pending", token=CUO_TOKEN)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            print(f"  Pending escalations: {len(items)}")
            for item in items:
                print(
                    f"    • [{item['action']}] {item['entity_type']} {item['entity_id']}"
                    f" — ${item['amount']:,.0f} — requires {item['required_role']}"
                )
        else:
            print(f"  ⚠ Could not fetch escalations: {resp.status_code}")

        resp = _get(client, "/escalations/count", token=CUO_TOKEN)
        if resp.status_code == 200:
            print(f"  Total pending: {resp.json().get('pending', '?')}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger escalations in the OpenInsure backend")
    parser.add_argument("--url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--no-start", action="store_true", help="Don't start/stop the backend (use existing)")
    args = parser.parse_args()
    run(args.url, start_backend=not args.no_start)
