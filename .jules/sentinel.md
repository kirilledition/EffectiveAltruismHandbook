## 2025-03-05 - Prevent XSS Payload Persistence in Compiled Books
**Vulnerability:** XSS payload persistence in compiled EPUB/PDF formats via insecure `href` and `src` attributes. The HTML-to-Markdown conversion logic was blindly trusting attribute values, meaning `javascript:` links and `data:` URIs could be smuggled through to the final document where a PDF/EPUB reader might inadvertently execute them.
**Learning:** Even when converting to non-browser formats like Markdown or PDF, malicious URIs must be sanitized. If left intact, the target compilation tools or readers may unsafely process `javascript:` or `data:` URIs, leading to Stored XSS or similar execution vulnerabilities when a user interacts with the final compiled eBook.
**Prevention:** Always sanitize link (`href`) and image (`src`) attributes by stripping or invalidating `javascript:` and `data:` protocols from the HTML source *before* converting it to intermediate or final compiled formats.
## 2026-03-07 - Pandoc Security Flag `--sandbox`
**Vulnerability:** Untrusted user input or Markdown could execute malicious code or read local files if pandoc operates unrestricted.
**Learning:** Pandoc offers a `--sandbox` flag (since 2.15) which locks down potentially harmful functionality (like reading local files or calling external programs).
**Prevention:** Add the `--sandbox` flag to all `subprocess.run` calls involving pandoc to reduce the attack surface.
