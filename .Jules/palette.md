## 2024-05-24 - Hiding Click docstring arguments from `--help` output
**Learning:** `click` natively includes the entire docstring of the command function in the `--help` output. For CLI applications, developer-focused information like `Args:` and `Raises:` clutters the user help text.
**Action:** Use `click`'s `\f` (form feed) escape character in the docstring. `click` truncates the help output at `\f`, hiding anything below it from the user while preserving the full docstring for documentation generators and linters like `ruff`. Do NOT use raw string prefixes (`r"""`) for the docstring, as `r"\f"` evaluates to a literal backslash and the letter "f", which Click will not recognize as a truncation marker. Instead, use standard strings (`"""`) and suppress the resulting `D301` (missing `r` prefix) linting rule in `pyproject.toml` (under `tool.ruff.lint.per-file-ignores`) to prevent CI failures.

## 2025-03-24 - Unwrapping Outbound Redirects for Offline Readability
**Learning:** Platform-specific outbound link redirects (like `/out?url=...`) cause severe UX issues for users consuming content offline (e.g., via exported PDFs or EPUBs), as the redirect service requires an internet connection to resolve to the true destination URL.
**Action:** When scraping content intended for offline consumption, proactively unwrap outbound link redirects by parsing the URL query string (using `urllib.parse.parse_qs`) and extracting the target URL, replacing the redirect link with the direct link before generating the final artifact.

## 2025-03-25 - Improve CLI Progress Bar Color Contrast
**Learning:** Using the same color (e.g., `fg="blue"`) for both the filled and empty characters in a CLI progress bar significantly reduces visual contrast, making it harder to read the bar's progress at a glance, especially on lower-contrast dark terminal backgrounds.
**Action:** Always ensure high visual contrast between filled and empty portions of a progress bar. For example, in `click.progressbar`, use a distinct color or apply `dim=True` to the `empty_char` (e.g., `empty_char=click.style("░", dim=True)`) to make the filled portion clearly stand out.

## 2025-03-26 - Add helpful call-to-action after CLI commands
**Learning:** Users often run a partial CLI command (like `scrape`) and aren't immediately sure what the next logical command is (like `convert`), increasing cognitive load and reducing feature discoverability.
**Action:** Always append a visually distinct "Hint: Run <next command>" message with a helpful call-to-action to success outputs of intermediate commands, guiding the user smoothly through the intended multi-step workflow.

## 2026-03-28 - Add fallback alt text to images for offline accessibility
**Learning:** When HTML `<img>` tags without `alt` attributes are converted to Markdown (rendered as `![](url)`) and then compiled into offline formats like EPUB or PDF, screen readers will often read out the raw, unhelpful image URL. This severely degrades the accessibility of offline documents.
**Action:** Always ensure a fallback `alt` text (e.g., `alt="Image"`) is assigned to images during HTML sanitization if they lack one. This prevents screen readers from vocalizing long image URLs to visually impaired users.

## 2025-03-29 - Improve Terminal Color Contrast for Accessibility
**Learning:** Standard ANSI blue (`\033[34m` or `fg="blue"`) has notoriously poor contrast and is often unreadable against default dark terminal backgrounds, causing accessibility issues for informational UI text and progress indicators.
**Action:** When printing status messages or filling progress bars in CLI tools, use cyan (`fg="cyan"`) instead of blue. Cyan has a much higher relative luminance, ensuring clear readability and sufficient visual contrast on dark backgrounds while remaining distinctly different from success (green) or error (red) colors.

## 2025-03-30 - Add title attribute to embedded iframes for screen reader accessibility
**Learning:** When embedded content tags like `<iframe>`, `<object>`, or `<embed>` lack a `title` attribute, screen readers navigating the compiled EPUB or PDF often read out the raw source URL or unhelpfully announce "frame", causing a poor accessibility experience.
**Action:** Always ensure a fallback `title` attribute (e.g., `title="Embedded content"`) is assigned to embedding tags during HTML sanitization if they lack one. This provides immediate context to visually impaired users reading the offline document.

## 2026-04-01 - Expand `<abbr>` tags for offline accessibility
**Learning:** During HTML-to-Markdown conversion, `<abbr>` tags are dropped, leaving only their inner text. Offline readers (e.g. in EPUB or PDF) cannot hover to see the `title` attribute, severely degrading the context and accessibility of acronyms and abbreviations.
**Action:** Before converting HTML to Markdown, always inspect `<abbr>` tags. If an `<abbr>` tag has a `title` attribute, expand its text content by explicitly appending the title in parentheses (e.g., `element.string = f"{element.get_text()} ({title})"`). This ensures the abbreviation's full meaning is preserved in the offline text.

