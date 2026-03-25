"""Set up automatic Cosmos DB → Azure AI Search synchronisation.

Creates:
  1. A **data source** in AI Search that points to the Cosmos DB container
  2. An **indexer** that auto-syncs changes on a 5-minute schedule

This means: edit knowledge in the portal → API writes to Cosmos →
indexer picks it up within 5 min → Foundry agents see it via AI Search.

Authentication for AI Search:
  - ``OPENINSURE_SEARCH_ADMIN_KEY`` (preferred for management operations)
  - Falls back to ``DefaultAzureCredential`` (needs *Search Service Contributor*)

Authentication for Cosmos DB connection string in the data source:
  - ``OPENINSURE_COSMOS_KEY`` — required so AI Search can connect to Cosmos
  - If not set, the script creates the data source with a managed identity
    reference (requires the search service MI to have Cosmos DB reader role)

Usage:
    python src/scripts/setup_cosmos_search_sync.py              # create all
    python src/scripts/setup_cosmos_search_sync.py --dry-run     # preview
    python src/scripts/setup_cosmos_search_sync.py --delete       # tear down
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEARCH_ENDPOINT = os.environ.get(
    "OPENINSURE_SEARCH_ENDPOINT",
    "https://openinsure-dev-search-knshtzbusr734.search.windows.net",
)
SEARCH_ADMIN_KEY = os.environ.get("OPENINSURE_SEARCH_ADMIN_KEY", "")
INDEX_NAME = os.environ.get("OPENINSURE_SEARCH_INDEX_NAME", "openinsure-knowledge")

COSMOS_ENDPOINT = os.environ.get(
    "OPENINSURE_COSMOS_ENDPOINT",
    "https://openinsure-dev-cosmos-knshtzbusr734.documents.azure.com:443/",
)
COSMOS_DATABASE = os.environ.get("OPENINSURE_COSMOS_DATABASE_NAME", "openinsure-knowledge")
COSMOS_CONTAINER = os.environ.get("OPENINSURE_COSMOS_CONTAINER", "guidelines")
COSMOS_KEY = os.environ.get("OPENINSURE_COSMOS_KEY", "")

DATA_SOURCE_NAME = "openinsure-cosmos-datasource"
INDEXER_NAME = "openinsure-cosmos-indexer"
API_VERSION = "2024-07-01"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _get_headers() -> dict[str, str]:
    """Return request headers with proper auth."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if SEARCH_ADMIN_KEY:
        headers["api-key"] = SEARCH_ADMIN_KEY
    else:
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential()
        token = cred.get_token("https://search.azure.com/.default").token
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ---------------------------------------------------------------------------
# Data source definition
# ---------------------------------------------------------------------------


def _build_data_source() -> dict[str, Any]:
    """Build the Cosmos DB data source definition for AI Search."""
    # Connection string: key-based or managed-identity
    if COSMOS_KEY:
        conn_str = f"AccountEndpoint={COSMOS_ENDPOINT};AccountKey={COSMOS_KEY};Database={COSMOS_DATABASE}"
    else:
        # Managed identity — use the Cosmos resource ID
        cosmos_resource_id = os.environ.get(
            "OPENINSURE_COSMOS_RESOURCE_ID",
            "/subscriptions/d20aaf79-95bf-45f9-91df-7483ed00c40a/resourceGroups/openinsure-dev-sc"
            "/providers/Microsoft.DocumentDB/databaseAccounts/openinsure-dev-cosmos-knshtzbusr734",
        )
        conn_str = f"ResourceId={cosmos_resource_id};Database={COSMOS_DATABASE}"

    return {
        "name": DATA_SOURCE_NAME,
        "type": "cosmosdb",
        "credentials": {"connectionString": conn_str},
        "container": {
            "name": COSMOS_CONTAINER,
            "query": None,  # index all documents
        },
        "dataChangeDetectionPolicy": {
            "@odata.type": "#Microsoft.Azure.Search.HighWaterMarkChangeDetectionPolicy",
            "highWaterMarkColumnName": "_ts",
        },
    }


# ---------------------------------------------------------------------------
# Indexer definition
# ---------------------------------------------------------------------------


def _build_indexer() -> dict[str, Any]:
    """Build the indexer that syncs Cosmos → AI Search on schedule."""
    return {
        "name": INDEXER_NAME,
        "dataSourceName": DATA_SOURCE_NAME,
        "targetIndexName": INDEX_NAME,
        "schedule": {
            "interval": "PT5M",  # every 5 minutes
        },
        "fieldMappings": [
            {"sourceFieldName": "id", "targetFieldName": "id"},
            {"sourceFieldName": "content", "targetFieldName": "content"},
            {"sourceFieldName": "entityType", "targetFieldName": "category"},
            {"sourceFieldName": "source", "targetFieldName": "source"},
        ],
        "parameters": {},
    }


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------


