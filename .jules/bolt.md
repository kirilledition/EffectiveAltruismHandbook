## 2024-05-18 - BeautifulSoup get_text() vs string node iteration
**Learning:** For calculating the total string length of an element, BeautifulSoup's built-in `element.get_text()` is roughly ~1.5x faster than manually iterating over text nodes with `find_all(string=True)` and checking lengths, primarily because `get_text()` drops down to C-level iteration and automatically handles comment skipping.
**Action:** Always prefer `get_text()` when you need the full text of an element or its length, rather than writing custom DOM walkers.

## 2024-05-18 - BeautifulSoup Regex vs Lambda for class attributes
**Learning:** When searching for an element by class name, compiling a case-insensitive regular expression (`re.compile(r"(?i)pattern1|pattern2")`) and passing it to `class_` is roughly 3x faster than passing a custom lambda function that evaluates each element's classes. Lambdas force BeautifulSoup back into Python for every element, whereas regex searches are highly optimized.
**Action:** Replace multiple lambda-based DOM traversals or loops with a single `find` or `find_all` call using a compiled regex and a list of target tag names (e.g., `soup.find(["a", "span"], class_=REGEX)`).

## 2024-05-18 - Fast string matching over regex
**Learning:** Pre-compiling regular expressions is good, but adding fast-path string checks like `.startswith()` or `.endswith()` before falling back to regex evaluations is even better when most strings (like normal markdown lines) won't match. This bypasses regex overhead completely for the common case, roughly doubling performance in functions processing many lines.
**Action:** Always check if a simple string operation can efficiently filter out negative cases before running a regular expression.

## 2024-05-18 - BeautifulSoup `get_text()` bottleneck on nested DOM
**Learning:** Calling `.get_text()` on every `div` to calculate its text length is NOT an O(1) C-level operation; it is a recursive pure Python tree traversal that constantly concatenates strings and allocates memory. If used in a loop over all elements, it downgrades performance to O(N^2) and spikes memory usage. The previous custom O(N) integer-based `string=True` node traversal was actually faster and more memory-efficient.
**Action:** Never use `get_text()` repeatedly on nested elements within loops when checking for lengths or content heuristics.

## 2025-03-08 - BeautifulSoup class parsing and regex matching
**Learning:** In BeautifulSoup 4, for HTML documents, the `class` attribute is parsed as a list of strings, not a single string. Passing `class_=lambda c: "pattern" in c.lower()` can raise `AttributeError: 'list' object has no attribute 'lower'`. Moreover, using `re.compile` with `class_` correctly evaluates against each class item safely and is significantly faster than using custom Python lambda functions for DOM traversal because it leverages C-level regex evaluations natively rather than making repeated Python function calls.
**Action:** Always pre-compile regular expressions at the module level (e.g., `COMMENTS_RE = re.compile(r"(?i)comments")`) and pass them directly to `class_` in `find()` or `find_all()`. Avoid using lambda functions for DOM lookups.

## 2025-02-28 - Regex versus native string operations for simple parsing
**Learning:** Using regular expressions (e.g., `re.compile(r"^(#+) ")`) to process simple, predictable patterns like markdown headings can be significantly slower than native string indexing and methods (e.g., `.lstrip("#")`).
**Action:** Always measure the overhead of regex for basic string parsing inside large iteration loops. Prefer Python's highly optimized built-in string methods like `.split()`, `.find()`, and `.lstrip()` where they provide an equivalent logic to avoid regex instantiation and matching cost.

## 2025-02-28 - Deduplication logic in Python
**Learning:** In Python 3.7+, standard dictionaries preserve insertion order. Replacing the traditional `set` + `list` accumulator pattern with a single `dict` loop (`if key not in seen: seen[key] = obj`) is roughly 2x faster and avoids maintaining two separate collections. However, be cautious with dictionary comprehensions (`{obj.key: obj for obj in arr}`): they evaluate the whole array and continuously overwrite keys, meaning they keep the **last** duplicate occurrence, causing a regression if the **first** occurrence must be preserved.
**Action:** When deduplicating a list of objects while preserving their original order, avoid set + list operations or set comprehensions. Instead, use a simple `dict` accumulator loop to cleanly preserve the *first* occurrence with O(N) performance.

