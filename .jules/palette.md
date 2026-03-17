## 2024-03-24 - Provide visual feedback for long running CLI tasks
**Learning:** During testing of the `scrape_all` functionality without `--verbose` flag, the user experience suffered significantly due to the lack of any feedback. The program appeared to be frozen.
**Action:** Implemented `click.progressbar` for iterative fetching loops during non-verbose mode. Next time, always ensure long running CLI tasks have explicit loading or progress indicators, especially when fetching resources over the network.
## 2025-03-07 - Provide explicit loading feedback for initial network requests
**Learning:** Users lack feedback during the initial `scrape_handbook_index` network request when running without the `--verbose` flag, causing the CLI to appear frozen for several seconds before the progress bar appears.
**Action:** Added explicit, non-verbose loading feedback (`click.secho(..., nl=False)`) for the initial network request to improve perceived performance and keep the interface smooth.
## 2025-02-27 - Added UI progress feedback for long-running CLI tasks
**Learning:** During long running tasks like PDF or Epub generation in a CLI via external tools (e.g. pandoc), the lack of visual feedback makes the interface seem frozen, reducing user confidence in the application's stability.
**Action:** Always provide explicit, immediate progress feedback in CLI outputs (e.g. using `click.secho(..., nl=False)`) before invoking long-running synchronous functions.
## 2025-03-11 - Add explicitly truncated item_show_func to long-running CLI tasks
**Learning:** Using `click.progressbar` for iterative HTTP requests without displaying the current item feels like a static UI on large datasets. Providing an `item_show_func` that aggressively truncates strings (e.g., to ~35 characters) prevents line wrapping/flickering while providing crucial contextual feedback.
**Action:** Always provide an `item_show_func` for `click.progressbar` tasks spanning over a few seconds. When iterating over futures asynchronously (e.g., `concurrent.futures.as_completed`), explicitly update `bar.current_item = item.title` before `bar.update(1)` so the user sees which tasks are finishing.
## 2025-03-24 - Improve CLI UX by wrapping unhandled exceptions
**Learning:** Leaking overwhelming raw Python stack traces to users on unexpected failures provides a poor user experience in a CLI tool.
**Action:** Catch unhandled `Exception` instances at the command level and raise `click.ClickException(str(e)) from e` to display a clean, actionable error message.
## 2025-03-24 - Improve CLI UX by surfacing subprocess error outputs
**Learning:** When invoking external tools like `pandoc` via `subprocess.run()`, unhandled `CalledProcessError`s default to generic "command returned non-zero exit status" messages, hiding the actual failure reason (e.g., missing CSS, syntax error). This leaves users confused.
**Action:** Always capture `stderr` (e.g., `capture_output=True, text=True`) and surface it in the exception message so that CLI error handlers (`click.ClickException`) can provide actionable feedback.
## 2025-03-24 - Added visual feedback icons to CLI loading states
**Learning:** Adding explicit checkmarks (✓) and crosses (✗) to success/error CLI output messages makes the terminal logs significantly more scannable and intuitive for the user, improving the overall developer experience.
**Action:** When printing status messages (like 'Done' or 'Failed') in CLI tools, always prefix them with appropriate visual icons to provide immediate, clear feedback.
