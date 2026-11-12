# deckly-social

Scheduled Instagram posts for @decklymx. `queue.json` is the calendar (times in Mexico City,
UTC-6); `publish.py` runs every 15 minutes from GitHub Actions and publishes what is due through
the official Instagram API; `published.json` records what already went out. Media in `media/` is
served by GitHub Pages so Instagram can fetch it.
