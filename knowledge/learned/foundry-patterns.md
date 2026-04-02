# Foundry Patterns

Lessons learned from Azure AI Foundry integration in OpenInsure.

## Agent Invocation Format

**Correct:**
```python
extra_body = {
    "agent_reference": {
        "name": agent_name,
        "type": "agent_reference"
    }
}
```

**Incorrect (deprecated — returns 400):**
```python
extra_body = {"agent": ...}  # DO NOT USE
```

- **Confidence:** High — caused hours of debugging when the old format started returning 400.

## SDK Dictionary Format

- Use plain Python dicts for tool definitions, not SDK model classes.
- Field names in dicts differ from model class attribute names.
- **Confidence:** High.

## Model Deployment

- The model deployment name must exist in the Foundry project. If it doesn't, you get a 404.
- `gpt-5.2` deployment name must match exactly — no aliases, no fallbacks.
- **Confidence:** High.

## Timeouts

- Foundry agent calls take 10–30 seconds on average.
- Set HTTP client timeout to **90 seconds** minimum.
- Shorter timeouts will cause intermittent failures that are hard to reproduce.
- **Confidence:** High — learned from production timeout errors.