## 2025-03-31 - Preserve icon-only links during Markdown conversion
**Learning:** During HTML-to-Markdown conversion with tools like `markdownify`, `<a>` tags that rely solely on `aria-label` or `title` attributes (e.g., icon-only links with `<i class="icon"></i>`) are omitted from the output because they lack visible text content. This silently breaks link accessibility and navigation in generated offline formats like EPUB or PDF.
**Action:** Before converting HTML to Markdown, always inspect `<a>` tags. If a link has no visible text and contains no images, extract its `aria-label` or `title` attribute and explicitly assign it as the element's text content. This ensures the link and its accessible name are properly rendered in the final Markdown.

## 2025-04-02 - Preserve empty alt attributes for decorative images
**Learning:** While it is important to add fallback `alt` text to images that *lack* the attribute, images that explicitly define an empty alt text (`alt=""`) are intended to be decorative. The `alt=""` attribute is an established accessibility pattern that tells screen readers to silently skip the image. Using a generic truthiness check (e.g., `not element.get("alt")`) accidentally overwrites these empty attributes with a fallback like `"Image"`, which forces screen readers to vocalize useless, noisy descriptions for decorative graphics.
**Action:** When adding fallback `alt` attributes during HTML sanitization, strictly check if the attribute is missing (e.g., `element.get("alt") is None`) rather than evaluating its truthiness. This preserves intentionally empty `alt` attributes, keeping decorative images silent and reducing screen reader noise.

## 2026-04-03 - Preserve media tags as standard links for offline accessibility
**Learning:** When HTML `<video>` and `<audio>` tags without text content are converted to Markdown (e.g. using `markdownify`), they are often stripped out or rendered as unhelpful empty links `[](src)`. This completely removes access to the media for users reading offline formats (like EPUB or PDF).
**Action:** Before converting HTML to Markdown, convert `<video>` and `<audio>` tags into standard `<a>` tags. Move the `src` attribute to `href` and explicitly assign a fallback text description using the original tag's `aria-label`, `title`, or simply the tag name. This ensures the media remains accessible as a clear, descriptive link in the generated offline formats.

## 2025-04-04 - Preserve `<summary>` block structure for offline reading
**Learning:** `markdownify` drops `<details>` and `<summary>` tags during HTML-to-Markdown conversion, causing collapsible/spoiler content to blend seamlessly into surrounding text without visual indication. This creates a confusing reading experience in offline formats (EPUB/PDF) where the content was originally hidden.
**Action:** Before converting HTML to Markdown, convert `<summary>` tags to `<strong>` and prepend a visual indicator like `▶ ` (e.g., `element.name = "strong"; element.insert(0, "▶ ")`). This preserves the semantic structure visually, indicating to readers of offline formats that the following block of text is supplementary or a spoiler.

## 2025-04-05 - Preserve semantic inline tags (kbd, q, cite, del, s, sup, sub) during HTML to Markdown conversion
**Learning:** Tools like `markdownify` either drop semantic inline tags (`<sup>`, `<sub>`, `<del>`, `<s>`, `<kbd>`, `<q>`, `<cite>`) entirely or convert them into plain text, stripping important visual and semantic meaning. For offline EPUB and PDF reading, this can lead to confusing text (e.g., math `E=mc2` instead of `E=mc²` or unstyled keyboard shortcuts).
**Action:** Before passing HTML to a markdown converter, explicitly map semantic inline tags into their markdown equivalents or explicitly wrap them in their raw HTML tags. For example, convert `<sup>` and `<sub>` tags to pandoc's `^text^` and `~text~` superscript/subscript syntax respectively, and wrap tags like `<kbd>`, `<q>`, and `<cite>` inside `<kbd>text</kbd>` explicitly.

## 2024-05-24 - Preserve semantic text tags in Markdown extraction
**Learning:** Tools like `markdownify` often aggressively strip inline semantic HTML tags (`<mark>`, `<u>`, `<ins>`) from scraped content because standard Markdown doesn't have native equivalents for them all. This causes visual cues like highlights, underlines, and insertions to be completely lost when readers view the content offline in an EPUB or PDF.
**Action:** Always maintain a sanitize allowlist for meaningful inline tags and wrap them explicitly before passing to Markdown converters, ensuring they are passed through as raw HTML so downstream tools (like Pandoc) can process them properly and render them in the final accessible document.

## 2025-04-06 - Enable `-h` alias for CLI help output
**Learning:** By default, `click` only registers the `--help` flag. Users accustomed to typical command-line interfaces often instinctively type `-h` to view options. When the alias is missing, users receive an error (`Error: No such option: -h`), increasing friction and cognitive load.
**Action:** Always explicitly enable the `-h` alias for help output in `click` applications by passing `context_settings={"help_option_names": ["-h", "--help"]}` to the `@click.group` or `@click.command` decorators.
