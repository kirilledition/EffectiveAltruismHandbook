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
