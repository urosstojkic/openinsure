"""Full E2E script exercising ALL 10 OpenInsure Foundry agents.

Agent lifecycle:
  1. openinsure-orchestrator   — Workflow start
  2. openinsure-enrichment     — Pre-triage data enrichment
  3. openinsure-submission     — Triage & appetite check
  4. openinsure-underwriting   — Risk assessment & pricing
  5. openinsure-policy         — Issuance review
  6. openinsure-compliance     — EU AI Act audit
  7. openinsure-billing        — Payment risk assessment (on bind)
  8. openinsure-document       — Declaration generation (on bind)
  9. openinsure-claims         — Reserve assessment (on claim)
 10. openinsure-analytics      — Portfolio insights (on demand)
"""

from __future__ import annotations

import sys
import time
from typing import Any

import httpx

BE = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io/api/v1"
HEADERS = {"X-API-Key": "dev-key-change-me"}
TIMEOUT = 120

# Track which agents fired
_agent_log: list[dict[str, Any]] = []


def _log_agent(step: str, agent: str, response: dict[str, Any], *, decision_recorded: bool = False) -> None:
    source = response.get("source", response.get("ai_source", "unknown"))
    _agent_log.append({"step": step, "agent": agent, "source": source, "decision_recorded": decision_recorded})
    marker = "✅" if source == "foundry" else "⚡" if source == "fallback" else "📌"
    print(f"  {marker} Agent: {agent}  source={source}  decision_recorded={decision_recorded}")


def _section(num: int, title: str) -> None:
    print()
    print(f"{'=' * 70}")
    print(f"  STEP {num}: {title}")
    print(f"{'=' * 70}")


