# Thor Ports

A static catalog of Bill's native Android / AYN Thor game ports. `build.py` (Python 3, stdlib only) reads each repo's
GitHub description, latest release (APK / Flatpak assets) and README screenshots, and writes `site/index.html` plus one
detail page per port. A GitHub Actions workflow rebuilds and deploys it to GitHub Pages daily, on every push, and on demand.

## Add a port

Add one line to `ports.json`:

```json
{"repo": "My-New-Port-Android", "tagline": "One sentence taken from the README."}
```

Commit and push; the next workflow run picks it up. The owner is set once at the top of the file.

## Build locally

```
python3 build.py        # writes site/
```

Set `GITHUB_PERSONAL_ACCESS_TOKEN` to avoid the unauthenticated API rate limit (60 requests/hour). Repos without a
release or screenshots still render, with a "no release yet" button and placeholder screens.

## Publish with GitHub Pages

1. Create a repo: `sirbilliams.github.io` (site at `https://sirbilliams.github.io/`) or `thor-ports`
   (site at `https://sirbilliams.github.io/thor-ports/`; all links are relative, so both work).
2. Push this directory to it.
3. Settings > Pages > Build and deployment > Source: **GitHub Actions**.
4. Run the "Build and deploy site" workflow once (Actions tab > Run workflow). It also runs daily.

The workflow uses the built-in `GITHUB_TOKEN`, which covers public repos only; for private repos add a PAT secret.

Screenshots in `docs/` are from a local build.
