"""Index OpenInsure knowledge base YAML files into Azure AI Search.

Creates (or updates) the ``openinsure-knowledge`` index and uploads
chunked documents from every YAML file found under ``knowledge/``.

Usage:
    python src/scripts/index_knowledge.py              # index everything
    python src/scripts/index_knowledge.py --dry-run     # preview without indexing
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEARCH_ENDPOINT = "https://openinsure-dev-search-knshtzbusr734.search.windows.net"
INDEX_NAME = "openinsure-knowledge"
EMBEDDING_DIMENSIONS = 1536
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"
BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Index schema
# ---------------------------------------------------------------------------


def _build_index() -> SearchIndex:
    """Return an ``SearchIndex`` definition for the knowledge base."""
    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(
            name="title",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="category",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="source",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SearchField(
            name="tags",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="default-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="default-profile",
                algorithm_configuration_name="default-hnsw",
            )
        ],
    )

    return SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
    )


# ---------------------------------------------------------------------------
# YAML chunking
# ---------------------------------------------------------------------------


def _stable_id(source: str, path_parts: list[str]) -> str:
    """Produce a deterministic document ID from file + section path."""
    raw = f"{source}::{'/'.join(path_parts)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _infer_tags(path_parts: list[str], category: str) -> list[str]:
    """Derive search tags from the section path and category."""
    tags: set[str] = set()
    tags.add(category)
    for part in path_parts:
        # Convert camelCase/snake_case to individual tokens
        tokens = re.split(r"[_\-\s]+", part.lower())
        tags.update(t for t in tokens if len(t) > 1)
    return sorted(tags)


def _section_to_text(key: str, value: Any) -> str:
    """Render a YAML section as readable text for indexing."""
    if isinstance(value, str):
        return f"{key}: {value}"
    # Re-serialize complex values as indented YAML for readability
    serialized = yaml.dump({key: value}, default_flow_style=False, sort_keys=False, width=200)
    return serialized.strip()


def _is_leaf(value: Any) -> bool:
    """Return True if value should be emitted as-is rather than recursed."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return True
    return isinstance(value, list)


def _chunk_dict(
    data: dict[str, Any],
    *,
    source: str,
    category: str,
    parent_path: list[str] | None = None,
    depth: int = 0,
    max_depth: int = 2,
) -> list[dict[str, Any]]:
    """Recursively break a parsed YAML dict into indexable chunks.

    Strategy: walk into nested dicts up to *max_depth* levels.  When a
    value is a leaf (scalar / list) or we've reached max depth, emit the
    key-value pair as a standalone document.  This ensures each top-level
    YAML file produces many focused chunks.
    """
    parent_path = parent_path or []
    documents: list[dict[str, Any]] = []

    for key, value in data.items():
        current_path = [*parent_path, key]

        if not _is_leaf(value) and depth < max_depth and isinstance(value, dict):
            # Recurse into sub-dict
            documents.extend(
                _chunk_dict(
                    value,
                    source=source,
                    category=category,
                    parent_path=current_path,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )
        else:
            content = _section_to_text(key, value)
            title = " › ".join(current_path)
            documents.append(
                {
                    "id": _stable_id(source, current_path),
                    "content": content,
                    "title": title,
                    "category": category,
                    "source": source,
                    "tags": _infer_tags(current_path, category),
                }
            )

    return documents


def _parse_yaml_file(path: Path) -> list[dict[str, Any]]:
    """Load a YAML file and return chunked documents."""
    rel = path.relative_to(KNOWLEDGE_DIR)
    source = str(rel).replace("\\", "/")
    # Category is the first directory component (e.g. "guidelines")
    category = rel.parts[0] if len(rel.parts) > 1 else "general"

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        return []

    return _chunk_dict(data, source=source, category=category)


# ---------------------------------------------------------------------------
# Optional embeddings
# ---------------------------------------------------------------------------


def _try_get_embeddings(
    texts: list[str],
) -> list[list[float]] | None:
    """Attempt to generate embeddings via Azure OpenAI.  Returns ``None``
    on any failure so that indexing can proceed without vectors."""
    try:
        from openai import AzureOpenAI

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            print("  ℹ  AZURE_OPENAI_ENDPOINT not set — skipping embeddings")
            return None

        client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=None,
            azure_deployment="text-embedding-ada-002",
            api_version="2024-06-01",
            azure_ad_token=DefaultAzureCredential().get_token("https://cognitiveservices.azure.com/.default").token,
        )
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts,
        )
        return [item.embedding for item in response.data]
    except Exception as exc:
        print(f"  ⚠  Embedding generation failed ({exc}) — indexing without vectors")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _collect_documents() -> list[dict[str, Any]]:
    """Walk ``knowledge/`` and return all chunked documents."""
    if not KNOWLEDGE_DIR.is_dir():
        print(f"ERROR: knowledge directory not found at {KNOWLEDGE_DIR}")
        sys.exit(1)

    documents: list[dict[str, Any]] = []
    yaml_files = sorted(KNOWLEDGE_DIR.rglob("*.yaml"))

    if not yaml_files:
        print("WARNING: no .yaml files found under knowledge/")
        return documents

    for yaml_file in yaml_files:
        chunks = _parse_yaml_file(yaml_file)
        print(f"  📄 {yaml_file.relative_to(KNOWLEDGE_DIR)}  →  {len(chunks)} chunks")
        documents.extend(chunks)

    return documents


