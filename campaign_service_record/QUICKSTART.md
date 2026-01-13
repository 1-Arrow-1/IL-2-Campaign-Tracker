# Campaign Service Record - Quick Start Guide

## 5-Minute Setup

### Prerequisites

- Windows 10 or later
- IL-2 Campaign Tracker v2.0+ installed and run at least once

### Installation

1. **Download** or build `Campaign_Service_Record.exe`

2. **Place** in same directory as Campaign Tracker:
   ```
   IL2_Campaign_Tracker/
   ├── IL2_Campaign_Tracker.exe
   ├── Campaign_Service_Record.exe    ← Place here
   ├── campaign_completion_state.json
   ├── campaign_events.json
   └── ...
   ```

3. **Run** `Campaign_Service_Record.exe`

4. **Browser opens automatically** showing your campaigns

That's it!

---

## Development Setup

### 1. Install Dependencies

```bash
cd campaign_service_record
pip install -r requirements.txt
```

### 2. Run Development Server

```bash
python app.py
```

Server starts at http://127.0.0.1:5000

Browser opens automatically.

### 3. Build Executable (Optional)

```bash
# Windows
build_exe.bat

# Manual
pyinstaller campaign_service_record.spec
```

Output: `dist/Campaign_Service_Record/`

---

## Project Structure (Simplified)

```
campaign_service_record/
├── app.py                  # Main entry point
├── config.py               # Configuration
│
├── core/                   # Business logic
│   ├── data_loader.py      # JSON file reader
│   └── campaign_aggregator.py  # Data transformation
│
├── api/                    # REST API
│   └── routes.py           # Flask endpoints
│
├── utils/                  # Campaign Tracker utilities
│   ├── combat_results.py   # Kill calculations
│   └── sorting.py          # Mission sorting
│
└── static/                 # Frontend
    ├── index.html          # SPA shell
    ├── css/                # Styles
    └── js/                 # Controllers
```

---

## Common Tasks

### Add New Campaign Data Field

**1. Backend (Python):**

```python
# In core/campaign_aggregator.py
def get_campaign_detail(self, campaign_name: str):
    # ... existing code ...
    
    # Add new field
    new_field = self._calculate_new_field(campaign_decoded)
    
    return {
        # ... existing fields ...
        'new_field': new_field
    }
```

**2. Frontend (JavaScript):**

```javascript
// In static/js/detail.js
renderSummary(summary) {
    // ... existing code ...
    
    // Add new section
    if (summary.new_field) {
        const section = this.createSummarySection('New Feature',
            this.renderNewField(summary.new_field)
        );
        this.elements.summaryContent.appendChild(section);
    }
}
```

### Debug Data Loading Issues

**Enable debug logging:**

```python
# In config.py
self.debug = True  # Force debug mode
```

**Check data directory:**

```python
# In app.py, add after create_app():
print(f"Data dir: {config.data_dir}")
print(f"JSON files: {list(config.data_dir.glob('*.json'))}")
```

### Change Port

**Option 1: Environment variable**

```bash
set PORT=8080
python app.py
```

**Option 2: Edit config.py**

```python
# In config.py, __init__():
self.port = 8080  # Change from 5000
```

---

## Troubleshooting

### "No campaigns found"

**Cause:** Campaign Tracker hasn't generated data yet.

**Solution:** Run Campaign Tracker first, then restart Service Record.

### "Port 5000 already in use"

**Cause:** Another app using port 5000.

**Solution:** Change port (see above) or kill other process:

```bash
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### Stale data displayed

**Cause:** Cached JSON files not refreshed.

**Solution:** Restart app. Cache refreshes every 5 seconds.

### Build fails with PyInstaller

**Cause:** Missing dependencies or path issues.

**Solution:**

```bash
# Clean and rebuild
rmdir /s /q build dist
pip install --upgrade pyinstaller
pyinstaller --clean campaign_service_record.spec
```

---

## Next Steps

- **Read** [README.md](README.md) for full documentation
- **Explore** [DEVELOPMENT.md](DEVELOPMENT.md) for architecture details
- **Customize** CSS in `static/css/` for different look
- **Extend** with new features (see DEVELOPMENT.md)

---

## Support

**Issues:** Check logs in console or `service_record.log`

**Questions:** Refer to DEVELOPMENT.md or README.md

**Feature Requests:** See DEVELOPMENT.md § Future Enhancements
