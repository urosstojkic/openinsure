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

## Design Tokens (#276)

- **Always use CSS custom property tokens** from `index.css :root` — never hardcode colors, spacing, or radii.
- Colors: `var(--color-primary)`, `var(--color-danger)`, `var(--color-success)`, `var(--color-warning)`
- Spacing: `var(--spacing-sm)` (0.5rem), `var(--spacing-md)` (1rem), `var(--spacing-lg)` (1.5rem)
- Radius: `var(--radius-default)` (0.5rem), `var(--radius-lg)` (0.75rem), `var(--radius-xl)` (1rem)
- Shadows: `var(--shadow-xs)`, `var(--shadow-card)`, `var(--shadow-md)`
- Use Tailwind arbitrary value syntax: `rounded-[var(--radius-default)]`, `border-[var(--color-danger)]`
- **Why:** Enables future dark mode, white-label theming, single point of change.
- **Confidence:** High.

## Code Splitting (#275)

- **Never statically import page components in App.tsx.** Use `React.lazy(() => import('./pages/X'))`.
- Wrap routes in `<Suspense fallback={<LoadingSpinner />}>`.
- Split vendor chunks in `vite.config.ts` via `manualChunks` (react, tanstack-query, recharts).
- Impact: 1,176KB → 257KB main bundle (78% reduction).
- **Confidence:** High — verified in build output.

## Keyboard Accessibility (#277)

- **DataTable rows must have `tabIndex={0}`**, `role="row"`, and `onKeyDown` handler.
- Keys: Enter/Space = click, ArrowUp/Down = navigate rows, Home/End = jump to first/last.
- Use `focus-visible:ring-2` (not `:focus`) for keyboard-only focus ring.
- **Confidence:** High — verified with Playwright programmatic keyboard tests.

## Form Validation (#286)

- **Validate inline on blur, not just on submit.** Track "touched" state per field.
- Clear errors as soon as input becomes valid (in `onChange` when field is touched).
- Always include `aria-invalid`, `aria-describedby={fieldName}-error`, `role="alert"` on error text.
- **Confidence:** High — verified cycle: empty→blur→error→type valid→clears→bad email→"Invalid format"→fix→clears.

## Responsive Design (#283)

- **Page headers must stack on mobile:** `flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`
- Search inputs: `w-full sm:w-64` (full-width mobile, constrained on desktop).
- Touch targets: min 44px via CSS `@media (hover: none) and (pointer: coarse)`.
- Always test at: 375px, 768px, 1024px, 1440px.
- **Confidence:** High — verified with Playwright resize + screenshots.

## Verification Standard

- `npm run build` passing is **necessary but not sufficient** for UI changes.
- Start dev server, navigate to affected pages.
- Test keyboard interactions programmatically via `page.evaluate()`.
- Screenshot at mobile/tablet/desktop breakpoints.
- Verify aria attributes exist in DOM.
- **Confidence:** High — anti-rationalization rule.
