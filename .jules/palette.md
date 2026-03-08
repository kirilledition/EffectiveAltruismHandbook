## 2024-03-24 - Provide visual feedback for long running CLI tasks
**Learning:** During testing of the `scrape_all` functionality without `--verbose` flag, the user experience suffered significantly due to the lack of any feedback. The program appeared to be frozen.
**Action:** Implemented `click.progressbar` for iterative fetching loops during non-verbose mode. Next time, always ensure long running CLI tasks have explicit loading or progress indicators, especially when fetching resources over the network.
## 2025-03-07 - Provide explicit loading feedback for initial network requests
**Learning:** Users lack feedback during the initial `scrape_handbook_index` network request when running without the `--verbose` flag, causing the CLI to appear frozen for several seconds before the progress bar appears.
**Action:** Added explicit, non-verbose loading feedback (`click.secho(..., nl=False)`) for the initial network request to improve perceived performance and keep the interface smooth.
## 2025-03-08 - Provide explicit loading feedback for slow conversion tasks
**Learning:** During testing of `convert` and `build` commands, it was discovered that EPUB and PDF conversions take significant time with absolutely zero visual feedback, causing the CLI to appear completely frozen for an extended period.
**Action:** Added explicit loading feedback (`click.secho(..., nl=False)`) wrapped around `convert_to_epub`, `convert_to_pdf`, and `build_all` in `main.py` so users know that intensive background work is actively progressing.
