# Hania prospect demo pages

One private demo page per prospect, built by the Hania "Demo Page Builder" agent.

- `prospects/<slug>.json`: page content, written by the agent (only files it edits).
- `template.html` + `build.py`: Netlify runs `python3 build.py` and publishes `out/`.
- A page that fails validation shows a BUILD ERROR page listing the problems; other pages are unaffected.
- Live at https://hania-demos.netlify.app/<slug>/ (noindex).
