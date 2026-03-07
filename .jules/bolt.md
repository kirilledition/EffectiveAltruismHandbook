## 2024-05-24 - BeautifulSoup HTML text extraction performance
**Learning:** In the `eahandbookcompiler` scraper, manually finding text nodes (e.g. `find_all(string=True)`) and traversing up the parent tree (`parent.parent`) to aggregate string lengths per container is very slow. It is >2x faster to let BeautifulSoup compute the combined text via `d.get_text()` natively, which automatically filters out `bs4.element.Comment` objects and correctly aggregates visible strings in a C-accelerated path.
**Action:** Always prefer `len(element.get_text())` to measure total inner text size when building heuristic-based scrapers.

## 2024-05-24 - Optimizing deep BeautifulSoup traversal and filtering
**Learning:** Using `soup.find()` with a custom `lambda t: ...` for filtering takes significantly longer because the lambda gets executed for every potential node. An unanchored pre-compiled regex (e.g., `re.compile(r'(?i)pattern')`) passed via `class_=...` lets BeautifulSoup handle the matching internally much faster. A benchmark on a large nested DOM showed regexes being up to ~2x-3x faster for targeted lookups (especially when many irrelevant nodes exist).
**Action:** Replace `lambda` filters used in `find()` or `find_all()` with pre-compiled regexes where the logic implies multiple subclass matching.
