"""Seed the Cosmos DB knowledge graph with insurance knowledge from YAML files.

Also seeds claims precedents, coverage rules, and compliance rules from the
KnowledgeAgent's static dictionaries to make them queryable via Cosmos.

Usage:
    python src/scripts/seed_knowledge_graph.py
"""

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

    # Seed coverage rules from static data
    from openinsure.agents.knowledge_agent import COVERAGE_RULES

    for code, rule in COVERAGE_RULES.items():
        doc = {
            "id": f"coverage-rule-{code}",
            "entityType": "coverage_rule",
            "coverage_code": rule.get("coverage_code", code),
            "content": yaml.dump(rule),
            **{k: v for k, v in rule.items() if isinstance(v, (str, int, float, bool))},
        }
        container.upsert_item(doc)
        print(f"  Loaded coverage rule: {code}")

    # Seed claims precedents
    from openinsure.agents.knowledge_agent import CLAIMS_PRECEDENTS

    for claim_type, precedent in CLAIMS_PRECEDENTS.items():
        doc = {
            "id": f"claims-precedent-{claim_type}",
            "entityType": "claims_precedent",
            "claim_type": claim_type,
            "content": yaml.dump(precedent),
            **{k: v for k, v in precedent.items() if isinstance(v, (str, int, float, bool))},
        }
        container.upsert_item(doc)
        print(f"  Loaded claims precedent: {claim_type}")

    # Seed compliance rules
    from openinsure.agents.knowledge_agent import COMPLIANCE_RULES

    for framework, rules in COMPLIANCE_RULES.items():
        doc = {
            "id": f"compliance-rule-{framework}",
            "entityType": "compliance_rule",
            "framework": framework,
            "content": yaml.dump(rules),
            **{k: v for k, v in rules.items() if isinstance(v, (str, int, float, bool))},
        }
        container.upsert_item(doc)
        print(f"  Loaded compliance rule: {framework}")

    print("\n  Knowledge graph seeding complete.")


if __name__ == "__main__":
    main()
