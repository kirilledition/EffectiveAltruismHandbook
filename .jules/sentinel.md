## 2025-02-25 - Path Traversal in `.startswith()` string validations
**Vulnerability:** URL path validation using raw `parsed.path.startswith("/expected/")` is vulnerable to path traversal (e.g., `/expected/../../../etc/passwd` evaluates to `True` but resolves to `/etc/passwd`).
**Learning:** Raw URL strings with path traversal components like `../` will pass `.startswith()` prefix validations if the prefix strings appear correctly but bypass intended checks since clients dynamically resolve the resulting paths.
**Prevention:** Always normalize URL paths using `posixpath.normpath` to strip out `../` traversal segments before applying string prefix validations.

## 2025-03-16 - Local File Inclusion (LFI) via Pandoc Relative Paths
**Vulnerability:** Attackers could include arbitrary files from the local filesystem during PDF/EPUB generation if they supplied relative paths (e.g. `src="/etc/passwd"`) that Pandoc dynamically resolved and embedded.
**Learning:** Pandoc acts as a file system reader during compilation. When converting HTML to Markdown, allowing uncontrolled `file://` schemes or unresolved relative paths lets the external tool access the compiler's host environment.
**Prevention:** Sanitize image/resource URLs explicitly against local schemes (like `file:`) and eagerly resolve all relative paths to absolute domain URLs during the HTML sanitization phase so that downstream compilation tools interpret them as network boundaries.
## 2025-05-18 - SSRF via Initial URL Verification Bypass
**Vulnerability:** A `fetch` wrapper designed to safely follow redirects by restricting domains to `effectivealtruism.org` failed to validate the *initial* URL, allowing an attacker to bypass the restriction on the very first HTTP request (e.g. `fetch(session, "http://127.0.0.1/admin")` would execute immediately).
**Learning:** Security validations (like URL scheme/domain allowlists) that are meant to protect an HTTP request cycle must be applied eagerly to the initial input URL before any network connection is established, not just to subsequent redirect `Location` headers.
**Prevention:** Extract the URL validation logic into a reusable helper function and invoke it unconditionally at the start of the redirect loop or request wrapper, ensuring both the first URL and all subsequent redirects pass the same strict checks.
