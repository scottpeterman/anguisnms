# Components Web Interface

**Comprehensive hardware component inventory tracking and management**

## Overview

The Components module provides a dedicated web interface for viewing, searching, and analyzing hardware components extracted from device inventory captures. This complements the component display on individual device detail pages by providing network-wide visibility and advanced filtering.

## Features

### Dashboard View
- **Overall Statistics**
  - Total component count across all devices
  - Serial number coverage percentage
  - Unique device count with components
  - Real-time metrics from database

- **Type Distribution**
  - Visual bar charts showing component counts by type
  - Serial number coverage per type
  - Automatic sorting by component count

### Advanced Filtering
- **Search**: Free text search across component names, descriptions, serials, and device names
- **Type Filter**: Filter by component type (chassis, module, psu, fan, transceiver, etc.)
- **Vendor Filter**: Show components only from specific vendors
- **Serial Filter**: Show only components with or without serial numbers

### Component Table
- **Sortable Columns**
  - Component name and description
  - Component type with color coding
  - Serial number (monospace display)
  - Position/slot information
  - Parent device with clickable link
  - Vendor name
  - Extraction confidence indicator

- **Visual Indicators**
  - Color-coded type badges
  - Confidence bars (high/medium/low)
  - Serial number presence highlighting

### Pagination
- Configurable results per page (10-200)
- Page navigation controls
- Result count display

## Component Types

The system tracks these component types:

| Type | Color | Description |
|------|-------|-------------|
| chassis | Primary | Main device chassis or stack member |
| module | Secondary | Line cards, modules, blades |
| psu | Tertiary | Power supplies |
| fan | Success | Cooling fans |
| transceiver | Warning | SFP/QSFP transceivers |
| supervisor | Error | Supervisor/management modules |
| unknown | Neutral | Unclassified components |

## URL Structure

```
/components/                    # Main component inventory page
/components/?page=2             # Pagination
/components/?type=transceiver   # Filter by type
/components/?vendor=Cisco       # Filter by vendor
/components/?has_serial=yes     # Filter by serial presence
/components/?search=PWR         # Search components
```

## API Endpoints

### Statistics API
```
GET /components/api/stats
```
Returns component distribution, top devices, and vendor coverage statistics.

**Response:**
```json
{
  "type_distribution": [
    {"type": "transceiver", "count": 1200, "with_serials": 980}
  ],
  "top_devices": [
    {"name": "core-sw-1", "component_count": 45}
  ],
  "vendor_coverage": [
    {"vendor": "Cisco", "total": 850, "with_serials": 780, "coverage_pct": 91.8}
  ]
}
```

### Search API
```
GET /components/search?q=SFP
```
Quick search returning up to 50 matching components.

### Type Lookup
```
GET /components/api/by-type/transceiver
```
Get all components of a specific type.

### Serial Lookup
```
GET /components/api/serial/ABC123456
```
Find component by exact serial number match.

## Integration Points

### Navigation
- Main sidebar under "Assets" section
- Direct link: `/components/`
- Active state highlighting when on components pages

### Device Detail Pages
- Component tab shows device-specific components
- Links from device view to component inventory
- "View Full Inventory" button

### Database Queries
All queries use the `components` table with joins to:
- `devices` - Parent device information
- `vendors` - Vendor names
- Indexes on `device_id` for performance

## Use Cases

### 1. Transceiver/SFP Inventory
Filter by type "transceiver" to see all optical modules:
```
/components/?type=transceiver
```
Useful for:
- Planning upgrades
- Identifying spare parts needed
- Tracking optical inventory

### 2. EOL Component Tracking
Search for specific models approaching end-of-life:
```
/components/?search=WS-C3850
```
Filter results to find all affected devices.

### 3. Missing Serial Numbers
Find components without serials for audit purposes:
```
/components/?has_serial=no
```
Helps identify:
- Data quality issues
- Non-serialized components (fans, cables)
- Capture parsing failures

### 4. Vendor-Specific Inventory
View all components from a specific vendor:
```
/components/?vendor=Arista Networks
```
Useful for:
- Maintenance contract planning
- Vendor assessments
- Budget planning

### 5. Power Supply Audits
Filter to power supplies only:
```
/components/?type=psu
```
Check:
- Redundancy status
- Model standardization
- Replacement needs

## Future Enhancements

### Phase 1: Export & Reporting
- CSV export of filtered results
- PDF inventory reports
- Excel export with formatting

### Phase 2: EOL Database Integration
- Link component models to EOL database
- Flag components approaching EOL
- Automatic EOL notifications
- Migration planning tools

### Phase 3: Component Management
- Edit component details
- Add manual components
- Delete/archive components
- Bulk operations

### Phase 4: Advanced Analytics
- Component age tracking
- Failure rate analysis
- Cost tracking
- Warranty management
- Spare parts recommendations

### Phase 5: Lifecycle Management
- Replacement scheduling
- Maintenance history
- Component relationships (modules in chassis)
- Configuration change correlation

## Performance Considerations

- Pagination limits results to 10-200 per page (default 50)
- Database indexes on `device_id` for fast joins
- Type and vendor filters use indexed columns
- Search uses LIKE queries (consider FTS for large datasets)

## Database Schema

Components table structure:
```sql
CREATE TABLE components (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    serial TEXT,
    position TEXT,
    have_sn BOOLEAN DEFAULT 0,
    type TEXT,
    subtype TEXT,
    extraction_source TEXT,
    extraction_confidence REAL,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

CREATE INDEX idx_components_device ON components(device_id);
```

## Styling Notes

- Uses Material Design 3 design system
- Responsive layout (mobile-friendly)
- Color-coded type badges for quick identification
- Confidence indicators using color (green/yellow/red)
- Consistent with existing UI patterns

## Related Documentation

- **README_Inventory_Components.md** - Backend extraction system
- **README_DB_Loaders.md** - Database loading patterns
- **README_Fingerprinting.md** - TextFSM template development

---

**Created:** 2025-09-30  
**Status:** Production Ready  
**Blueprint:** `app/blueprints/components/`