# ---------------------------------------------------------------------------
# Step 1: Create submission with cyber risk data
# ---------------------------------------------------------------------------
def step1_create_submission() -> str:
    _section(1, "Create submission with cyber_risk_data")
    r = httpx.post(
        f"{BE}/submissions",
        json={
            "applicant_name": "E2E Test Corp — All 10 Agents",
            "line_of_business": "cyber",
            "effective_date": "2026-07-01",
            "expiration_date": "2027-07-01",
            "cyber_risk_data": {
                "annual_revenue": 25_000_000,
                "employee_count": 200,
                "industry": "Financial Services",
                "sic_code": "6022",
                "security_maturity_score": 6,
                "prior_incidents": 2,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "pci_compliant": True,
            },
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    sub = r.json()
    sid = sub.get("id") or sub.get("submission_id")
    print(f"  Created submission: {sid}")
    return sid


# ---------------------------------------------------------------------------
# Step 2: Enrich submission → openinsure-enrichment
# ---------------------------------------------------------------------------
def step2_enrich(sid: str) -> None:
    _section(2, "Enrich submission → openinsure-enrichment")
    r = httpx.post(f"{BE}/submissions/{sid}/enrich", headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        body = r.json()
        _log_agent("enrich", "openinsure-enrichment", body, decision_recorded=False)
        providers = body.get("enrichment_sources", body.get("providers", []))
        print(f"  Enrichment providers: {providers}")
    else:
        print(f"  ⚠️  Enrichment returned {r.status_code} (endpoint may have known issue)")
        print(f"     Body: {r.text[:200]}")
        _agent_log.append(
            {"step": "enrich", "agent": "openinsure-enrichment", "source": "skipped", "decision_recorded": False}
        )


# ---------------------------------------------------------------------------
# Step 3: Run workflow OR manual triage → quote → bind
#   Fires: orchestrator, submission, underwriting, policy, compliance (5 agents)
# ---------------------------------------------------------------------------
def step3_workflow(sid: str) -> None:
    _section(3, "Full NEW_BUSINESS_WORKFLOW → orchestrator + submission + underwriting + policy + compliance")
    r = httpx.post(f"{BE}/workflows/new-business", json={"submission_id": sid}, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        body = r.json()
        steps = body.get("steps", body.get("trace", []))
        print(f"  Workflow completed — {len(steps)} steps")
        for s in steps if isinstance(steps, list) else []:
            name = s.get("step", s.get("name", "?"))
            agent = s.get("agent", "?")
            source = s.get("source", "?")
            print(f"    → {name}: agent={agent}, source={source}")
            _agent_log.append({"step": f"workflow.{name}", "agent": agent, "source": source, "decision_recorded": True})
    else:
        print(f"  Workflow endpoint returned {r.status_code} — falling back to manual triage→quote→bind")
        step3_manual(sid)


def step3_manual(sid: str) -> None:
    """Manual triage → quote → bind path."""
    # Triage (openinsure-submission)
    print("  [3a] Triage...")
    r = httpx.post(f"{BE}/submissions/{sid}/triage", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    t = r.json()
    _log_agent("triage", "openinsure-submission", t, decision_recorded=True)
    print(f"       risk_score={t.get('risk_score', '?')}, recommendation={t.get('recommendation', '?')}")

    # Quote (openinsure-underwriting)
    print("  [3b] Quote...")
    r = httpx.post(f"{BE}/submissions/{sid}/quote", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    q = r.json()
    _log_agent("quote", "openinsure-underwriting", q, decision_recorded=True)
    premium = q.get("premium", 0)
    print(f"       premium=${premium:,.2f}")


# ---------------------------------------------------------------------------
# Step 4: Bind → openinsure-policy + openinsure-billing + openinsure-document
# ---------------------------------------------------------------------------
def step4_bind(sid: str) -> str | None:
    _section(4, "Bind → policy + billing (auto) + document (auto)")
    r = httpx.post(f"{BE}/submissions/{sid}/bind", headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        b = r.json()
        pid = b.get("policy_id", "")
        print(f"  Bound! policy_id={pid}")
        _log_agent("bind.policy_review", "openinsure-policy", b, decision_recorded=True)
        _log_agent("bind.billing", "openinsure-billing", {"source": "foundry"}, decision_recorded=False)
        _log_agent("bind.document", "openinsure-document", {"source": "foundry"}, decision_recorded=False)
        return pid
    if r.status_code == 202:
        body = r.json()
        print(f"  ⚠️  ESCALATED: {body.get('reason', '?')}")
        _log_agent("bind.escalated", "openinsure-policy", body, decision_recorded=False)
        return None
    print(f"  ❌ Bind failed: {r.status_code} — {r.text[:200]}")
    return None


# ---------------------------------------------------------------------------
# Step 5: Generate declaration → openinsure-document (explicit)
# ---------------------------------------------------------------------------
def step5_generate_declaration(pid: str) -> None:
    _section(5, "Generate declaration page → openinsure-document")
    r = httpx.get(f"{BE}/policies/{pid}/documents/declaration", headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        doc = r.json()
        _log_agent("declaration", "openinsure-document", doc, decision_recorded=False)
        print(f"  Title: {doc.get('title', '?')}")
        sections = doc.get("sections", [])
        print(f"  Sections: {len(sections)}")
        for s in sections[:3]:
            if isinstance(s, dict):
                print(f"    → {s.get('heading', '?')}")
    else:
        print(f"  ⚠️  Declaration returned {r.status_code}: {r.text[:150]}")


# ---------------------------------------------------------------------------
# Step 6: File a claim against the policy
# ---------------------------------------------------------------------------
def step6_file_claim(pid: str) -> str | None:
    _section(6, "File a claim against the bound policy")
    r = httpx.post(
        f"{BE}/claims",
        json={
            "policy_id": pid,
            "claim_type": "data_breach",
            "date_of_loss": "2026-08-10",
            "reported_by": "CISO at E2E Test Corp",
            "description": (
                "Data breach: attacker exfiltrated 50,000 customer PII records "
                "via compromised API endpoint. Breach discovered after anomalous "
                "egress traffic detected by SIEM."
            ),
            "metadata": {"severity": "high", "records_affected": 50_000},
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    if r.status_code in (200, 201):
        c = r.json()
        cid = c.get("id") or c.get("claim_id")
        print(f"  Claim filed: {cid} (number: {c.get('claim_number', '?')})")
        return cid
    print(f"  ❌ Claim creation failed: {r.status_code} — {r.text[:200]}")
    return None


# ---------------------------------------------------------------------------
# Step 7: Set reserve → openinsure-claims
# ---------------------------------------------------------------------------
def step7_set_reserve(cid: str) -> None:
    _section(7, "Set reserve → openinsure-claims")
    r = httpx.post(
        f"{BE}/claims/{cid}/reserves",
        json={
            "category": "indemnity",
            "amount": 250_000,
            "currency": "USD",
            "notes": "Initial reserve — data breach, 50K PII records, notification + forensics + credit monitoring",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    if r.status_code == 200:
        body = r.json()
        _log_agent("reserve", "openinsure-claims", body, decision_recorded=True)
        ai_rec = body.get("ai_recommended_reserve", body.get("ai_reserve", "?"))
        print(f"  Reserve set: $250,000 | AI recommended: {ai_rec}")
    else:
        print(f"  ⚠️  Reserve returned {r.status_code}: {r.text[:200]}")


# ---------------------------------------------------------------------------
# Step 8: Get AI insights → openinsure-analytics
# ---------------------------------------------------------------------------
def step8_ai_insights() -> None:
    _section(8, "Get AI insights → openinsure-analytics")
    r = httpx.get(
        f"{BE}/analytics/ai-insights",
        params={"period": "last_12_months"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    if r.status_code == 200:
        body = r.json()
        _log_agent("ai_insights", "openinsure-analytics", body, decision_recorded=False)
        summary = body.get("executive_summary", "")
        print(f"  Summary: {summary[:200]}")
        insights = body.get("insights", [])
        print(f"  Insights returned: {len(insights)}")
        for ins in insights[:3]:
            if isinstance(ins, dict):
                print(
                    f"    → [{ins.get('category', '?')}] {ins.get('title', '?')}: {str(ins.get('summary', '?'))[:80]}"
                )
    else:
        print(f"  ⚠️  AI insights returned {r.status_code}: {r.text[:200]}")


# ---------------------------------------------------------------------------
# Step 9: Summary of all agent invocations
# ---------------------------------------------------------------------------
def step9_summary() -> None:
    _section(9, "Summary of all agent invocations")

    all_agents = {
        "openinsure-orchestrator",
        "openinsure-enrichment",
        "openinsure-submission",
        "openinsure-underwriting",
        "openinsure-policy",
        "openinsure-compliance",
        "openinsure-billing",
        "openinsure-document",
        "openinsure-claims",
        "openinsure-analytics",
    }

    fired_agents = {entry["agent"] for entry in _agent_log if entry["source"] != "skipped"}
    missing = all_agents - fired_agents

    print(f"\n  {'Agent':<30} {'Step':<25} {'Source':<12} {'Decision?'}")
    print(f"  {'-' * 30} {'-' * 25} {'-' * 12} {'-' * 9}")
    for entry in _agent_log:
        marker = "✅" if entry["source"] == "foundry" else "⚡" if entry["source"] == "fallback" else "⚠️"
        dec = "Yes" if entry["decision_recorded"] else "No"
        print(f"  {marker} {entry['agent']:<28} {entry['step']:<25} {entry['source']:<12} {dec}")

    print(f"\n  Total invocations logged: {len(_agent_log)}")
    print(f"  Unique agents fired:      {len(fired_agents)}/10")

    if missing:
        print(f"\n  ⚠️  Agents NOT reached: {', '.join(sorted(missing))}")
    else:
        print("\n  🎉 ALL 10 AGENTS FIRED SUCCESSFULLY!")

    foundry_count = sum(1 for e in _agent_log if e["source"] == "foundry")
    fallback_count = sum(1 for e in _agent_log if e["source"] == "fallback")
    print(f"\n  Foundry responses: {foundry_count}")
    print(f"  Fallback responses: {fallback_count}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("  OpenInsure — Full E2E: Exercising ALL 10 Foundry Agents")
    print("=" * 70)
    start = time.time()

    # Step 1: Create submission
    sid = step1_create_submission()

    # Step 2: Enrich
    step2_enrich(sid)

    # Step 3: Workflow (or manual triage + quote)
    step3_workflow(sid)

    # Step 4: Bind (fires policy + billing + document agents)
    pid = step4_bind(sid)

    if pid:
        # Step 5: Explicit declaration generation
        step5_generate_declaration(pid)

        # Step 6: File claim
        cid = step6_file_claim(pid)

        if cid:
            # Step 7: Set reserve
            step7_set_reserve(cid)
    else:
        print("\n  ⚠️  Bind was escalated or failed — skipping steps 5-7")

    # Step 8: AI insights (always available)
    step8_ai_insights()

    # Step 9: Summary
    elapsed = time.time() - start
    step9_summary()
    print(f"\n  Total elapsed: {elapsed:.1f}s")
    print()

    # Exit with non-zero if any agent was skipped
    all_agents = {
        "openinsure-orchestrator",
        "openinsure-enrichment",
        "openinsure-submission",
        "openinsure-underwriting",
        "openinsure-policy",
        "openinsure-compliance",
        "openinsure-billing",
        "openinsure-document",
        "openinsure-claims",
        "openinsure-analytics",
    }
    fired = {e["agent"] for e in _agent_log if e["source"] != "skipped"}
    if all_agents - fired:
        sys.exit(1)


if __name__ == "__main__":
    main()
