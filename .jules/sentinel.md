## 2025-03-03 - Prevent XSS evasion via alternative execution schemes
**Vulnerability:** The scraper only blocked `javascript:`, `vbscript:`, `data:`, and `file:` schemes, leaving alternative/legacy schemes like `jscript:`, `vbs:`, and `livescript:` open to XSS.
**Learning:** Security filters based on blocklists often miss lesser-known or alternative aliases for execution schemes. While `javascript:` is the most common, others can be equally dangerous, particularly when content is rendered in different offline readers or environments (EPUB/PDF via Pandoc).
**Prevention:** When building URL scheme blocklists (`_DANGEROUS_SCHEMES`), always include legacy and alternative execution schemes (`jscript:`, `vbs:`, `livescript:`) to prevent evasion.
