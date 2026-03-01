## 2025-03-01 - Prevent XSS Persistence in Markdown to EPUB Conversion
**Vulnerability:** XSS payloads via `javascript:` and `data:text/html` schemes in `href` and `src` attributes of parsed HTML elements.
**Learning:** `markdownify` translates `javascript:` URLs into Markdown links (e.g., `[Click](javascript:alert(1))`). When Pandoc later converts this Markdown into EPUB or PDF formats, it generates active HTML tags (e.g., `<a href="javascript:alert(1)">Click</a>`), introducing a stored XSS vulnerability for readers of the generated ebook if a malicious post on the EA Forum contains such payloads.
**Prevention:** Sanitize potentially dangerous `href` and `src` attributes of anchor tags, images, and iframes from BeautifulSoup parsed tags *before* passing them to `markdownify`.
