## 2024-05-24 - [CRITICAL] Initial Security Review
**Vulnerability:** Initial codebase review.
**Learning:** Found possible injection vulnerabilities in `subprocess.run` calls in `src/eahandbookcompiler/converter.py` where `str(markdown_path)` and `str(output_path)` are passed to `pandoc`. `S603` is ignored in `pyproject.toml`.
**Prevention:** Always validate paths and use `shell=False` (which is the default).

## 2024-05-24 - [CRITICAL] Fix URL Redirect Unwrapping Vulnerability
**Vulnerability:** LFI / SSRF via Unwrapped Outbound Redirects. When processing tags with attributes like 'href' or 'src' in `html_to_markdown`, the code properly checked for dangerous schemes (e.g. `javascript:`, `file:`, `data:`). However, it subsequently performed an unwrapping of outbound redirects (like `/out?url=/etc/passwd`). The unwrapped URL (`/etc/passwd` in this example) was appended to `BASE_URL` if it lacked a scheme. But because the unwrapping happened *after* the fast-path check `not val.startswith(...)` which converted relative URLs to absolute URLs using `urljoin`, the unwrapped URL could be an unintended local file path. Specifically, `val` was originally `/out?url=/etc/passwd`. `val` didn't start with `http://` etc, so it became `https://forum.effectivealtruism.org/out?url=/etc/passwd`. Then it was unwrapped to `/etc/passwd`. Then it wasn't converted to an absolute URL anymore. Wait, the exact order of operations was:

Original code:
```python
                        if not val.startswith(("http://", "https://", "#", "mailto:", "tel:")):
                            parsed_val = urlparse(val)
                            if not parsed_val.scheme:
                                val = urljoin(BASE_URL, val)

                        # UX Enhancement: Unwrap EA Forum outbound link redirects (/out?url=...)
                        if "/out" in val:
                            parsed_url = urlparse(val)
                            if parsed_url.path == "/out":
                                qs = parse_qs(parsed_url.query)
                                if qs.get("url"):
                                    val = qs["url"][0]

                                # Re-validate unwrapped URL to prevent XSS bypass
                                unwrapped_cleaned = _WS_CTRL_RE.sub("", unquote(html.unescape(val))).lower()
                                if unwrapped_cleaned.startswith(_DANGEROUS_SCHEMES):
                                    del element[attr]
                                    continue

                        element[attr] = val
```
If `val` is `https://forum.effectivealtruism.org/out?url=/etc/passwd`, the first block doesn't do anything because it starts with `https://`.
Then the unwrapping block unwraps it to `/etc/passwd`.
Then `element[attr] = val` sets it to `/etc/passwd`.
When Pandoc later compiles it to PDF/EPUB, it could read `/etc/passwd` because Pandoc processes local files for relative paths! This is an LFI.

By reordering the unwrapping block to be *before* the check that makes relative URLs absolute, any unwrapped URL like `/etc/passwd` will then go through the absolute URL conversion block and become `https://forum.effectivealtruism.org/etc/passwd`, preventing Pandoc from reading it from the local disk!
**Learning:** When unwrapping URLs, the result might become a relative path. If the protection against LFI relies on making all paths absolute, the unwrapping must happen *before* the conversion to absolute URLs.
**Prevention:** Always ensure normalization to absolute URLs occurs *after* any extraction/unwrapping of payload URLs, to guarantee the final state is absolute and safe from local file inclusion by external tools like Pandoc.

## 2024-05-24 - [HIGH] Fix HTML5 Media Tag XSS / SSRF
**Vulnerability:** XSS and SSRF/LFI via HTML5 Media Tags (`<video>`, `<audio>`, `<track>`) and the `poster` attribute. While standard tags like `<a>` and `<img>` were sanitized for dangerous schemes (`javascript:`, `file:`, etc.), media tags were omitted. Additionally, the `poster` attribute on `<video>` tags (which `markdownify` converts to markdown image syntax) was not checked, allowing payloads like `<video poster="javascript:alert(1)">` or `<video src="file:///etc/passwd">` to persist into the final EPUB/PDF.
**Learning:** When sanitizing HTML for conversion to Markdown or other formats, all tags that can initiate network requests or execute scripts must be included in the allowlist. Furthermore, all attributes capable of holding URLs (`href`, `src`, `data`, `poster`, `action`, etc.) on those tags must be strictly validated.
**Prevention:** Maintain a comprehensive list of all HTML5 elements and attributes that accept URLs, and apply scheme validation (`_DANGEROUS_SCHEMES`) to all of them consistently.

