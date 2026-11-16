---
title: Olympics Analysis API
emoji: 🏅
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: FastAPI backend of the OlympicsAnaylsis website (1960-2026)
---

# Olympics Analysis API

FastAPI backend for the **OlympicsAnaylsis** website: every Summer (1960–2024) and Winter (1960–2026) Olympic Games, with results, matches, bouts, heats, medal tables, countries and athletes.

The SQLite warehouse (about 2.7 GB) is downloaded on first boot from the dataset repo named by the `WAREHOUSE_REPO` variable. Interactive docs: `/docs`.