def _create_or_update(resource_type: str, name: str, body: dict[str, Any], headers: dict[str, str]) -> bool:
    """Create or update an AI Search resource via REST API."""
    url = f"{SEARCH_ENDPOINT}/{resource_type}/{name}?api-version={API_VERSION}"
    resp = requests.put(url, headers=headers, json=body, timeout=30)
    if resp.status_code in (200, 201, 204):
        print(f"  ✅ {resource_type}/{name} created/updated")
        return True
    print(f"  ✗ {resource_type}/{name} failed: {resp.status_code} {resp.text[:200]}")
    return False


def _delete(resource_type: str, name: str, headers: dict[str, str]) -> bool:
    """Delete an AI Search resource."""
    url = f"{SEARCH_ENDPOINT}/{resource_type}/{name}?api-version={API_VERSION}"
    resp = requests.delete(url, headers=headers, timeout=30)
    if resp.status_code in (200, 204):
        print(f"  ✅ {resource_type}/{name} deleted")
        return True
    if resp.status_code == 404:
        print(f"  ℹ  {resource_type}/{name} not found (already deleted)")
        return True
    print(f"  ✗ {resource_type}/{name} delete failed: {resp.status_code}")
    return False


def _run_indexer(headers: dict[str, str]) -> None:
    """Trigger an immediate indexer run."""
    url = f"{SEARCH_ENDPOINT}/indexers/{INDEXER_NAME}/run?api-version={API_VERSION}"
    resp = requests.post(url, headers=headers, timeout=30)
    if resp.status_code in (202, 204):
        print(f"  ✅ Indexer '{INDEXER_NAME}' triggered for immediate run")
    else:
        print(f"  ⚠  Indexer run trigger returned {resp.status_code}: {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up Cosmos DB → AI Search auto-sync.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating.")
    parser.add_argument("--delete", action="store_true", help="Delete indexer and data source.")
    args = parser.parse_args()

    if args.dry_run:
        print(f"\n{'=' * 60}")
        print("DRY RUN — Cosmos → AI Search Sync Setup")
        print(f"{'=' * 60}\n")
        print(f"  Search Endpoint:  {SEARCH_ENDPOINT}")
        print(f"  Index Name:       {INDEX_NAME}")
        print(f"  Data Source:      {DATA_SOURCE_NAME}")
        print(f"  Indexer:          {INDEXER_NAME}")
        print(f"  Cosmos Endpoint:  {COSMOS_ENDPOINT}")
        print(f"  Cosmos Database:  {COSMOS_DATABASE}")
        print(f"  Cosmos Container: {COSMOS_CONTAINER}")
        print(f"  Auth:             {'key-based' if COSMOS_KEY else 'managed-identity'}")
        print("  Schedule:         Every 5 minutes")
        print()
        print("  Data Source Definition:")
        print(f"  {json.dumps(_build_data_source(), indent=2, default=str)[:500]}")
        print()
        print("  Indexer Definition:")
        print(f"  {json.dumps(_build_indexer(), indent=2)}")
        return

    headers = _get_headers()

    if args.delete:
        print("Tearing down Cosmos → AI Search sync …\n")
        _delete("indexers", INDEXER_NAME, headers)
        _delete("datasources", DATA_SOURCE_NAME, headers)
        print("\n✅ Sync resources removed.")
        return

    print("Setting up Cosmos DB → AI Search auto-sync …\n")

    # 1. Create data source
    ds_body = _build_data_source()
    if not _create_or_update("datasources", DATA_SOURCE_NAME, ds_body, headers):
        print("\n✗ Failed to create data source. Aborting.")
        sys.exit(1)

    # 2. Create indexer
    indexer_body = _build_indexer()
    if not _create_or_update("indexers", INDEXER_NAME, indexer_body, headers):
        print("\n✗ Failed to create indexer. Aborting.")
        sys.exit(1)

    # 3. Trigger immediate run
    _run_indexer(headers)

    print(f"""
✅ Cosmos → AI Search sync configured!

  Flow:  Portal → API → Cosmos DB → Indexer (5min) → AI Search → Foundry Agents
  Data Source: {DATA_SOURCE_NAME}
  Indexer:     {INDEXER_NAME}
  Schedule:    Every 5 minutes

  To check indexer status:
    GET {SEARCH_ENDPOINT}/indexers/{INDEXER_NAME}/status?api-version={API_VERSION}
""")


if __name__ == "__main__":
    main()
