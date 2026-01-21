# IL-2 Campaign Service Record

A standalone web-based viewer for IL-2 Sturmovik campaign pilot service records.

## Project Structure

```
campaign_service_record/
├── app.py                          # Flask application entry point
├── config.py                       # Configuration management
├── requirements.txt                # Python dependencies
├── campaign_service_record.spec    # PyInstaller specification
├── build_exe.bat                   # Build script for Windows
├── README.md                       # This file
│
├── core/                           # Core business logic
│   ├── __init__.py
│   ├── data_loader.py              # JSON file loading with caching
│   ├── campaign_aggregator.py     # Data aggregation and transformation
│   └── validation.py               # Data validation and schema checks
│
├── api/                            # Flask API routes
│   ├── __init__.py
│   └── routes.py                   # REST endpoints
│
├── utils/                          # Shared utilities (from Campaign Tracker)
│   ├── __init__.py
│   ├── combat_results.py           # Kill calculation logic
│   ├── combat_results_html.py     # Combat results HTML generation
│   ├── formatting.py               # String formatting utilities
│   └── sorting.py                  # Mission sorting logic
│
└── static/                         # Frontend assets
    ├── index.html                  # Landing page (SPA shell)
    ├── css/
    │   ├── main.css               # Global styles
    │   ├── landing.css            # Landing page styles
    │   └── detail.css             # Campaign detail page styles
    ├── js/
    │   ├── main.js                # Application initialization
    │   ├── api.js                 # API client
    │   ├── landing.js             # Landing page controller
    │   └── detail.js              # Detail page controller
    └── images/
        └── placeholder_pilot.png   # Default pilot photo
```

## Architecture

### Data Flow
```
User Request
    ↓
Flask Routes (api/routes.py)
    ↓
Campaign Aggregator (core/campaign_aggregator.py)
    ↓
Data Loader (core/data_loader.py)
    ↓
JSON Files (campaign_completion_state.json, etc.)
```

### Key Design Principles

1. **Read-Only Access**: Never modifies Campaign Tracker data
2. **Single Source of Truth**: `campaign_completion_state.json` determines visible campaigns
3. **Defensive Programming**: Graceful handling of missing/corrupt JSON files
4. **Lazy Loading**: Data loaded on-demand, cached intelligently
5. **Separation of Concerns**: Clear boundaries between data access, business logic, and presentation

## Dependencies

- Flask 2.3.0+ - Web framework
- Python 3.11+ - Runtime

All dependencies are listed in `requirements.txt`

## Building

### Development Mode

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
```

Application will open automatically at http://127.0.0.1:5000

### Production Build (EXE)

```bash
# Windows
build_exe.bat

# Manual PyInstaller
pyinstaller campaign_service_record.spec
```

Output: `dist/Campaign_Service_Record/Campaign_Service_Record.exe`

## Deployment

Place the built executable in the same directory as the IL-2 Campaign Tracker.
The tool will automatically read JSON files from the current directory.

```
IL2_Campaign_Tracker/
├── IL2_Campaign_Tracker.exe
├── Campaign_Service_Record.exe    ← This tool
├── campaign_completion_state.json
├── campaign_events.json
├── campaigns_decoded.json
├── campaign_mission_dates.json
└── reports/
```

## Configuration

No additional configuration required. The tool auto-detects JSON files in the working directory.

**Optional**: Set `DATA_DIR` environment variable to specify a custom data directory.

## Usage

1. Ensure Campaign Tracker has run at least once (generates JSON files)
2. Launch `Campaign_Service_Record.exe`
3. Browser opens automatically showing available campaigns
4. Click any campaign to view detailed service record

## Troubleshooting

**"No campaigns found"**
- Campaign Tracker must run first to generate data
- Check that `campaign_completion_state.json` exists

**Missing campaign details**
- Verify `campaign_events.json` and `campaigns_decoded.json` exist
- Check Campaign Tracker logs for processing errors

**Application won't start**
- Ensure no other application is using port 5000
- Check that Python 3.11+ is installed (dev mode)

## Technical Notes

### JSON File Dependencies

| File | Purpose | Fallback if Missing |
|------|---------|---------------------|
| `campaign_completion_state.json` | Campaign list filter | Empty list (no campaigns) |
| `campaign_events.json` | Awards/promotions/debriefings | Show warning, skip events |
| `campaigns_decoded.json` | Statistics/kills | Show warning, skip stats |
| `campaign_mission_dates.json` | Mission metadata | Generic display names |

### Performance Considerations

- JSON files cached in memory with file modification time tracking
- Large campaigns (30+ missions) use pagination in debriefings
- Frontend lazy-loads campaign details on navigation

### Extensibility

Adding new data sources:
1. Add loader method to `core/data_loader.py`
2. Update aggregator in `core/campaign_aggregator.py`
3. Extend API in `api/routes.py`
4. Update frontend controllers

## License

MIT License - See parent project for details

## Credits

Built on the IL-2 Campaign Tracker by Alex
Reuses combat results calculation logic and utilities from the Campaign Tracker project.
