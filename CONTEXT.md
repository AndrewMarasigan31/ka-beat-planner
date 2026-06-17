# KA Beat Planner — Domain Context

## Glossary

**Beat**
One field agent's store list for a single visit day. A beat is a geographic cluster of stores assigned to one agent for one day.

**Beat Size**
Number of stores per beat (i.e. per agent per day). Supervisor-adjustable at session start — re-clustering does not require re-upload.

**P1 Store**
A store assigned to a field agent beat after clustering. Gets a physical visit.

**P2 / Caller Store**
A store routed to callers instead of field agents. Two ways a store becomes P2:
1. **Lasso exclusion** — supervisor draws a polygon on the map to exclude stores from beats. Excluded stores appear in the Caller list tagged as "Excluded".
2. **Day Assignment override** — supervisor sets a beat's day to "→ Caller", routing that entire beat to callers.

There is no algorithmic P2 detection. The supervisor drives all P1/P2 decisions.

**Field Agent**
Agent with prefix `[SKAS/...]` or `[GKAS/...]`. Gets full beat planning: geographic clustering, map view, day assignment, CSV export.

**Caller Agent**
Agent with prefix `[Caller/KA]`. Excluded from beat planning. Receives P2 stores (lasso-excluded or caller-assigned beats). Shown in the Caller CSV export.

## Clustering Approach

1. Identify field agents vs caller agents from the `agent` column naming convention.
2. Run geographic k-means clustering across **all stores** (not per existing agent assignment), constrained to beat size.
3. Merge small clusters (< 50% of beat size) into nearest neighbor.
4. Re-split any cluster exceeding beat size iteratively until all clusters are within the cap.
5. Assign each cluster to the nearest field agent by centroid proximity.
6. Supervisor adjusts beat-to-agent and day assignments after clustering.

## GMV Priority & Visit Frequency

Goal: drive GMV and delivered store count. Beat planning enforces this via priority and frequency.

| Cohort | Priority | Suggested Visits/Week | Rule |
|---|---|---|---|
| Active But High GMV | 1 — Protect | 2–3x | Guaranteed slots; never bumped when beat is full |
| Active But Low GMV | 2 — Grow | 1–2x | Fill remaining capacity after High GMV |
| Inactive | 3 — Reactivate | 1x | Assigned last; dropped first if beat is over capacity |

When a beat exceeds the supervisor-set beat size, stores are trimmed in reverse priority order (Inactive first, then Low GMV). High GMV stores are never trimmed.

## Input

- Excel (XLSX) upload each session
- All 3 cohorts included: `Active But High GMV Store`, `Active But Low GMV Store`, `Inactive Store`
- No store exclusions by cohort or status at upload time

## Output

- **Field CSV** — one row per store, per agent per day (skips unassigned and caller-assigned beats)
- **Caller CSV** — flat list of P2 stores (lasso-excluded + caller-assigned beats), round-robin distributed across caller agents

## Key Columns (from XLSX)

| Column | Use |
|---|---|
| `store_id` | Unique store identifier |
| `store_name` | Display name |
| `agent` | Current assignment — used to detect agent type; overridable in Day Assignment |
| `gcu` | Geographic cluster unit |
| `warehouse` | BC / SL / ST |
| `point_y` | Latitude (note: reversed from conventional naming) |
| `point_x` | Longitude (note: reversed from conventional naming) |
| `visit_day` | Current day assignment — starting point, supervisor can change |
| `cohort` | Active High GMV / Active Low GMV / Inactive |
| `MTD Delivered` | Month-to-date delivered order count |
| `Last Delivered Order Date` | Date of last fulfilled order (Excel serial → YYYY-MM-DD) |
| `Last Placed Order Date` | Date of last placed order (Excel serial → YYYY-MM-DD) |
| `Pending GMV MTD` | Pending GMV for the current month |
| `has_pending` | Derived flag: `Pending GMV MTD > 0` |
