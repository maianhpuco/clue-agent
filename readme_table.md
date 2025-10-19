### Ontology Cache Database Tables

Location: `documents/ontology_cache.db` (override with `ONTOLOGY_DB_PATH`). The database stores search activity, returned results, and post-processed extractions.

---

## Table: `searches`
- Purpose: One row per MCP tool invocation (e.g., `search_literature`, `search_terminology`).
- Relationships: Parent of `results` and `extractions` (via `search_id`).

| Column        | Type     | Notes |
|---------------|----------|-------|
| `id`          | INTEGER  | Primary key, autoincrement |
| `keyword`     | TEXT     | User keyword/query |
| `source`      | TEXT     | Provider key (e.g., `europe_pmc`, `ncbo_bioportal`) |
| `tool_name`   | TEXT     | MCP tool name used for this search |
| `max_results` | INTEGER  | Requested max results |
| `args_json`   | TEXT     | Full argument payload (JSON) |
| `requested_at`| TEXT     | UTC timestamp (`CURRENT_TIMESTAMP`) |

Example:
```sql
SELECT * FROM searches
ORDER BY datetime(requested_at) DESC
LIMIT 50;
```

---

## Table: `results`
- Purpose: Individual hits returned by a specific search.
- Relationships: Child of `searches` (FK `search_id`).
- Uniqueness: `UNIQUE(search_id, title, url)` prevents duplicates within a search.

| Column        | Type     | Notes |
|---------------|----------|-------|
| `id`          | INTEGER  | Primary key, autoincrement |
| `search_id`   | INTEGER  | FK to `searches.id` |
| `title`       | TEXT     | Result title (may be empty) |
| `url`         | TEXT     | Canonical URL (may be empty) |
| `published`   | TEXT     | Provider-published date (string) |
| `license`     | TEXT     | License string if present |
| `snippet`     | TEXT     | Short text/snippet for preview |
| `payload_json`| TEXT     | Full raw provider item (JSON) |

Example (join with search metadata and order by newest search):
```sql
SELECT r.*, s.keyword, s.source, s.requested_at
FROM results r
JOIN searches s ON s.id = r.search_id
ORDER BY datetime(s.requested_at) DESC, r.id DESC
LIMIT 100;
```

---

## Table: `extractions`
- Purpose: Post-processed artifacts derived from a search (e.g., consolidated evidence, ontology items, summaries).
- Relationships: Child of `searches` (FK `search_id`).

| Column        | Type     | Notes |
|---------------|----------|-------|
| `id`          | INTEGER  | Primary key, autoincrement |
| `search_id`   | INTEGER  | FK to `searches.id` |
| `extractor`   | TEXT     | Extraction routine identifier |
| `keyword`     | TEXT     | Keyword associated with the extraction |
| `content_json`| TEXT     | Extracted structured content (JSON) |
| `created_at`  | TEXT     | UTC timestamp (`CURRENT_TIMESTAMP`) |

Example (latest extractions first):
```sql
SELECT * FROM extractions
ORDER BY datetime(created_at) DESC
LIMIT 50;
```

---

## Common Queries
- Latest searches for a specific keyword and source:
```sql
SELECT * FROM searches
WHERE keyword = 'Lymph node metastasis' AND source = 'europe_pmc'
ORDER BY datetime(requested_at) DESC
LIMIT 20;
```

- Results for the newest search of a keyword (all sources):
```sql
WITH latest AS (
  SELECT id
  FROM searches
  WHERE keyword = 'Lymph node metastasis'
  ORDER BY datetime(requested_at) DESC
  LIMIT 1
)
SELECT r.*
FROM results r
JOIN latest l ON r.search_id = l.id
ORDER BY r.id DESC;
```

- Extractions for a given search id:
```sql
SELECT * FROM extractions
WHERE search_id = 123
ORDER BY datetime(created_at) DESC;
```

---

## Programmatic Access (Python)
```python
import sqlite3

conn = sqlite3.connect("documents/ontology_cache.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT * FROM searches ORDER BY datetime(requested_at) DESC LIMIT 10;")
print([dict(r) for r in cur.fetchall()])
```

