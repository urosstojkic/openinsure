"""Trigger escalations by creating submissions and claims that exceed authority limits.

The default API key (``dev-key-change-me``) maps to the **CUO** role, which has
high authority limits and will never trigger ``ESCALATE``.  To trigger real
escalations the script:

1. Creates submissions and claims using the API key (CUO) for setup.
2. Uses **unsigned JWT tokens** with low-authority roles (UW Analyst, Claims
   Adjuster) to attempt quote/reserve operations that exceed their limits.
3. If the backend is in dev mode (``require_auth=false`` → always CUO), JWT
   role overrides are ignored.  In that case the script falls back to direct
   escalation-queue injection (Phase 4).
4. Verifies the escalation queue via ``GET /escalations``.

Usage::

    # Against a remote backend (no local start)
    python -m src.scripts.trigger_escalations \\
        --url os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000") \\
        --no-start

    # Auto-start local backend with auth enabled
    python -m src.scripts.trigger_escalations
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
API_KEY = "dev-key-change-me"

DEFAULT_REMOTE_URL = os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")"


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


def _headers_apikey() -> dict[str, str]:
    """Return headers for API-key auth (CUO role)."""
    return {"X-API-Key": API_KEY}


def _headers_jwt(token: str) -> dict[str, str]:
    """Return headers for JWT auth (role from token claims, NO API key)."""
    return {"Authorization": f"Bearer {token}"}


def _post(
    client: httpx.Client,
    path: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return client.post(
        f"{BASE_URL}/api/v1{path}",
        json=body,
        headers=headers or _headers_apikey(),
        timeout=60,
    )


def _get(
    client: httpx.Client,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return client.get(
        f"{BASE_URL}/api/v1{path}",
        headers=headers or _headers_apikey(),
        timeout=60,
    )


def _wait_for_backend(timeout: int = 30) -> bool:
    """Poll the backend until it responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=5)
            if resp.status_code < 500:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(1)
    return False


def _detect_auth_mode(client: httpx.Client) -> str:
    """Detect whether the backend requires auth.

    Returns ``"auth_required"`` if 401 without credentials,
    ``"dev_mode"`` if requests succeed without credentials.
    """
    try:
        resp = client.get(f"{BASE_URL}/api/v1/submissions?limit=1", timeout=10)
        if resp.status_code == 401:
            return "auth_required"
        return "dev_mode"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------


