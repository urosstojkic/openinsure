"""Seed Cosmos DB with ALL OpenInsure knowledge — the definitive loader.

Reads from two sources:
  1. YAML files in ``knowledge/``  (products, guidelines, regulatory)
  2. Rich in-memory data from ``knowledge_store.py`` (industry profiles,
     jurisdiction rules, claims precedents, compliance rules, billing, workflow)

Uploads every document to the ``insurance-graph`` container with a proper
``entityType`` partition key so Cosmos is the **single source of truth**.

Authentication: tries ``DefaultAzureCredential`` (RBAC) first; if
``OPENINSURE_COSMOS_KEY`` is set, uses key-based auth as a fallback.

Usage:
    python src/scripts/seed_cosmos_knowledge.py              # seed everything
    python src/scripts/seed_cosmos_knowledge.py --dry-run     # preview only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"

# Cosmos DB config
COSMOS_ENDPOINT = os.environ.get(
    "OPENINSURE_COSMOS_ENDPOINT",
    "https://openinsure-dev-cosmos-knshtzbusr734.documents.azure.com:443/",
)
COSMOS_DATABASE = os.environ.get("OPENINSURE_COSMOS_DATABASE_NAME", "openinsure-knowledge")
COSMOS_CONTAINER = os.environ.get("OPENINSURE_COSMOS_GRAPH_NAME", "insurance-graph")
COSMOS_KEY = os.environ.get("OPENINSURE_COSMOS_KEY", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC).isoformat()


def _safe_scalars(data: dict[str, Any]) -> dict[str, Any]:
    """Extract only JSON-serialisable scalar fields for top-level Cosmos props."""
    return {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool))}


# ---------------------------------------------------------------------------
# Source 1: YAML files
# ---------------------------------------------------------------------------


def _collect_yaml_docs() -> list[dict[str, Any]]:
    """Parse all YAML files under knowledge/ into Cosmos documents."""
    docs: list[dict[str, Any]] = []

    if not KNOWLEDGE_DIR.is_dir():
        print(f"  ⚠  knowledge/ directory not found at {KNOWLEDGE_DIR}")
        return docs

    # Products
    for yaml_file in sorted((KNOWLEDGE_DIR / "products").glob("*.yaml")):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        product = data.get("product", data)
        doc = {
            "id": f"product-{product.get('code', yaml_file.stem)}",
            "entityType": "product",
            "content": yaml.dump(data, default_flow_style=False),
            "updated_at": _NOW,
            **_safe_scalars(product),
        }
        docs.append(doc)

    # Guidelines
    for yaml_file in sorted((KNOWLEDGE_DIR / "guidelines").glob("*.yaml")):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        for key, content in data.items():
            doc = {
                "id": f"guideline-yaml-{yaml_file.stem}-{key}",
                "entityType": "guideline",
                "lob": content.get("line_of_business", "cyber") if isinstance(content, dict) else "cyber",
                "content": yaml.dump({key: content}, default_flow_style=False),
                "source": f"yaml/{yaml_file.name}",
                "updated_at": _NOW,
            }
            if isinstance(content, dict):
                doc.update(_safe_scalars(content))
            docs.append(doc)

    # Regulatory
    for yaml_file in sorted((KNOWLEDGE_DIR / "regulatory").glob("*.yaml")):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        for key, content in data.items():
            doc = {
                "id": f"regulatory-{yaml_file.stem}-{key}",
                "entityType": "regulatory",
                "jurisdiction": "US",
                "content": yaml.dump({key: content}, default_flow_style=False),
                "source": f"yaml/{yaml_file.name}",
                "updated_at": _NOW,
            }
            docs.append(doc)

    return docs


# ---------------------------------------------------------------------------
# Source 2: In-memory knowledge store data
# ---------------------------------------------------------------------------


def _collect_inmemory_docs() -> list[dict[str, Any]]:
    """Convert all in-memory knowledge store data to Cosmos documents."""
    # Import the module-level dicts directly to avoid singleton side-effects
    from openinsure.infrastructure.knowledge_store import (
        BILLING_RULES,
        CLAIMS_PRECEDENTS,
        COMPLIANCE_RULES,
        INDUSTRY_GUIDELINES,
        JURISDICTION_RULES,
        UNDERWRITING_GUIDELINES,
        WORKFLOW_RULES,
    )

    docs: list[dict[str, Any]] = []

    # Underwriting guidelines (full structured data per LOB)
    for lob, gl_data in UNDERWRITING_GUIDELINES.items():
        docs.append(
            {
                "id": f"guideline-{lob}",
                "entityType": "guideline",
                "lob": lob,
                "content": json.dumps(gl_data, default=str),
                "source": "knowledge_store",
                "updated_at": _NOW,
                # Flatten appetite for search
                **_safe_scalars(gl_data.get("appetite", {})),
            }
        )

        # Rating factors as separate doc
        rf = gl_data.get("rating_factors")
        if rf:
            docs.append(
                {
                    "id": f"rating-factor-{lob}",
                    "entityType": "rating_factor",
                    "lob": lob,
                    "content": json.dumps(rf, default=str),
                    "source": "knowledge_store",
                    "updated_at": _NOW,
                    **_safe_scalars(rf),
                }
            )

        # Coverage options as separate docs
        opts = gl_data.get("coverage_options", [])
        for i, opt in enumerate(opts):
            name_slug = opt.get("name", f"opt-{i}").lower().replace(" ", "-").replace("/", "-")
            docs.append(
                {
                    "id": f"coverage-option-{lob}-{name_slug}",
                    "entityType": "coverage_option",
                    "lob": lob,
                    "content": json.dumps(opt, default=str),
                    "source": "knowledge_store",
                    "updated_at": _NOW,
                    **_safe_scalars(opt),
                }
            )

    # Claims precedents
    for claim_type, prec_data in CLAIMS_PRECEDENTS.items():
        docs.append(
            {
                "id": f"claims-precedent-{claim_type}",
                "entityType": "claims_precedent",
                "claim_type": claim_type,
                "content": json.dumps(prec_data, default=str),
                "source": "knowledge_store",
                "updated_at": _NOW,
                **_safe_scalars(prec_data),
            }
        )

    # Compliance rules
    for framework, rule_data in COMPLIANCE_RULES.items():
        docs.append(
            {
                "id": f"compliance-rule-{framework}",
                "entityType": "compliance_rule",
                "framework": framework,
                "content": json.dumps(rule_data, default=str),
                "source": "knowledge_store",
                "updated_at": _NOW,
                **_safe_scalars(rule_data),
            }
        )

    # Industry profiles
    for industry, profile in INDUSTRY_GUIDELINES.items():
        docs.append(
            {
                "id": f"industry-profile-{industry}",
                "entityType": "industry_profile",
                "industry": industry,
                "content": json.dumps(profile, default=str),
                "source": "knowledge_store",
                "updated_at": _NOW,
                **_safe_scalars(profile),
            }
        )

    # Jurisdiction rules
    for territory, rules in JURISDICTION_RULES.items():
        docs.append(
            {
                "id": f"jurisdiction-rule-{territory.lower()}",
                "entityType": "jurisdiction_rule",
                "territory": territory,
                "content": json.dumps(rules, default=str),
                "source": "knowledge_store",
                "updated_at": _NOW,
                **_safe_scalars(rules),
            }
        )

    # Billing rules (single doc)
    docs.append(
        {
            "id": "billing-rules",
            "entityType": "billing_rule",
            "content": json.dumps(BILLING_RULES, default=str),
            "source": "knowledge_store",
            "updated_at": _NOW,
        }
    )

    # Workflow rules (single doc)
    docs.append(
        {
            "id": "workflow-rules",
            "entityType": "workflow_rule",
            "content": json.dumps(WORKFLOW_RULES, default=str),
            "source": "knowledge_store",
            "updated_at": _NOW,
        }
    )

    return docs


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def _get_container():
    """Return a Cosmos DB container client."""
    from azure.cosmos import CosmosClient

    if COSMOS_KEY:
        client = CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)
    else:
        from azure.identity import DefaultAzureCredential

        client = CosmosClient(COSMOS_ENDPOINT, credential=DefaultAzureCredential())

    db = client.get_database_client(COSMOS_DATABASE)
    return db.get_container_client(COSMOS_CONTAINER)


def _upload(documents: list[dict[str, Any]]) -> None:
    """Upload documents to Cosmos DB."""
    container = _get_container()
    succeeded = 0
    failed = 0
    for doc in documents:
        try:
            container.upsert_item(doc)
            succeeded += 1
        except Exception as exc:
            failed += 1
            print(f"  ✗ {doc['id']}: {exc}")

    print(f"\n  ✅ {succeeded} documents uploaded, {failed} failed")


def _dry_run(documents: list[dict[str, Any]]) -> None:
    """Print what would be seeded without making API calls."""
    print(f"\n{'=' * 60}")
    print(f"DRY RUN — {len(documents)} documents would be seeded")
    print(f"Target: {COSMOS_ENDPOINT}")
    print(f"Database: {COSMOS_DATABASE}")
    print(f"Container: {COSMOS_CONTAINER}")
    print(f"{'=' * 60}\n")

    by_type: dict[str, int] = {}
    for doc in documents:
        et = doc.get("entityType", "unknown")
        by_type[et] = by_type.get(et, 0) + 1

    for et, count in sorted(by_type.items()):
        print(f"  {et:25s}  {count:3d} documents")

    print(f"\n  Total: {len(documents)} documents")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Cosmos DB with all OpenInsure knowledge.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading.")
    args = parser.parse_args()

    print("Collecting knowledge documents …\n")

    yaml_docs = _collect_yaml_docs()
    print(f"  📁 YAML files:       {len(yaml_docs)} documents")

    # Ensure src/ is on the path for imports
    src_dir = str(ROOT_DIR / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    inmem_docs = _collect_inmemory_docs()
    print(f"  🧠 In-memory store:  {len(inmem_docs)} documents")

    all_docs = yaml_docs + inmem_docs
    print(f"\n  Total: {len(all_docs)} documents\n")

    if not all_docs:
        print("Nothing to seed.")
        return

    if args.dry_run:
        _dry_run(all_docs)
        return

    print("Uploading to Cosmos DB …")
    _upload(all_docs)
    print("\n✅ Cosmos DB seeding complete.")


if __name__ == "__main__":
    main()
