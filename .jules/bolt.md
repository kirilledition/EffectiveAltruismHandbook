## 2024-05-18 - BeautifulSoup get_text() vs string node iteration
**Learning:** For calculating the total string length of an element, BeautifulSoup's built-in `element.get_text()` is roughly ~1.5x faster than manually iterating over text nodes with `find_all(string=True)` and checking lengths, primarily because `get_text()` drops down to C-level iteration and automatically handles comment skipping.
**Action:** Always prefer `get_text()` when you need the full text of an element or its length, rather than writing custom DOM walkers.

## 2024-05-18 - BeautifulSoup Regex vs Lambda for class attributes
**Learning:** When searching for an element by class name, compiling a case-insensitive regular expression (`re.compile(r"(?i)pattern1|pattern2")`) and passing it to `class_` is roughly 3x faster than passing a custom lambda function that evaluates each element's classes. Lambdas force BeautifulSoup back into Python for every element, whereas regex searches are highly optimized.
**Action:** Replace multiple lambda-based DOM traversals or loops with a single `find` or `find_all` call using a compiled regex and a list of target tag names (e.g., `soup.find(["a", "span"], class_=REGEX)`).
