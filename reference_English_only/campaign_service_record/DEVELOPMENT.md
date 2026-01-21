# Campaign Service Record - Development Guide

## Architecture Overview

### Design Principles

1. **Separation of Concerns**
   - Core logic (data access, aggregation) independent of presentation
   - API layer as clean interface between backend and frontend
   - Frontend controllers for each page/feature

2. **Read-Only Data Access**
   - Never modifies Campaign Tracker files
   - Defensive programming: handles missing/corrupt data gracefully
   - Cache invalidation based on file modification time

3. **Single Source of Truth**
   - `campaign_completion_state.json` determines visible campaigns
   - All other JSONs provide supplementary data
   - Missing supplementary data degrades gracefully

### Module Responsibilities

```
app.py
  └─ Entry point, Flask setup, threading

config.py
  └─ Configuration management (paths, feature flags)

core/
  ├─ data_loader.py       # JSON file I/O and caching
  ├─ campaign_aggregator.py  # Business logic and data transformation
  └─ validation.py        # Data validation and schema checks

api/
  └─ routes.py            # REST endpoints for frontend

utils/
  ├─ combat_results.py    # Kill calculation (from Campaign Tracker)
  ├─ combat_results_html.py  # Combat grid HTML generation
  ├─ formatting.py        # String utilities
  └─ sorting.py           # Mission sorting

static/
  ├─ index.html           # SPA shell
  ├─ css/                 # Styles (global, landing, detail)
  ├─ js/
  │   ├─ api.js           # API client
  │   ├─ landing.js       # Landing page controller
  │   ├─ detail.js        # Detail page controller
  │   └─ main.js          # App controller and routing
  └─ images/              # Static assets
```

## Data Flow

### Campaign List (Landing Page)

```
User loads page
  ↓
main.js initializes app
  ↓
landing.js calls API.getCampaigns()
  ↓
routes.py:/api/campaigns
  ↓
CampaignAggregator.get_campaign_list()
  ↓
DataLoader.get_campaigns_with_progress()
  ↓
Filters campaigns from campaign_completion_state.json
  ↓
Aggregates metadata from campaign_events.json, mission_dates.json
  ↓
Returns list to frontend
  ↓
landing.js renders campaign items
```

### Campaign Detail

```
User clicks campaign
  ↓
main.js navigates to detail page
  ↓
detail.js calls API.getCampaignDetail(name)
  ↓
routes.py:/api/campaign/<name>
  ↓
CampaignAggregator.get_campaign_detail(name)
  ↓
DataLoader loads all relevant JSONs
  ↓
Aggregates:
  - Events (promotions, awards)
  - Debriefings HTML
  - Summary statistics (combat, missions, aircraft, career)
  ↓
Returns to frontend
  ↓
detail.js renders three columns
```

## Key Algorithms

### Campaign Filtering

Only campaigns with **non-empty** mission lists in `campaign_completion_state.json` are shown:

```python
def get_campaigns_with_progress(self):
    completion_state = self.get_campaign_completion_state()
    return [
        campaign for campaign, missions in completion_state.items()
        if missions  # Non-empty list
    ]
```

### Kill Calculation

Reuses Campaign Tracker's `calculate_kills_from_stats()`:

```python
# From cumulative stats of last mission
cumulative_stats = per_mission_stats[last_mission]
kills = calculate_kills_from_stats(cumulative_stats)
# Returns: {"Air": 15, "Ground": 22, ...}
```

### Mission Sorting

Uses Campaign Tracker's `smart_mission_sort_key()` to handle various mission ID formats:

- Numeric: `"01"`, `"02"`, ...
- Date-based: `"1941-07-02a"`, `"1941-07-02b"`, ...
- Mixed formats

## Adding New Features

### Add New Data Source

1. **Add loader method to `DataLoader`:**

```python
def get_new_data_source(self) -> Dict:
    data = self._load_json('new_data.json')
    return data or {}
```

2. **Use in `CampaignAggregator`:**

```python
def get_campaign_detail(self, campaign_name: str):
    # ... existing code ...
    new_data = self.loader.get_new_data_source()
    campaign_new_data = new_data.get(campaign_name, {})
```

3. **Add API endpoint (if needed):**

```python
@api_bp.route('/api/new_feature/<campaign_name>')
def get_new_feature(campaign_name: str):
    # ...
```

4. **Update frontend:**

```javascript
// In api.js
async getNewFeature(campaignName) {
    return this.get(`/new_feature/${encodeURIComponent(campaignName)}`);
}

// In detail.js
async loadNewFeature(campaign) {
    const feature = await API.getNewFeature(campaign.name);
    // Render...
}
```

### Add New Page

1. **Create HTML structure in `index.html`:**

```html
<div id="new-page" class="page" style="display: none;">
    <!-- Page content -->
</div>
```

2. **Create CSS file:**

```css
/* static/css/new-page.css */
```

3. **Create controller:**

```javascript
// static/js/new-page.js
const NewPage = {
    init() { /* ... */ },
    load() { /* ... */ }
};
```

