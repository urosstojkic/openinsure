# Portal / Dashboard Lessons

Lessons learned from the OpenInsure dashboard (React + Vite frontend).

## API Routing

- Dashboard uses `/api/v1` relative path — nginx reverse-proxies to the backend.
- nginx must forward the `X-API-Key` header via `proxy_set_header`. Without this, all proxied requests fail auth.
- **Confidence:** High.

## Environment Configuration

- `VITE_USE_MOCK=false` in production — never fall back to mock data.
- If `VITE_USE_MOCK` is missing or `true`, the dashboard silently uses mock data and everything looks fine but isn't real.
- **Confidence:** High — caused a "works in dev, broken in prod" incident.

## Timeout Handling

- Axios timeout must be **90 seconds or higher** for Foundry agent calls.
- On timeout: **check server-side status before showing an error**. The action may have succeeded even though the client timed out.
- **Confidence:** High.

## UX Patterns

- Product detail click uses an **inline panel** (slide-out), not page navigation.
- This is a deliberate design decision — do not change to route-based navigation.
- **Confidence:** High.
