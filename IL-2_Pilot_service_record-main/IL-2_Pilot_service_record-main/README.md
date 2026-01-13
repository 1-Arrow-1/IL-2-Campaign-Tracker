# IL-2 Pilot Service Record

This project exposes a small Flask web application for viewing a pilot's service record from the *IL-2 Sturmovik: Battle of Stalingrad* series.  The app reads the game's `cp.db` SQLite database and renders pilot information through a small JSON API and static front‑end.

## Features
- Automatically locates the game's installation on Windows or lets the user supply the path.
- Serves static assets used by the front‑end, including pilot photos and rank/award images.
- Provides REST endpoints for pilot lists, service records, statistics and sorties.

## Setup
1. **Unpack static assets**
   The `static` directory contains compressed archives (`achievements.7z.*`, `squadrons.zip`, `standard_charactersranks.zip`).  Extract these archives so the folders `achievements`, `squadrons` and `standard_charactersranks` exist under `static/`.

2. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the server**
   ```bash
   python app.py
   ```
   The application will attempt to locate the IL‑2 installation automatically.  If it cannot, supply the path through the UI and it will be stored in a configuration file under `~/.il2_pilot_passport/config.json`.

## Project Structure
- `app.py` – Flask entry point and application setup.
- `routes.py` – API endpoints used by the front‑end.
- `config.py` – Helper functions for reading and writing configuration.
- `il2_core.py` – Utilities for interpreting game data such as ranks and awards.
- `static/` – Front‑end files and image assets.

## License
This project is released under the [MIT License](LICENSE.md).