4. **Update `main.js` routing:**

```javascript
showNewPage() {
    this.elements.newPage.style.display = 'block';
    // Hide others...
}
```

## Testing

### Manual Testing Checklist

- [ ] **Data Loading**
  - [ ] Handles missing `campaign_completion_state.json`
  - [ ] Handles empty campaigns list
  - [ ] Handles corrupt JSON files
  
- [ ] **Landing Page**
  - [ ] Displays all campaigns with missions
  - [ ] Shows correct mission counts
  - [ ] Click navigation works
  
- [ ] **Detail Page**
  - [ ] Loads campaign details correctly
  - [ ] Events render (promotions, awards)
  - [ ] Debriefings HTML displays
  - [ ] Summary statistics accurate
  - [ ] Back button works
  - [ ] PDF download shown (if available)
  
- [ ] **Error Handling**
  - [ ] Non-existent campaign → 404
  - [ ] Server error → user-friendly message
  - [ ] Network timeout → recovers gracefully

### Unit Testing (Future)

Example test structure:

```python
# tests/test_data_loader.py
import pytest
from core.data_loader import DataLoader

def test_load_completion_state(tmp_path):
    # Create test JSON
    json_file = tmp_path / "campaign_completion_state.json"
    json_file.write_text('{"kerch": ["01", "02"]}')
    
    loader = DataLoader(tmp_path)
    state = loader.get_campaign_completion_state()
    
    assert "kerch" in state
    assert len(state["kerch"]) == 2

def test_campaigns_with_progress_filter(tmp_path):
    # ...
```

## Performance Considerations

### Caching Strategy

- **JSON files cached in memory** with modification time tracking
- **Cache invalidation** on file change (5-second check interval)
- **No persistent cache** - fresh data on each app start

### Frontend Optimization

- **Lazy rendering** for large debriefings (future enhancement)
- **Minimal re-renders** - only update changed components
- **Event delegation** for dynamic lists

### Scalability

Current design supports:
- **~50 campaigns** without issues
- **~100 missions per campaign** without noticeable lag

For larger datasets:
- Implement pagination in debriefings
- Add virtual scrolling for long lists
- Consider backend pagination for campaign list

## Debugging

### Enable Debug Mode

Set environment variable:
```bash
# Development
python app.py  # Debug mode auto-enabled when not frozen
```

In `config.py`, debug mode enables:
- Detailed logging
- Flask debug output
- No file caching (always reload from disk)

### Common Issues

**"No campaigns found"**
- Check if `campaign_completion_state.json` exists
- Verify it contains non-empty mission lists
- Check Campaign Tracker ran successfully

**"Campaign not found" error**
- Verify campaign name matches key in JSONs exactly (case-sensitive internally)
- Check aggregator uses case-insensitive lookups

**Stale data displayed**
- Cache may not have invalidated yet
- Manually restart app or disable caching in `DataLoader`

**Port 5000 already in use**
- Change port in `config.py` or set `PORT` env var
- Kill existing process using port

### Logging

Logs are written to stdout. In production (frozen mode), redirect to file:

```bash
Campaign_Service_Record.exe > service_record.log 2>&1
```

## Code Style

### Python

- **PEP 8** compliance
- **Type hints** for function signatures
- **Docstrings** for public methods (Google style)
- **4 spaces** indentation

### JavaScript

- **ES6+** syntax
- **Async/await** for promises (no callbacks)
- **const/let** only (no var)
- **2 spaces** indentation
- **CamelCase** for class/constructor names
- **camelCase** for functions/variables

### CSS

- **BEM-like** naming for components (e.g., `.campaign-item`, `.campaign-item__name`)
- **Mobile-first** responsive design
- **CSS Grid** for layouts (no frameworks)

## Contributing Guidelines

1. **Branch Strategy**
   - `main` - production-ready code
   - `develop` - integration branch
   - `feature/*` - new features
   - `bugfix/*` - bug fixes

2. **Commit Messages**
   - Use conventional commits: `type(scope): message`
   - Types: `feat`, `fix`, `docs`, `refactor`, `test`
   - Example: `feat(api): add PDF availability endpoint`

3. **Pull Requests**
   - Include description of changes
   - Reference related issues
   - Update documentation if needed

## Future Enhancements

### Planned Features

- **V1.1**
  - [ ] Pilot name/photo customization
  - [ ] Campaign comparison view
  - [ ] Export campaign summary to JSON
  
- **V2.0**
  - [ ] Dark mode
  - [ ] Internationalization (DE, EN, RU)
  - [ ] Advanced filtering/sorting
  - [ ] Statistics charts (Chart.js)
  
- **V3.0**
  - [ ] Multi-pilot support
  - [ ] Custom report templates
  - [ ] Integration with PWCG

### Technical Debt

- [ ] Add comprehensive unit tests
- [ ] Add integration tests
- [ ] Implement error boundary for frontend
- [ ] Add loading skeletons (better UX)
- [ ] Optimize large debriefing rendering

## License

MIT License - See parent project for details