## 2025-03-09 - Skipping unconditional lstrip allocations in loops
**Learning:** Using `line.lstrip()` unconditionally at the top of a text-processing loop creates a new string object and allocates memory for every single line. In loops traversing many lines (like large Markdown files), this causes significant overhead. We can bypass this by checking `if line[0] == "#"` or `if "`" in line` before calling `.lstrip()`, taking the fast path and avoiding allocation ~90% of the time, resulting in a ~35% speed improvement.
**Action:** When iterating over thousands of lines in Python, use fast-path boolean checks (like exact character indices `line[0]` or the `in` operator) to filter lines before applying operations that allocate new strings, like `.lstrip()`, `.replace()`, or `.lower()`.

2024-05-24
When optimizing BeautifulSoup document traversals involving multiple `find_all()` calls, consolidate them into fewer passes using a combined list of tags (e.g., `soup.find_all(['nav', 'div', 'a'])`). This reduces O(N) full-document scans. Define the tag lists as module-level collections (like `frozenset` or `list`) to avoid redundant memory allocation.
## 2026-03-12 - Pre-filtering JSON-LD with string checks
**Learning:** Parsing JSON-LD scripts in a loop with `json.loads()` is extremely slow when most scripts don't contain the target data. Adding a fast-path string check (e.g., `if '"author"' not in s:`) before decoding bypasses unnecessary overhead and significantly speeds up processing.
**Action:** Always pre-filter large JSON strings using fast substring checks before invoking expensive JSON decoding in performance-critical loops.

## 2025-03-09 - BeautifulSoup text length by parent tag
**Learning:** To optimize text length calculations across deeply nested DOM trees, iterating over `soup.find_all(string=True)` and walking up the `.parent` chain for *every individual text node* results in $O(N \times Depth)$ time complexity. Grouping text node lengths by their immediate parent tag's ID first (in $O(N)$), and then propagating the accumulated sums up the tree just once per parent tag, significantly reduces redundant DOM traversals.
**Action:** When calculating aggregated structural values from text nodes up the DOM tree, always aggregate by the immediate parent element before traversing ancestors to avoid redundant full-path walks.

## 2025-03-09 - JSON-LD single-pass parsing
**Learning:** Combining multiple JSON-LD parsing functions into a single pass that extracts all metadata (e.g., author and date) simultaneously is much faster than running `soup.find_all("script", type="application/ld+json")` and parsing JSON multiple times. However, the wrapper functions must ensure the single pass isn't called multiple times on the same page. By hoisting the combined call up to the parent `scrape_post_content` method and passing the results down into `extract_author` and `extract_date`, we effectively halve the DOM traversal and JSON decoding overhead per page while keeping the individual fallback chains functionally identical.
**Action:** Always aim to extract related metadata from `ld+json` blocks in a single pass to avoid duplicate parsing, and hoist the call upstream if multiple modular functions rely on the same structured data.

## 2025-03-09 - Minimizing redundant DOM searches for multiple attributes
**Learning:** When evaluating an element across multiple conditions (like checking different `<meta>` tag `property` attributes in a priority order), running `soup.find("meta", attrs=...)` multiple times causes redundant $O(N)$ full-document traversals. Since `<meta>` tags are relatively sparse and localized to `<head>`, calling `soup.find_all("meta")` exactly once and iterating over the list in Python to check attributes is roughly 5x faster because it reduces the DOM scans.
**Action:** Always fetch sparse, target elements with a single `find_all` query when checking them against multiple independent criteria, filtering the pre-fetched list in Python instead of re-scanning the DOM repeatedly.

## 2025-03-17 - Fast-path checks before regex substitution
**Learning:** Using `re.sub(r"<[^>]+>", "", name)` and `re.sub(r"\s+", " ", name)` inside `_clean_author_name` creates an unnecessary performance penalty when processing hundreds of author names that mostly don't contain HTML tags or excessive whitespace. Pre-compiling the regexes and adding fast-path string checks (e.g. `"<" in name` and `"\n" in name`) avoids the overhead of executing standard regex machinery and provides a ~3x speedup.
**Action:** When applying regular expressions to sanitize or manipulate strings, avoid blindly applying `re.sub` inside tight loops if the operation will often be a no-op. Guard it with fast-path string presence checks to conditionally apply the regex only when necessary.
## 2025-03-05 - Fast-path checking for rare string occurrences in BeautifulSoup
**Learning:** `BeautifulSoup.find_all()` combined with evaluating `get_text()` on every matched child node is incredibly expensive in Python loops, especially for deeply nested HTML like forum posts. When searching for rare text strings (like CC licenses which appear in <1% of posts), this causes massive O(N) overhead.
**Action:** Use `element.get_text().lower()` as an initial O(1) string check at the parent level. If the keywords are completely absent from the parent's concatenated text, `return` immediately to skip the O(N) DOM traversal entirely. This dropped evaluation time for posts without CC licenses from ~100ms down to ~10ms.

