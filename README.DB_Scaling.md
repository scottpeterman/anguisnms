Got it 👍 — I can bring your **README.DB.md section** up to date with the actual schema you have now (`assets.db`), plus insert a **maintenance checklist** and **scaling expectations** so future you (or others) know what to expect.

Here’s a cleaned and extended version:

---

# Database Architecture – Anguis

The **Anguis platform database** (`assets.db`) provides the backbone for network discovery, configuration capture, and asset management.
It is implemented in **SQLite 3.45+**, using normalized relational tables, indexed views, and full-text search (FTS5) for capture content.

---

## Core Tables

* **devices**
  Primary device inventory.
  Fields: name, normalized_name, site_code, vendor_id, device_type_id, role_id, model, os_version, management_ip, stack info, source metadata.
  Foreign keys: sites, vendors, device_types, device_roles.

* **sites**
  Site inventory, keyed by `code`.

* **vendors**
  Manufacturer definitions.

* **device_types**
  Communication profiles (Netmiko/NAPALM drivers, transport, default port).

* **device_roles**
  Device classifications with optional expected port count and infra flag.

* **components**
  Hardware component inventory (serials, slots, type, confidence, extraction source).

* **stack_members**
  Stack details per device (serial, model, position, is_master).

* **device_serials**
  Serial number registry (primary vs. secondary).

---

## Capture & Fingerprinting

* **device_captures_current**
  Latest capture per device/type. Uniqueness constraint `(device_id, capture_type)`.

* **capture_snapshots**
  Historical archive of captures with content and hash.

* **capture_changes**
  Diff history between snapshots. Tracks added/removed lines, diff path, severity.

* **fingerprint_extractions**
  Fingerprinting audit log (timestamp, template, score, success, fields extracted).

* **bulk_operations**
  Audit log of batch operations (filters, operation_values, rollback flag).

---

## Search & Indexing

* **capture_fts (FTS5 virtual table)**
  Full-text search across `capture_snapshots.content`.
* **Indexes**

  * `idx_bulk_ops_timestamp` on `bulk_operations.executed_at`
  * `idx_changes_device_time` on `capture_changes(device_id, detected_at)`
  * `idx_snapshots_device_type_time` on `(device_id, capture_type, captured_at)`

---

## Optimized Views

* **v_device_status** – full device info with latest captures, fingerprints, roles, types.
* **v_capture_coverage** – capture type coverage, success/failure counts, success rate %.
* **v_capture_details** – joined view of capture metadata, device/site/vendor info.
* **v_site_inventory** – summarized site-level inventory (counts, infra %, vendor diversity).

---

## Maintenance To-Do

* [ ] Run `VACUUM` weekly on `assets.db` to defragment and shrink.
* [ ] Run `ANALYZE` after large batch loads to refresh query planner stats.
* [ ] Rotate `capture_snapshots` by moving >90-day-old data into archive storage.
* [ ] Periodically `REINDEX` capture FTS tables for performance.
* [ ] Monitor file size: keep under ~10GB for optimal SQLite performance.
* [ ] Use `PRAGMA journal_mode=WAL;` for concurrent readers + batch writer safety.

---

## Scaling Expectations

### Stage 1 – SMB / Lab (0–2k devices)

* **SQLite only**
* Millions of rows supported, sub-second queries with indexes.
* Single writer process, batch loads preferred.

### Stage 2 – Enterprise Mid (2k–10k devices)

* SQLite still viable with discipline.
* 30–60 days of capture archives (~5M rows) manageable.
* Maintain indexes, batch inserts, archive aggressively.

### Stage 3 – Large Enterprise (10k–50k devices)

* Migrate to **MariaDB/MySQL** for concurrency and clustering.
* Full schema ports cleanly; only FTS5 → FULLTEXT replacement needed.
* Gains: multi-writer support, replication, HA.

### Stage 4 – Multi-Region / >50k devices

* Hybrid: keep operational DB in MariaDB/MySQL, offload long-term archives into S3/Parquet/ClickHouse.
* Use the built-in **current/archive split** to manage DB footprint.

---

✅ This keeps the README current with the schema you actually have now, plus it explicitly documents **maintenance tasks** and **scaling thresholds**.

Do you want me to also generate a **diagram (ERD + scaling roadmap)** you can drop into the repo/README to visually show “SQLite → MySQL → Hybrid”?


Medical References:
1. None — DOI: file-B4JSJhiJBHpbwZpuGzHk9E