# Ralph Agent Instructions — KA Beat Planner

You are an autonomous coding agent building the KA Beat Planner — a Streamlit app for Key Account supervisors to plan daily store visit beats for field agents.

## Your Task

1. Read the PRD at `prd.json`
2. Read the progress log at `progress.txt` (check Codebase Patterns section first)
3. Check you're on the correct branch (`ralph/ka-beat-planner`). If not, create it from main: `git checkout -b ralph/ka-beat-planner`
4. Pick the **highest priority** user story where `passes: false`
5. Implement that single user story completely
6. Run quality check: `python -m py_compile app.py` and any new lib files
7. If checks pass, commit ALL changes: `feat: [Story ID] - [Story Title]`
8. Update `prd.json` to set `passes: true` for the completed story
9. Close the corresponding GitHub issue on `AndrewMarasigan31/ka-beat-planner` with a commit link:
   `gh issue close <N> --repo AndrewMarasigan31/ka-beat-planner --comment "Implemented in commit $(git rev-parse HEAD)"`
10. Append your progress to `progress.txt`
11. If ALL stories have `passes: true`, output `<promise>COMPLETE</promise>`

## Project Context

- **Stack:** Python, Streamlit, pandas, scikit-learn, folium, streamlit-folium, openpyxl
- **Main file:** `app.py`
- **Lib modules:** `lib/parser.py`, `lib/clustering.py`, `lib/composer.py`, `lib/exporter.py`
- **Data:** XLSX with 530 KA stores — uploaded by supervisor each session
- **Password:** `ka2026` (hardcoded for now)
- **Repo:** `AndrewMarasigan31/ka-beat-planner`

## Domain Model (from CONTEXT.md)

- **Beat** = one field agent's stores for one day
- **Field agents** = prefix `[SKAS/` or `[GKAS/` in the `agent` column
- **Caller agents** = prefix `[Caller/KA]` — no beat planning, receive P2 stores only
- **P1 store** = falls within a field agent k-means cluster → field visit
- **P2 store** = outlier (distance to nearest centroid > mean inter-centroid distance) → caller
- **GMV priority:** Active But High GMV Store (protect) > Active But Low GMV Store (grow) > Inactive Store (reactivate)
- **Visit frequency:** High GMV = 3 slots/week, Low GMV = 2 slots, Inactive = 1 slot
- **`point_y` = latitude, `point_x` = longitude** (note: reversed from conventional naming)

## Key Implementation Notes

- Use `st.session_state` to preserve parsed stores and beats across Streamlit reruns
- Use `st.number_input` for beat size (min=5, max=100, default=30) — re-clustering should not require re-upload
- Folium map via `streamlit_folium.st_folium` — always `use_container_width=True`
- CSV exports via `st.download_button(data=bytes, mime="text/csv")` — never write files to disk
- scikit-learn KMeans: `KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=42)`
- Agent colors for map: use a fixed palette — cycle through ["#E63946","#2A9D8F","#E9C46A","#F4A261","#264653","#6A4C93","#1982C4","#8AC926","#FF595E"]

## Progress Report Format

APPEND to `progress.txt` (never replace):
```
## [Date/Time] - [Story ID]
- What was implemented
- Files changed
- **Learnings:**
  - Patterns discovered
  - Gotchas
---
```

## Codebase Patterns

(Ralph will add reusable patterns here as discovered)

## Quality Requirements

- No syntax or import errors before committing
- Keep changes scoped to the single user story
- Do NOT commit broken code
