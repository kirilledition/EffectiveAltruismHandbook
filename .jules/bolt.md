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

## 2025-02-28 - Regex versus native string operations for simple parsing
**Learning:** Using regular expressions (e.g., `re.compile(r"^(#+) ")`) to process simple, predictable patterns like markdown headings can be significantly slower than native string indexing and methods (e.g., `.lstrip("#")`).
**Action:** Always measure the overhead of regex for basic string parsing inside large iteration loops. Prefer Python's highly optimized built-in string methods like `.split()`, `.find()`, and `.lstrip()` where they provide an equivalent logic to avoid regex instantiation and matching cost.

## 2025-02-28 - Deduplication logic in Python
**Learning:** In Python 3.7+, standard dictionaries preserve insertion order. Replacing the traditional `set` + `list` accumulator pattern with a single `dict` loop (`if key not in seen: seen[key] = obj`) is roughly 2x faster and avoids maintaining two separate collections. However, be cautious with dictionary comprehensions (`{obj.key: obj for obj in arr}`): they evaluate the whole array and continuously overwrite keys, meaning they keep the **last** duplicate occurrence, causing a regression if the **first** occurrence must be preserved.
**Action:** When deduplicating a list of objects while preserving their original order, avoid set + list operations or set comprehensions. Instead, use a simple `dict` accumulator loop to cleanly preserve the *first* occurrence with O(N) performance.