## 2026-03-19 - Native split and join over regex for whitespace normalization
**Learning:** Using `\" \".join(string.split())` is roughly 2x faster than using `re.sub(r'\s+', ' ', string)` to collapse arbitrary whitespace. It avoids instantiating and running the regular expression engine, instead relying entirely on highly-optimized native C-level string methods.
**Action:** When normalizing whitespace (e.g. collapsing spaces, tabs, and newlines), prefer the `.split()` and `.join()` pattern over regular expressions.

## 2025-03-09 - Fast-path string checks over regex for class name exclusion
**Learning:** When checking if a class name contains a specific substring (like "comments") case-insensitively across many elements, using `re.search` with a compiled `(?i)comments` pattern is significantly slower (~2-3x) than using a fast-path string check like `"comments" in c.lower()`. Regular expressions carry intrinsic engine overhead, whereas Python's built-in string methods like `.lower()` and the `in` operator execute as highly optimized C code.
**Action:** When filtering or excluding elements based on simple, known substrings in tight loops (like iterating over all nodes to clean up the DOM before Markdown conversion), always prefer native string checks (`"substring" in string.lower()`) over regular expressions to bypass the regex engine overhead entirely.

## 2025-03-22 - Fast-path string inclusion bypasses for heavy URL parsing
**Learning:** Executing `urllib.parse.urlparse` and `posixpath.normpath` on thousands of arbitrary external links simply to check if they match a specific route pattern (like `/posts/`) is unnecessarily expensive. A simple `if "/posts/" not in url` substring check can immediately reject invalid URLs, bypassing the heavy library parsing entirely and doubling performance for the negative case.
**Action:** When filtering or validating complex URIs or file paths, always identify if there's a required, unique substring. Use a native Python `in` or `not in` check to fast-path reject invalid strings before passing the remaining inputs to heavy standard library parsing functions.

## 2024-05-18 - Caching MarkdownConverter instances
**Learning:** Instantiating `markdownify.MarkdownConverter` repeatedly inside a tight loop (e.g., for every HTML element or page converted) incurs significant overhead due to internal initialization and regex compilation. Reusing a single instance initialized at the module level roughly halves the conversion time.
**Action:** Always instantiate heavy conversion objects like `MarkdownConverter` once at the module level or share them via a context/class property, rather than re-creating them for each item processed in a loop.

## 2026-03-26 - Fast-path string checks bypass redundant URL parsing
**Learning:** During HTML sanitization, calling `urllib.parse.urlparse` unconditionally on every `href` or `src` attribute (to check if it lacks a scheme so it can be resolved against `BASE_URL`) is a major bottleneck, as ~99% of forum links are already fully qualified absolute URLs (`http://...` or `https://...`). Adding a simple string check `if not val.startswith(("http://", "https://", "#", "mailto:", "tel:")):` bypasses the heavy `urlparse()` machinery for standard absolute links, resulting in a ~2x speedup for typical full URLs. Similarly, checking `"/out" in val` before unwrapping the EA Forum's redirect proxy (`/out?url=...`) yields a ~3x speedup.
**Action:** When iterating over HTML attributes to parse and resolve URLs, use `str.startswith()` or the `in` operator to fast-path reject URLs that do not need normalization or custom unboxing.

## 2025-03-27 - Distinguishing empty results from uncomputed results in kwargs
**Learning:** Passing an empty string (`""`) as a default keyword argument to indicate "not provided" creates a performance bug when an empty string is *also* a valid computed result from an upstream function. In `extract_author` and `extract_date`, using `if not name:` caused the fallback logic to redundantly re-execute the expensive JSON-LD parser every time the first pass found nothing. This resulted in the same $O(N)$ DOM scanning and JSON decoding running three times per page.
**Action:** When passing pre-computed results down a fallback chain to save processing time, always use `None` as the default value to distinguish "uncomputed" from "computed but empty". Guard the fallback execution with an explicit `is None` check rather than a boolean falsiness check (like `not val` or `if val:`).

## 2025-02-28 - Fast Python String Matching
**Learning:** In a tight Python text-processing loop (like `demote_headings` for markdown compilation), using `re.match` to check prefixes and Python function calls (`_demote_line`) adds significant overhead. Built-in string operations (`line[0]`, `line.lstrip()`, `stripped[:3]`) are much faster than regex matching and function call frames.
**Action:** Replace `re.match` with `.startswith()` and direct string slicing for known-length markers, and inline heavily-called string processing helpers. Use `first = line[0]` checks to skip allocating `line.lstrip()` for lines that clearly don't match the pattern.