## 2026-04-02 - [CRITICAL] Prevent Pandoc LFI via Sandbox
**Vulnerability:** Local File Inclusion (LFI) via Pandoc processing untrusted markdown. Even if HTML sanitization successfully prevents malicious protocols (like `file:///etc/passwd`), if an attacker can inject a standard relative link to a local file (e.g. `[link](/etc/passwd)` or `![image](/etc/passwd)`) and bypass the absolute URL check, Pandoc will attempt to read and embed the local file from disk during EPUB/PDF generation.
**Learning:** Pandoc is a powerful conversion tool that interacts with the filesystem by default. When processing markdown derived from untrusted user input, relying solely on input sanitization is insufficient defense-in-depth against LFI. Pandoc provides a `--sandbox` flag specifically designed to restrict IO operations (preventing reads of arbitrary local files).
**Prevention:** Always execute Pandoc with the `--sandbox` flag enabled when converting user-generated or externally-scraped markdown to offline formats (EPUB, PDF, etc.).

## 2024-05-24 - [CRITICAL] Fix SSRF Parser Differential
**Vulnerability:** Server-Side Request Forgery (SSRF) bypass due to URL parser differentials. The `_validate_url` function validated the URL components correctly (restricting to `effectivealtruism.org`), but then returned `parsed.geturl()`, which reconstructed the *original* string (e.g. `http://effectivealtruism.org\t@evil.com/`). When this original, unnormalized string was passed to downstream HTTP clients like `requests`, the client's internal parser (`urllib3`) would interpret the string differently (ignoring the "valid" host and connecting to `evil.com`).
**Learning:** Returning `parsed.geturl()` on a `urllib.parse.ParseResult` does not "clean" or normalize the ambiguous parts of the network location; it simply re-combines the original parsed tokens. If the input string is malformed or uses trick characters (like tabs, spaces, or embedded credentials before an `@` that point to a different host), the downstream consumer might parse those tokens differently, completely invalidating the security check.
**Prevention:** To prevent SSRF and URL validation bypasses via parsing differentials, explicitly reconstruct the parsed URL's `netloc` using *strictly* the validated `hostname` and `port` components (e.g., `parsed._replace(netloc=f"{hostname}:{port}").geturl()`). Do not rely on `parsed.geturl()` on the original object if the original string could contain ambiguous unvalidated segments.

## 2024-05-24 - [HIGH] Fix URL Validation Bypass for Empty Hostnames
**Vulnerability:** Denial of Service (DoS) / Server-Side Request Forgery (SSRF) bypass due to URL parser accepting empty hostnames. The `is_ea_forum_post` function permitted URLs with an empty or missing `hostname` to support relative links (e.g. `/posts/123`). However, `urllib.parse.urlparse` also returns an empty hostname for malformed absolute URIs like `http:///posts/123` or `file:///etc/passwd`. An attacker injecting such a URL into the forum would bypass the `forum.effectivealtruism.org` allowlist check. Downstream functions like `fetch` would then crash when encountering `http:///posts/123`, causing the entire scraping job to fail (DoS).
**Learning:** Permitting empty hostnames to support relative paths creates a loophole for absolute paths that intentionally omit the host. If a scheme is present in the URL, a valid hostname must also be strictly required.
**Prevention:** When validating URLs that conditionally allow relative paths (where `hostname` is empty), explicitly verify that if `parsed.scheme` is present, `hostname` is also present and valid.

## 2024-05-24 - [MEDIUM] Prevent Cache Collisions
**Vulnerability:** Cache Collisions / Poisoning. The `_process_single_post` cache mechanism truncated the SHA-256 hash of post URLs to 16 characters (`[:16]`). While useful for saving disk space, 16 hex characters only provide 64 bits of entropy. Over large document sets or maliciously crafted URLs, this can lead to cache collisions where two different URLs hash to the same value, causing the incorrect cached content to be served.
**Learning:** Truncating cryptographic hashes significantly weakens collision resistance. When used for cache keys, it creates a risk of serving incorrect content, and in some contexts could allow cache poisoning if an attacker crafts colliding keys.
**Prevention:** Always use the full length of a cryptographic hash (e.g., the full 64-character SHA-256 hexdigest) when generating unique filenames or cache keys based on arbitrary string inputs like URLs.
