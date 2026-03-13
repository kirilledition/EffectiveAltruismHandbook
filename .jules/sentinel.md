## 2025-02-25 - Path Traversal in `.startswith()` string validations
**Vulnerability:** URL path validation using raw `parsed.path.startswith("/expected/")` is vulnerable to path traversal (e.g., `/expected/../../../etc/passwd` evaluates to `True` but resolves to `/etc/passwd`).
**Learning:** Raw URL strings with path traversal components like `../` will pass `.startswith()` prefix validations if the prefix strings appear correctly but bypass intended checks since clients dynamically resolve the resulting paths.
**Prevention:** Always normalize URL paths using `posixpath.normpath` to strip out `../` traversal segments before applying string prefix validations.
