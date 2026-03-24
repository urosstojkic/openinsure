"""Try listing and creating agents via the New Foundry REST API."""

import os

import httpx
from azure.identity import DefaultAzureCredential

os.environ["OPENAI_API_VERSION"] = "2025-05-01-preview"

cred = DefaultAzureCredential()
token = cred.get_token("https://ai.azure.com/.default").token

ENDPOINT = "https://uros-ai-foundry-demo-resource.services.ai.azure.com"
PROJECT = "uros-ai-foundry-demo"
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
API_VERSION = "2025-01-01-preview"

# List agents
print("=== Listing agents (New Foundry API) ===")
url = f"{ENDPOINT}/api/projects/{PROJECT}/agents?api-version={API_VERSION}"
r = httpx.get(url, headers=HEADERS, timeout=30)
print(f"GET agents: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    for a in data.get("value", data.get("data", [])):
        name = a.get("name", "?")
        aid = a.get("id", "?")
        print(f"  {name}: {aid}")
else:
    print(f"  Error: {r.text[:300]}")

# Try creating a new agent via REST
print("\n=== Creating openinsure-billing (New Foundry API) ===")
body = {
    "name": "openinsure-billing",
    "model": "gpt-4o",
    "instructions": "AI billing agent for OpenInsure. Predicts payment defaults, recommends billing plans.",
}
url = f"{ENDPOINT}/api/projects/{PROJECT}/agents?api-version={API_VERSION}"
r = httpx.post(url, headers=HEADERS, json=body, timeout=30)
print(f"POST agent: {r.status_code}")
if r.status_code in (200, 201):
    print(f"  Created: {r.json()}")
else:
    print(f"  Error: {r.text[:300]}")

# Try the assistants endpoint (old API)
print("\n=== Trying assistants endpoint ===")
url = f"{ENDPOINT}/api/projects/{PROJECT}/assistants?api-version={API_VERSION}"
r = httpx.get(url, headers=HEADERS, timeout=30)
print(f"GET assistants: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    for a in data.get("data", []):
        print(f"  {a.get('name', '?')}: {a.get('id', '?')}")
