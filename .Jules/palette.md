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
