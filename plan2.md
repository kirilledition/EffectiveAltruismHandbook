Based on the prompt: `most often they are from 80000 hours website. i need to parse them to and have real text from external book inside my book. detect those blog posts by reading markdown that is outputted by current parser and create logic to read and parse them too and put into the book`

1. **Identification**: I will create a function to identify external 80000hours.org linkposts from the markdown output. I can use the regex `r'(?:This is a linkpost for|Continue reading on.+?website|a link to|summary of).*?\[.+?\]\((https?://[^)]+80000hours\.org[^)]*)\)'` and similar patterns to extract the target URL.
2. **Scraping**: If such an external URL is found, we:
   - Call `_validate_url` but update it to allow `80000hours.org`.
   - `fetch(session, external_url)`.
   - Use `find_external_post_body(soup)` which will specifically handle `80000hours.org` (e.g. `soup.find('article')`).
   - Call `html_to_markdown` on the found body to get the real text.
   - Combine the new markdown with the original, or simply replace it with `f"{original_title}\n\n*This is an external post from {external_url}*\n\n{new_markdown}"` (or similar).
3. **Changes in `src/eahandbookcompiler/scraper.py`**:
   - Update `_validate_url` to allow `80000hours.org`.
   - Add a `find_external_post_body(soup, url)` function.
   - Update `scrape_post_content` to run the detection logic on `post.markdown`, and if it matches an 80000 hours link, fetch the external post, extract the body, and re-run `html_to_markdown(body)`, updating `post.markdown`.

Let's do this plan.