def _add_embeddings(documents: list[dict[str, Any]]) -> None:
    """Enrich *documents* in-place with ``content_vector`` if possible."""
    texts = [doc["content"] for doc in documents]
    embeddings = _try_get_embeddings(texts)
    if embeddings:
        for doc, emb in zip(documents, embeddings, strict=True):
            doc["content_vector"] = emb
        print(f"  ✅ Generated {len(embeddings)} embeddings")


def _dry_run(documents: list[dict[str, Any]]) -> None:
    """Print what would be indexed without making any API calls."""
    print(f"\n{'=' * 60}")
    print(f"DRY RUN — {len(documents)} documents would be indexed")
    print(f"Target index: {INDEX_NAME}")
    print(f"Endpoint:     {SEARCH_ENDPOINT}")
    print(f"{'=' * 60}\n")

    for doc in documents:
        snippet = doc["content"][:120].replace("\n", " ")
        print(f"  [{doc['id'][:12]}…]  {doc['title']}")
        print(f"              category={doc['category']}  source={doc['source']}")
        print(f"              tags={doc['tags']}")
        print(f"              {snippet}…\n")


def _get_search_credential():
    """Return the best available credential for Azure AI Search.

    Prefers ``DefaultAzureCredential`` (RBAC).  If an admin key is set via
    ``AZURE_SEARCH_ADMIN_KEY`` it will be used as a fallback — this is
    useful when the caller's identity lacks
    ``Search Index Data Contributor``.
    """
    admin_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY")
    if admin_key:
        from azure.core.credentials import AzureKeyCredential

        return AzureKeyCredential(admin_key)
    return DefaultAzureCredential()


def _index(documents: list[dict[str, Any]]) -> None:
    """Create/update the index and upload documents."""
    credential = _get_search_credential()

    # 1. Ensure index exists
    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
    index_def = _build_index()
    index_client.create_or_update_index(index_def)
    print(f"  ✅ Index '{INDEX_NAME}' created/updated")

    # 2. Upload documents in batches (merge_or_upload for idempotency)
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=credential,
    )

    for i in range(0, len(documents), BATCH_SIZE):
        batch = documents[i : i + BATCH_SIZE]
        results = search_client.merge_or_upload_documents(documents=batch)
        succeeded = sum(1 for r in results if r.succeeded)
        failed = len(batch) - succeeded
        label = f"batch {i // BATCH_SIZE + 1}"
        if failed:
            print(f"  ⚠  {label}: {succeeded} succeeded, {failed} failed")
            for r in results:
                if not r.succeeded:
                    print(f"      ✗ {r.key}: {r.error_message}")
        else:
            print(f"  ✅ {label}: {succeeded} documents uploaded")

    search_client.close()
    index_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Index OpenInsure knowledge base into Azure AI Search.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be indexed without making any API calls.",
    )
    args = parser.parse_args()

    print("Collecting knowledge documents …")
    documents = _collect_documents()

    if not documents:
        print("Nothing to index.")
        return

    print(f"\nTotal: {len(documents)} documents\n")

    if args.dry_run:
        _dry_run(documents)
        return

    # Try to add embeddings (non-fatal if unavailable)
    _add_embeddings(documents)

    print("Indexing into Azure AI Search …")
    _index(documents)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()
