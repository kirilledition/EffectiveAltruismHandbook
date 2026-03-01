## 2024-05-24 - [Avoid Redundant HTML Parsing in markdownify]
**Learning:** `markdownify()` function takes an HTML string. Passing a `BeautifulSoup` element to it requires serializing the tree back into a string (`str(html_element)`), only for `markdownify` to immediately re-parse it into a new `BeautifulSoup` tree under the hood.
**Action:** Use `MarkdownConverter(heading_style="ATX").convert_soup(html_element)` directly instead of `markdownify(str(html_element), heading_style="ATX")` to skip redundant string serialization and parsing.