def run(base_url: str, *, start_backend: bool = True) -> None:
    _set_base_url(base_url)

    backend_proc: subprocess.Popen | None = None  # type: ignore[type-arg]

    if start_backend:
        print("▶ Starting backend with REQUIRE_AUTH=true …")
        env = {
            **os.environ,
            "OPENINSURE_REQUIRE_AUTH": "true",
            "OPENINSURE_API_KEY": API_KEY,
        }
        backend_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "openinsure.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
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
        # Detect auth mode
        auth_mode = _detect_auth_mode(client)
        print(f"ℹ Backend auth mode: {auth_mode}")
        if auth_mode == "auth_required":
            print("  JWT role overrides will work (low-authority roles trigger escalations)")
        else:
            print("  Dev mode — all requests resolve to CUO role regardless of headers")
            print("  Will attempt JWT approach first, then fall back to direct injection")

        escalation_count = 0

        # ---------------------------------------------------------------
        # Phase 1: Create a small submission → bind → get policy for claims
        # ---------------------------------------------------------------
        print("\n── Phase 1: Create policy (small submission via API key / CUO) ──")
        resp = _post(
            client,
            "/submissions",
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

        resp = _post(client, f"/submissions/{small_sub_id}/triage")
        print(f"  Triage → {resp.status_code}")

        resp = _post(client, f"/submissions/{small_sub_id}/quote")
        if resp.status_code in (200, 201):
            premium = resp.json().get("premium", "?")
            print(f"  Quoted → premium=${premium}")
        else:
            print(f"  Quote → {resp.status_code}: {resp.text[:200]}")

        resp = _post(client, f"/submissions/{small_sub_id}/bind")
        policy_id = ""
        if resp.status_code in (200, 201):
            policy_id = resp.json().get("policy_id", "")
            print(f"  Bound → policy {policy_id}")
        else:
            print(f"  Bind → {resp.status_code}: {resp.text[:200]}")

        # Also try to find an existing policy if binding failed
        if not policy_id:
            resp = _get(client, "/policies?limit=5")
            if resp.status_code == 200:
                policies = resp.json().get("items", resp.json() if isinstance(resp.json(), list) else [])
                for p in policies:
                    if p.get("status", "").lower() in ("active", "bound"):
                        policy_id = p["id"]
                        print(f"  Using existing policy {policy_id}")
                        break

        # ---------------------------------------------------------------
        # Phase 2: Large submission → quote with low-authority role → ESCALATE
        # ---------------------------------------------------------------
        print("\n── Phase 2: Trigger quote escalation (large submission) ──")
        print("  Authority: UW Analyst auto-quote limit = $50K")
        print("  Strategy: $500M revenue company → Foundry should return high premium")

        resp = _post(
            client,
            "/submissions",
            body={
                "applicant_name": "MegaCorp International Ltd",
                "applicant_email": "risk@megacorp.global",
                "channel": "broker",
                "line_of_business": "cyber",
                "risk_data": {
                    "annual_revenue": 500_000_000,
                    "employee_count": 5_000,
                    "industry": "Financial Services",
                    "security_score": 4,
                    "prior_incidents": 3,
                    "requested_limit": 25_000_000,
                    "requested_deductible": 250_000,
                },
                "metadata": {"broker_id": "BRK-ESC-001", "source": "escalation_test"},
            },
        )
        resp.raise_for_status()
        large_sub = resp.json()
        large_sub_id = large_sub["id"]
        print(f"  Created submission {large_sub_id}")

        # Triage with API key (CUO)
        resp = _post(client, f"/submissions/{large_sub_id}/triage")
        print(f"  Triage → {resp.status_code}")

        # Quote with UW Analyst JWT (no API key) → premium > $50K should ESCALATE
        resp = _post(
            client,
            f"/submissions/{large_sub_id}/quote",
            headers=_headers_jwt(UW_ANALYST_TOKEN),
        )
        if resp.status_code == 202:
            esc_data = resp.json()
            escalation_count += 1
            print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
            print(f"    Reason: {esc_data.get('reason', '?')}")
            print(f"    Required role: {esc_data.get('required_role', '?')}")
        elif resp.status_code in (200, 201):
            data = resp.json()
            prem = data.get("premium", "?")
            authority = data.get("authority_decision", "?")
            print(f"  Quote returned {resp.status_code}: premium=${prem}, authority={authority}")
            print("  (premium may be below $50K threshold, or backend in dev mode → CUO role)")
        else:
            print(f"  Quote → {resp.status_code}: {resp.text[:300]}")

        # Second large submission
        resp = _post(
            client,
            "/submissions",
            body={
                "applicant_name": "GlobalTech Solutions Inc",
                "applicant_email": "underwriting@globaltech.io",
                "channel": "api",
                "line_of_business": "tech_eo",
                "risk_data": {
                    "annual_revenue": 300_000_000,
                    "employee_count": 8_000,
                    "industry": "Technology",
                    "security_score": 3,
                    "prior_incidents": 5,
                    "requested_limit": 15_000_000,
                },
                "metadata": {"source": "escalation_test"},
            },
        )
        resp.raise_for_status()
        sub2 = resp.json()
        sub2_id = sub2["id"]
        print(f"\n  Created submission {sub2_id} (Tech E&O)")

        resp = _post(client, f"/submissions/{sub2_id}/triage")
        print(f"  Triage → {resp.status_code}")

        resp = _post(
            client,
            f"/submissions/{sub2_id}/quote",
            headers=_headers_jwt(UW_ANALYST_TOKEN),
        )
        if resp.status_code == 202:
            esc_data = resp.json()
            escalation_count += 1
            print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
            print(f"    Reason: {esc_data.get('reason', '?')}")
        elif resp.status_code in (200, 201):
            data = resp.json()
            prem = data.get("premium", "?")
            print(f"  Quote → premium=${prem} (no escalation)")
        else:
            print(f"  Quote → {resp.status_code}: {resp.text[:300]}")

        # ---------------------------------------------------------------
        # Phase 3: Large reserve on claim → Claims Adjuster → ESCALATE
        # ---------------------------------------------------------------
        print("\n── Phase 3: Trigger reserve escalation ($200K reserve, Claims Adjuster) ──")
        print("  Authority: Claims Adjuster reserve limit = $100K")

        if not policy_id:
            print("  ⚠ No policy available — trying to find existing claims …")
            resp = _get(client, "/claims?limit=5")
            if resp.status_code == 200:
                claims = resp.json().get("items", resp.json() if isinstance(resp.json(), list) else [])
                if claims:
                    claim_id = claims[0]["id"]
                    print(f"  Using existing claim {claim_id}")
                else:
                    print("  ⚠ No existing claims found. Skipping reserve escalation.")
                    claim_id = ""
            else:
                claim_id = ""
        else:
            # Create a claim on the policy
            resp = _post(
                client,
                "/claims",
                body={
                    "policy_id": policy_id,
                    "claim_type": "ransomware",
                    "description": (
                        "Major ransomware attack encrypted all production databases. "
                        "Business halted for 72+ hours. 500K customer records exposed."
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
            if resp.status_code in (200, 201):
                claim_id = resp.json()["id"]
                print(f"  Created claim {claim_id}")
            else:
                print(f"  Create claim → {resp.status_code}: {resp.text[:200]}")
                claim_id = ""

        if claim_id:
            # Set reserve $200K as Claims Adjuster (limit $100K) → ESCALATE
            resp = _post(
                client,
                f"/claims/{claim_id}/reserve",
                headers=_headers_jwt(CLAIMS_ADJUSTER_TOKEN),
                body={
                    "category": "indemnity",
                    "amount": 200_000,
                    "currency": "USD",
                    "notes": "Initial reserve — ransomware severity + data exposure scope",
                },
            )
            if resp.status_code == 202:
                esc_data = resp.json()
                escalation_count += 1
                print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
                print(f"    Reason: {esc_data.get('reason', '?')}")
                print(f"    Required role: {esc_data.get('required_role', '?')}")
            else:
                print(f"  Reserve → {resp.status_code}: {resp.text[:300]}")

            # Second claim with even larger reserve
            if policy_id:
                resp = _post(
                    client,
                    "/claims",
                    body={
                        "policy_id": policy_id,
                        "claim_type": "business_interruption",
                        "description": (
                            "Extended outage from ransomware — revenue loss ~$2M "
                            "over 10-day recovery. Customer SLA penalties triggered."
                        ),
                        "date_of_loss": "2026-06-15",
                        "reported_by": "CFO",
                        "metadata": {"source": "escalation_test"},
                    },
                )
                if resp.status_code in (200, 201):
                    claim2_id = resp.json()["id"]
                    print(f"\n  Created claim {claim2_id} (business interruption)")

                    resp = _post(
                        client,
                        f"/claims/{claim2_id}/reserve",
                        headers=_headers_jwt(CLAIMS_ADJUSTER_TOKEN),
                        body={
                            "category": "indemnity",
                            "amount": 350_000,
                            "currency": "USD",
                            "notes": "Revenue loss reserve — 10-day outage at $200K/day",
                        },
                    )
                    if resp.status_code == 202:
                        esc_data = resp.json()
                        escalation_count += 1
                        print(f"  ✓ ESCALATED → {esc_data.get('escalation_id', '?')}")
                        print(f"    Reason: {esc_data.get('reason', '?')}")
                    else:
                        print(f"  Reserve → {resp.status_code}: {resp.text[:300]}")

        # ---------------------------------------------------------------
        # Phase 4: Fallback — create escalation records via POST /escalations
        # ---------------------------------------------------------------
        if escalation_count == 0:
            print("\n── Phase 4 (fallback): Create escalation records via POST /escalations ──")
            print("  No natural escalations (backend in dev mode → CUO role for all requests)")
            print("  Using admin POST /escalations endpoint to inject records …")

            escalation_records = [
                {
                    "action": "quote",
                    "entity_type": "submission",
                    "entity_id": large_sub_id,
                    "requested_by": "UW Analyst (escalation test)",
                    "requested_role": "openinsure-uw-analyst",
                    "amount": 2_250_000,
                    "required_role": "openinsure-senior-uw",
                    "reason": "Premium $2,250,000 exceeds UW Analyst auto-quote limit ($50K)",
                    "context": {"applicant": "MegaCorp International Ltd", "source": "escalation_test"},
                },
                {
                    "action": "quote",
                    "entity_type": "submission",
                    "entity_id": sub2_id,
                    "requested_by": "UW Analyst (escalation test)",
                    "requested_role": "openinsure-uw-analyst",
                    "amount": 300_000,
                    "required_role": "openinsure-senior-uw",
                    "reason": "Premium $300,000 exceeds UW Analyst auto-quote limit ($50K)",
                    "context": {"applicant": "GlobalTech Solutions Inc", "source": "escalation_test"},
                },
            ]
            if claim_id:
                escalation_records.append(
                    {
                        "action": "reserve",
                        "entity_type": "claim",
                        "entity_id": claim_id,
                        "requested_by": "Claims Adjuster (escalation test)",
                        "requested_role": "openinsure-claims-adjuster",
                        "amount": 200_000,
                        "required_role": "openinsure-claims-manager",
                        "reason": "Reserve $200,000 exceeds Claims Adjuster limit ($100K)",
                        "context": {"claim_type": "ransomware", "source": "escalation_test"},
                    }
                )
                escalation_records.append(
                    {
                        "action": "settlement",
                        "entity_type": "claim",
                        "entity_id": claim_id,
                        "requested_by": "Claims Adjuster (escalation test)",
                        "requested_role": "openinsure-claims-adjuster",
                        "amount": 150_000,
                        "required_role": "openinsure-claims-manager",
                        "reason": "Settlement $150,000 exceeds Claims Adjuster limit ($25K)",
                        "context": {"claim_type": "ransomware", "source": "escalation_test"},
                    }
                )

            for rec in escalation_records:
                resp = _post(client, "/escalations", body=rec)
                if resp.status_code == 201:
                    esc_data = resp.json()
                    escalation_count += 1
                    print(f"  ✓ Created [{rec['action']}] ${rec['amount']:,.0f} → {esc_data.get('id', '?')}")
                else:
                    print(f"  ✗ POST /escalations → {resp.status_code}: {resp.text[:200]}")

        # ---------------------------------------------------------------
        # Phase 5: Verify escalation queue
        # ---------------------------------------------------------------
        print(f"\n── Phase 5: Verify escalation queue (triggered {escalation_count} so far) ──")
        resp = _get(client, "/escalations?status=pending")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            print(f"  Pending escalations: {len(items)}")
            for item in items:
                amt = item.get("amount", 0)
                print(
                    f"    • [{item.get('action', '?')}] "
                    f"{item.get('entity_type', '?')} {item.get('entity_id', '?')}"
                    f" — ${amt:,.0f} — requires {item.get('required_role', '?')}"
                )
            if not items:
                print("  ⚠ Queue is empty — backend is likely in dev mode (CUO for all requests)")
                print("    To trigger escalations, start backend with OPENINSURE_REQUIRE_AUTH=true")
        else:
            print(f"  ⚠ Could not fetch escalations: {resp.status_code}: {resp.text[:200]}")

        resp = _get(client, "/escalations/count")
        if resp.status_code == 200:
            print(f"  Escalation count: {resp.json()}")

        # ---------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------
        print("\n── Summary ──")
        print(f"  Escalations triggered this run: {escalation_count}")
        if escalation_count > 0:
            print("  ✓ Escalation queue populated successfully")
        else:
            print("  ✗ No escalations triggered")
            print("  Likely cause: backend in dev mode (require_auth=false) → all users get CUO role")
            print("  Fix: Set OPENINSURE_REQUIRE_AUTH=true on the backend deployment")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger escalations in the OpenInsure backend")
    parser.add_argument(
        "--url",
        default=DEFAULT_REMOTE_URL,
        help="Backend base URL (default: remote Azure deployment)",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Don't start/stop the backend (use existing)",
    )
    parser.add_argument(
        "--api-key",
        default=API_KEY,
        help="API key for CUO-level operations",
    )
    args = parser.parse_args()
    if args.api_key:
        API_KEY = args.api_key
    run(args.url, start_backend=not args.no_start)
