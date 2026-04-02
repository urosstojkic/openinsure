# Security Hardening Gotchas

Learned during resolution of security issues #266–#273.

## 1. Changing config defaults breaks tests that relied on the old default

**Issue:** Changing `jwt_validation_mode` from `"dev"` to `"production"` broke 6 JWT unit
tests and 1 integration test. These tests craft unsigned JWTs (alg: "none") which only
work in dev mode. They never explicitly set `jwt_validation_mode` — they relied on the
default.

**Fix:** Every test that constructs a fake JWT must explicitly pass
`jwt_validation_mode="dev"` in its `Settings(...)` constructor. This is correct: tests
*should* opt in to dev mode, not inherit it silently.

**Rule:** When changing a security-relevant default, grep all test files for `Settings(`
and add the explicit override where needed.

## 2. CORS middleware is configured at app creation time, not via FastAPI DI

**Issue:** `create_app()` calls `get_settings()` directly at startup and passes
`allowed_origins` to `CORSMiddleware`. Overriding `get_settings` via
`app.dependency_overrides` has no effect on CORS — that only affects request-time
dependency injection into route handlers.

**Fix:** To test CORS behavior, set `OPENINSURE_CORS_ORIGINS` as an environment variable
*before* calling `create_app()`, not via DI overrides.

**Rule:** Any middleware configured during `create_app()` must be tested via env vars or
by patching the module-level `get_settings` function before app creation.

## 3. `git stash` can silently discard uncommitted edits on stash pop

**Issue:** Running `git stash` then `git stash pop` with a dirty working tree can drop
edits made between stash and pop if the stash only captured the pre-existing dirty state.

**Fix:** Never use `git stash` as a "save point" mid-edit. Commit your changes first,
then revert if you need to test the baseline.

## 4. nginx alpine requires directory ownership for non-root

**Issue:** nginx alpine stores temp files in `/var/cache/nginx`, PID in `/var/run`, and
logs in `/var/log/nginx`. Running as non-root without `chown` on these dirs causes
permission errors at startup.

**Fix:** The Dockerfile must `chown` all nginx runtime directories to the non-root user:
```dockerfile
RUN chown -R appuser:appuser /var/cache/nginx /var/run /var/log/nginx /etc/nginx/conf.d
```

## 5. Setting env vars to empty string breaks pydantic bool parsing

**Issue:** `$env:OPENINSURE_DEBUG = ""` causes pydantic to fail validation on the `debug:
bool` field because an empty string is not a valid boolean.

**Fix:** Use `Remove-Item Env:OPENINSURE_DEBUG` instead of setting to empty string when
clearing PowerShell environment variables.
