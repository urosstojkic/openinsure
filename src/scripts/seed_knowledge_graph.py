"""Seed the Cosmos DB knowledge graph with insurance knowledge from YAML files."""

from pathlib import Path

import yaml
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

COSMOS_ENDPOINT = "https://openinsure-dev-cosmos-knshtzbusr734.documents.azure.com:443/"
DATABASE = "openinsure-knowledge"
CONTAINER = "insurance-graph"


def main():
    credential = DefaultAzureCredential()
    client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    db = client.get_database_client(DATABASE)
    container = db.get_container_client(CONTAINER)

    knowledge_dir = Path(__file__).parent.parent.parent / "knowledge"

    # Load product definitions
    for yaml_file in (knowledge_dir / "products").glob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        doc = {
            "id": f"product-{data['product']['code']}",
            "entityType": "product",
            "content": yaml.dump(data),
            **data["product"],
        }
        container.upsert_item(doc)
        print(f"  Loaded product: {data['product']['code']}")

    # Load guidelines
    for yaml_file in (knowledge_dir / "guidelines").glob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        # Guidelines YAML has a top-level key like 'underwriting_guidelines'
        for key, content in data.items():
            doc = {
                "id": f"guideline-{yaml_file.stem}-{key}",
                "entityType": "guideline",
                "lob": content.get("line_of_business", "cyber"),
                "content": yaml.dump(content),
                **{k: v for k, v in content.items() if isinstance(v, (str, int, float, bool))},
            }
            container.upsert_item(doc)
            print(f"  Loaded guideline: {key}")

    # Load regulatory
    for yaml_file in (knowledge_dir / "regulatory").glob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        for key, content in data.items():
            doc = {
                "id": f"regulatory-{yaml_file.stem}-{key}",
                "entityType": "regulatory",
                "jurisdiction": "US",
                "content": yaml.dump(content),
            }
            container.upsert_item(doc)
            print(f"  Loaded regulatory: {key}")


if __name__ == "__main__":
    main()
