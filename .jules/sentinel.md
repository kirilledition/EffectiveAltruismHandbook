## 2025-02-25 - Path Traversal in `.startswith()` string validations
**Vulnerability:** URL path validation using raw `parsed.path.startswith("/expected/")` is vulnerable to path traversal (e.g., `/expected/../../../etc/passwd` evaluates to `True` but resolves to `/etc/passwd`).
**Learning:** Raw URL strings with path traversal components like `../` will pass `.startswith()` prefix validations if the prefix strings appear correctly but bypass intended checks since clients dynamically resolve the resulting paths.
**Prevention:** Always normalize URL paths using `posixpath.normpath` to strip out `../` traversal segments before applying string prefix validations.

## 2025-03-16 - Local File Inclusion (LFI) via Pandoc Relative Paths
**Vulnerability:** Attackers could include arbitrary files from the local filesystem during PDF/EPUB generation if they supplied relative paths (e.g. `src="/etc/passwd"`) that Pandoc dynamically resolved and embedded.
**Learning:** Pandoc acts as a file system reader during compilation. When converting HTML to Markdown, allowing uncontrolled `file://` schemes or unresolved relative paths lets the external tool access the compiler's host environment.
**Prevention:** Sanitize image/resource URLs explicitly against local schemes (like `file:`) and eagerly resolve all relative paths to absolute domain URLs during the HTML sanitization phase so that downstream compilation tools interpret them as network boundaries.
