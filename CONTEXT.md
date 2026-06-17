# KA Beat Planner — Domain Context

## Glossary

**Beat**
One field agent's store list for a single visit day. A beat is a geographic cluster of stores assigned to one agent for one day.

**Beat Size**
Number of stores per beat (i.e. per agent per day). Supervisor-adjustable at session start — not hardcoded.

**P1 Store**
A store within the supervisor-set distance threshold of a field agent's territory. Gets assigned to a field agent for a physical visit, regardless of its current `agent` column value (may have been a caller store before).

**P2 Store**
A store beyond the distance threshold of all field agent territories. Stays with a caller agent — no physical visit possible.

**Distance Threshold**
Not a fixed km value. P1/P2 is determined by the clustering itself: stores that fall naturally within a field agent's k-means cluster are P1; stores that are outliers (no field agent cluster is near) become P2. Driven by actual lead density and geography.

**Field Agent**
Agent with prefix `[SKAS/...]` or `[GKAS/...]`. Gets full beat planning: geographic clustering, map view, day assignment, CSV export.

**Caller Agent**
Agent with prefix `[Caller/KA]`. Excluded from beat planning. Receives only P2 stores (those no field agent can reach). No map, no day clustering.

## Clustering Approach

1. Identify field agents vs caller agents from the `agent` column naming convention.
2. Run geographic k-means clustering across **all stores** (not per existing agent assignment), constrained to beat size.
3. Assign each cluster to the nearest field agent.
4. Stores whose nearest cluster centroid exceeds the distance threshold → P2 → stay with callers.
5. Supervisor can adjust beat-to-agent and day assignments after clustering.

## GMV Priority & Visit Frequency

Goal: drive GMV and delivered store count. Beat planning enforces this via priority and frequency.

| Cohort | Priority | Suggested Visits/Week | Rule |
|---|---|---|---|
| Active But High GMV | 1 — Protect | 2–3x | Guaranteed slots; never bumped when beat is full |
| Active But Low GMV | 2 — Grow | 1–2x | Fill remaining capacity after High GMV |
| Inactive | 3 — Reactivate | 1x | Assigned last; dropped first if beat is over capacity |

When a beat exceeds the supervisor-set beat size, stores are trimmed in reverse priority order (Inactive first, then Low GMV).

## Input

- Excel (XLSX) upload each session
- All 3 cohorts included: `Active But High GMV Store`, `Active But Low GMV Store`, `Inactive Store`
- No store exclusions by cohort or status

## Output

- CSV export per agent per day (field agents only)
- Caller store list as separate CSV (P2 stores, no day breakdown)

## Key Columns (from XLSX)

| Column | Use |
|---|---|
| `store_id` | Unique store identifier |
| `store_name` | Display name |
| `agent` | Current assignment — used to detect agent type; overridable |
| `gcu` | Geographic cluster unit |
| `warehouse` | BC / SL / ST |
| `point_y` | Latitude |
| `point_x` | Longitude |
| `visit_day` | Current day assignment — starting point, supervisor can change |
| `cohort` | Active High GMV / Active Low GMV / Inactive |
| `Delivered TW / LW / MTD` | GMV metrics shown in UI |
