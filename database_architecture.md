# Database Architecture: Multi-State Draw Odds & Harvest Data

## The Core Question

**Can all states share a single schema, or do mechanics differ enough to require per-state schemas?**

**Answer: A single unified schema can work**, but it requires careful normalization and a few key design decisions to accommodate the wide variation in draw mechanics across states. Per-state schemas would cause massive code duplication and make cross-state comparisons (the app's primary value proposition) extremely difficult. The approach below uses a single schema with configuration/metadata tables that capture state-specific mechanics.

---

## Key Differences That Drive Schema Design

| Dimension | Variation Across States |
|-----------|------------------------|
| **Draw type** | Pure lottery (NM), preference points (WY, CA), bonus points (AZ, NV, MT), hybrid (CO, UT) |
| **Point math** | None (NM), linear (AZ: pts+1 entries), squared (NV: (pts+1)²), ordered queue (WY preference), hybrid split (CO: 80% pref / 20% weighted) |
| **Pools** | NM: 3 pools (res/NR/outfitter). Most states: 2 pools (res/NR). Some: single pool with quotas |
| **Tag types** | Draw-only, OTC unlimited, OTC quota (FCFS), landowner, leftover/surplus |
| **Weapon types** | Some states run separate draws per weapon (rifle/archery/muzz); others combine |
| **Choices** | 1-5 choices per application depending on state |
| **Turn-back** | Some allow tag return with point restoration, others don't |
| **NR allocation** | Fixed %, fixed count, or per-unit caps |
| **Price structure** | Varies by species, weapon, quality tier, residency, age |

---

## Recommended Approach: Single Schema with State Configuration

### Design Principles

1. **States table** as top-level dimension — every hunt, draw result, and harvest record ties to a state
2. **Point system metadata** captured in a `state_draw_config` table, not baked into draw results
3. **Pools are generic** — can be "RES", "NR", "OUTF", "LANDOWNER", etc. per state
4. **Tag types** distinguish draw vs OTC vs landowner vs leftover
5. **Draw results store raw numbers** (applications, tags available, tags awarded) — the app layer computes odds using point system rules from config
6. **Weapon type** is a column on hunts, not a separate table hierarchy
7. **Points data** (if states publish point distribution) gets its own table

---

## Draft CREATE TABLE Statements

```sql
PRAGMA foreign_keys = ON;

----------------------------------------------------------------
-- CORE LOOKUP / DIMENSION TABLES
----------------------------------------------------------------

-- States
CREATE TABLE states (
    state_id        INTEGER PRIMARY KEY,
    state_code      TEXT NOT NULL UNIQUE,    -- NM, AZ, CO, UT, NV, MT, ID, WY, OR, WA, CA
    state_name      TEXT NOT NULL,
    draw_type       TEXT NOT NULL,           -- 'lottery', 'preference', 'bonus', 'hybrid'
    point_system    TEXT,                    -- NULL for NM; 'bonus_linear', 'bonus_squared', 'preference_queue', 'hybrid_split', etc.
    point_math_desc TEXT,                    -- Human-readable: "Each bonus point = 1 additional entry" or "(points+1)² entries"
    choices_per_app INTEGER DEFAULT 1,       -- Number of hunt choices per application
    has_otc_tags    INTEGER DEFAULT 0,       -- 1 if state offers OTC tags for deer/elk
    has_landowner   INTEGER DEFAULT 0,       -- 1 if state has landowner tag program
    can_buy_points  INTEGER DEFAULT 0,       -- 1 if you can purchase a point without applying for a hunt
    tag_turnback    INTEGER DEFAULT 0,       -- 1 if tag turn-back is allowed
    nr_allocation   TEXT,                    -- '10%', '20%', 'per-unit caps', '6%+10% outfitter', etc.
    residency_req   TEXT,                    -- e.g. '6 months', '1 year', etc.
    notes           TEXT
);

-- Species (extending existing)
CREATE TABLE species (
    species_id      INTEGER PRIMARY KEY,
    species_code    TEXT NOT NULL UNIQUE,    -- ELK, DER, MDR (mule deer), WTD (whitetail), ANT, ORX, etc.
    common_name     TEXT NOT NULL,
    notes           TEXT
);

-- Bag limits (keep existing NM table, works for all states)
CREATE TABLE bag_limits (
    bag_limit_id        INTEGER PRIMARY KEY,
    bag_code            TEXT NOT NULL UNIQUE,
    label               TEXT NOT NULL,
    plain_definition    TEXT NOT NULL,
    notes               TEXT
);

-- Pools (generic, per-state)
CREATE TABLE pools (
    pool_id         INTEGER PRIMARY KEY,
    state_id        INTEGER NOT NULL,
    pool_code       TEXT NOT NULL,           -- 'RES', 'NR', 'OUTF', 'LANDOWNER', 'YOUTH', etc.
    description     TEXT NOT NULL,
    allocation_pct  REAL,                    -- NULL if not applicable; e.g. 84.0, 6.0, 10.0 for NM
    allocation_note TEXT,                    -- "Up to 10% of tags" or "Remaining after preference draw"
    FOREIGN KEY (state_id) REFERENCES states(state_id),
    UNIQUE (state_id, pool_code)
);

-- Weapon types
CREATE TABLE weapon_types (
    weapon_type_id  INTEGER PRIMARY KEY,
    weapon_code     TEXT NOT NULL UNIQUE,    -- 'RIFLE', 'ARCHERY', 'MUZZ', 'ANY', 'SHOTGUN'
    description     TEXT NOT NULL
);

-- Tag types (draw vs OTC vs landowner, etc.)
CREATE TABLE tag_types (
    tag_type_id     INTEGER PRIMARY KEY,
    tag_type_code   TEXT NOT NULL UNIQUE,    -- 'DRAW', 'OTC_UNLIMITED', 'OTC_QUOTA', 'LANDOWNER', 'LEFTOVER', 'SURPLUS'
    description     TEXT NOT NULL
);

----------------------------------------------------------------
-- GMU / UNIT TABLES
----------------------------------------------------------------

CREATE TABLE gmus (
    gmu_id          INTEGER PRIMARY KEY,
    state_id        INTEGER NOT NULL,
    gmu_code        TEXT NOT NULL,           -- '51', '201', 'Unit 44', etc. (state-specific codes)
    gmu_name        TEXT,
    FOREIGN KEY (state_id) REFERENCES states(state_id),
    UNIQUE (state_id, gmu_code)
);

----------------------------------------------------------------
-- HUNTS (CORE TABLE — ONE ROW PER UNIQUE HUNT OFFERING)
----------------------------------------------------------------

CREATE TABLE hunts (
    hunt_id             INTEGER PRIMARY KEY,
    state_id            INTEGER NOT NULL,
    hunt_code           TEXT NOT NULL,           -- State-specific hunt code: 'ELK-1-195', 'E-RF-001', etc.
    species_id          INTEGER NOT NULL,
    bag_limit_id        INTEGER,
    weapon_type_id      INTEGER,                 -- NULL if state doesn't differentiate by weapon
    tag_type_id         INTEGER NOT NULL DEFAULT 1,  -- DRAW by default
    unit_description    TEXT,                    -- Raw unit text from proclamation
    quality_tier        TEXT,                    -- 'standard', 'quality', 'high_demand', 'premium', 'limited_entry', NULL
    is_active           INTEGER NOT NULL DEFAULT 1,
    notes               TEXT,
    FOREIGN KEY (state_id)       REFERENCES states(state_id),
    FOREIGN KEY (species_id)     REFERENCES species(species_id),
    FOREIGN KEY (bag_limit_id)   REFERENCES bag_limits(bag_limit_id),
    FOREIGN KEY (weapon_type_id) REFERENCES weapon_types(weapon_type_id),
    FOREIGN KEY (tag_type_id)    REFERENCES tag_types(tag_type_id),
    UNIQUE (state_id, hunt_code)
);

-- Hunt-to-GMU mapping (many-to-many)
CREATE TABLE hunt_gmus (
    hunt_gmu_id     INTEGER PRIMARY KEY,
    hunt_id         INTEGER NOT NULL,
    gmu_id          INTEGER NOT NULL,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    FOREIGN KEY (gmu_id)  REFERENCES gmus(gmu_id),
    UNIQUE (hunt_id, gmu_id)
);

----------------------------------------------------------------
-- HUNT DATES / SEASONS (PER YEAR)
----------------------------------------------------------------

CREATE TABLE hunt_dates (
    hunt_date_id    INTEGER PRIMARY KEY,
    hunt_id         INTEGER NOT NULL,
    season_year     INTEGER NOT NULL,
    start_date      TEXT,                    -- ISO YYYY-MM-DD
    end_date        TEXT,
    hunt_name       TEXT,                    -- Cleaned English name
    notes           TEXT,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, season_year)
);

----------------------------------------------------------------
-- DRAW RESULTS (PER HUNT, PER YEAR, PER POOL)
-- Normalized: one row per pool instead of NM's pivoted columns
----------------------------------------------------------------

CREATE TABLE draw_results (
    draw_result_id      INTEGER PRIMARY KEY,
    hunt_id             INTEGER NOT NULL,
    draw_year           INTEGER NOT NULL,
    pool_id             INTEGER NOT NULL,
    applications        INTEGER,             -- Number of applicants in this pool
    tags_available      INTEGER,             -- Tags allocated to this pool
    tags_awarded        INTEGER,             -- Tags actually drawn/awarded
    first_choice_apps   INTEGER,             -- Applicants who listed this as 1st choice (if available)
    second_choice_apps  INTEGER,             -- 2nd choice apps (if available)
    third_choice_apps   INTEGER,             -- 3rd choice apps (if available)
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    FOREIGN KEY (pool_id) REFERENCES pools(pool_id),
    UNIQUE (hunt_id, draw_year, pool_id)
);

----------------------------------------------------------------
-- POINT DISTRIBUTION (FOR STATES THAT PUBLISH POINT DATA)
-- e.g. "For hunt X, 50 people with 5 points applied, 20 drew"
----------------------------------------------------------------

CREATE TABLE point_distribution (
    point_dist_id       INTEGER PRIMARY KEY,
    hunt_id             INTEGER NOT NULL,
    draw_year           INTEGER NOT NULL,
    pool_id             INTEGER NOT NULL,
    point_level         INTEGER NOT NULL,    -- 0, 1, 2, 3, ... N points
    applicants          INTEGER NOT NULL,    -- How many people at this point level applied
    successful          INTEGER,             -- How many at this point level drew a tag
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    FOREIGN KEY (pool_id) REFERENCES pools(pool_id),
    UNIQUE (hunt_id, draw_year, pool_id, point_level)
);

----------------------------------------------------------------
-- HARVEST STATS (PER HUNT, PER YEAR)
-- Extended from NM schema to handle more data fields
----------------------------------------------------------------

CREATE TABLE harvest_stats (
    harvest_id          INTEGER PRIMARY KEY,
    hunt_id             INTEGER NOT NULL,
    harvest_year        INTEGER NOT NULL,
    access_type         TEXT NOT NULL DEFAULT 'All',  -- 'Public', 'Private', 'All', etc.
    hunters_afield      INTEGER,             -- Total hunters who hunted
    total_harvest       INTEGER,             -- Animals harvested
    success_rate        REAL,                -- Percent (e.g., 37.5)
    satisfaction        REAL,                -- 1-5 scale (NM-specific, NULL for others)
    days_hunted         REAL,                -- Average days hunted
    licenses_sold       INTEGER,             -- Tags/licenses issued
    bulls_harvested     INTEGER,             -- Male harvest (elk)
    cows_harvested      INTEGER,             -- Female harvest (elk)
    bucks_harvested     INTEGER,             -- Male harvest (deer)
    does_harvested      INTEGER,             -- Female harvest (deer)
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, harvest_year, access_type)
);

----------------------------------------------------------------
-- PRICING (PER STATE, PER SPECIES, PER RESIDENCY)
----------------------------------------------------------------

CREATE TABLE license_prices (
    price_id            INTEGER PRIMARY KEY,
    state_id            INTEGER NOT NULL,
    species_id          INTEGER,             -- NULL for base hunting license
    residency           TEXT NOT NULL,        -- 'RES', 'NR'
    price_type          TEXT NOT NULL,        -- 'base_license', 'tag', 'application_fee', 'point_fee', 'stamp', 'otc_tag'
    description         TEXT NOT NULL,        -- 'Elk draw tag', 'Habitat stamp', 'Preference point purchase', etc.
    amount              REAL NOT NULL,        -- Dollar amount
    is_refundable       INTEGER DEFAULT 0,   -- 1 if refundable on unsuccessful draw
    effective_year      INTEGER NOT NULL,     -- Year these prices apply
    weapon_code         TEXT,                 -- NULL if same price for all weapons
    quality_tier        TEXT,                 -- 'standard', 'quality', 'high_demand', NULL
    notes               TEXT,
    FOREIGN KEY (state_id)  REFERENCES states(state_id),
    FOREIGN KEY (species_id) REFERENCES species(species_id)
);

----------------------------------------------------------------
-- APPLICATION DEADLINES (PER STATE, PER YEAR)
----------------------------------------------------------------

CREATE TABLE application_deadlines (
    deadline_id         INTEGER PRIMARY KEY,
    state_id            INTEGER NOT NULL,
    season_year         INTEGER NOT NULL,
    species_id          INTEGER,             -- NULL if same deadline for all species
    app_open_date       TEXT,                -- ISO date
    app_deadline        TEXT,                -- ISO date
    draw_results_date   TEXT,                -- ISO date
    leftover_sale_date  TEXT,                -- ISO date (if applicable)
    notes               TEXT,
    FOREIGN KEY (state_id)  REFERENCES states(state_id),
    FOREIGN KEY (species_id) REFERENCES species(species_id),
    UNIQUE (state_id, season_year, species_id)
);

----------------------------------------------------------------
-- OTC TAG AVAILABILITY (PER STATE)
----------------------------------------------------------------

CREATE TABLE otc_availability (
    otc_id              INTEGER PRIMARY KEY,
    state_id            INTEGER NOT NULL,
    species_id          INTEGER NOT NULL,
    season_year         INTEGER NOT NULL,
    weapon_type_id      INTEGER,
    available_to_res    INTEGER DEFAULT 1,   -- 1 if residents can buy
    available_to_nr     INTEGER DEFAULT 1,   -- 1 if nonresidents can buy
    is_unlimited        INTEGER DEFAULT 0,   -- 1 if unlimited, 0 if quota/FCFS
    quota               INTEGER,             -- NULL if unlimited
    unit_description    TEXT,                -- Which units/zones, or 'statewide'
    price_res           REAL,
    price_nr            REAL,
    notes               TEXT,
    FOREIGN KEY (state_id)   REFERENCES states(state_id),
    FOREIGN KEY (species_id) REFERENCES species(species_id),
    FOREIGN KEY (weapon_type_id) REFERENCES weapon_types(weapon_type_id)
);

----------------------------------------------------------------
-- LANDOWNER TAG PROGRAMS
----------------------------------------------------------------

CREATE TABLE landowner_programs (
    landowner_prog_id   INTEGER PRIMARY KEY,
    state_id            INTEGER NOT NULL,
    program_name        TEXT NOT NULL,        -- 'Ranching for Wildlife', 'LPP', 'CWMU', '454 Permits', etc.
    tags_tied_to_prop   INTEGER DEFAULT 0,   -- 1 if tags are property-specific
    transferable        INTEGER DEFAULT 0,   -- 1 if tags can be sold/transferred
    available_to_nr     INTEGER DEFAULT 0,   -- 1 if NR can receive/buy these tags
    description         TEXT,
    volume_note         TEXT,                 -- "~15% of total tags" or "varies by unit"
    price_note          TEXT,                 -- "Same as draw" or "$5,000-$12,000 market rate"
    FOREIGN KEY (state_id) REFERENCES states(state_id)
);

----------------------------------------------------------------
-- VIEWS
----------------------------------------------------------------

-- Cross-state hunt summary with draw odds
CREATE VIEW hunt_draw_summary AS
SELECT
    s.state_code,
    s.state_name,
    sp.species_code,
    sp.common_name AS species_name,
    h.hunt_code,
    h.unit_description,
    bl.bag_code,
    bl.label AS bag_label,
    wt.weapon_code,
    tt.tag_type_code,
    h.quality_tier,
    dr.draw_year,
    p.pool_code,
    dr.applications,
    dr.tags_available,
    dr.tags_awarded,
    CASE
        WHEN dr.applications > 0 AND dr.tags_available > 0
        THEN ROUND(CAST(dr.tags_available AS REAL) / dr.applications * 100, 1)
        ELSE NULL
    END AS draw_odds_pct
FROM hunts h
JOIN states s           ON s.state_id = h.state_id
JOIN species sp         ON sp.species_id = h.species_id
LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
LEFT JOIN tag_types tt  ON tt.tag_type_id = h.tag_type_id
LEFT JOIN draw_results dr ON dr.hunt_id = h.hunt_id
LEFT JOIN pools p       ON p.pool_id = dr.pool_id;

-- Cross-state harvest comparison
CREATE VIEW harvest_comparison AS
SELECT
    s.state_code,
    sp.species_code,
    sp.common_name AS species_name,
    h.hunt_code,
    h.unit_description,
    hs.harvest_year,
    hs.access_type,
    hs.hunters_afield,
    hs.total_harvest,
    hs.success_rate,
    hs.days_hunted,
    hs.licenses_sold
FROM harvest_stats hs
JOIN hunts h    ON h.hunt_id = hs.hunt_id
JOIN states s   ON s.state_id = h.state_id
JOIN species sp ON sp.species_id = h.species_id;
```

---

## Migration Strategy from Current NM Schema

The current NM tables map to the new schema as follows:

| Current NM Table | New Table | Migration Notes |
|------------------|-----------|-----------------|
| `species` | `species` | Add state-agnostic species codes; NM-specific species (ORX, IBX, BBY) remain |
| `bag_limits` | `bag_limits` | Keep as-is; other states will add their own entries |
| `gmus` | `gmus` | Add `state_id` column (all existing = NM) |
| `hunts` | `hunts` | Add `state_id`, `weapon_type_id`, `tag_type_id`, `quality_tier` columns |
| `hunt_gmus` | `hunt_gmus` | No change needed |
| `hunt_dates` | `hunt_dates` | No change needed |
| `draw_results` | `draw_results` | **Normalize**: pivot from res/NR/outf columns to one row per pool. Each NM draw result becomes 3 rows |
| `harvest_stats` | `harvest_stats` | Add new optional columns (`hunters_afield`, `total_harvest`, `bulls_harvested`, etc.) |
| `pools` | `pools` | Add `state_id`; NM keeps RES/NR/OUTF; other states get their own pool configs |
| — (new) | `states` | New dimension table |
| — (new) | `weapon_types` | New lookup |
| — (new) | `tag_types` | New lookup |
| — (new) | `point_distribution` | New table for states that publish point-level data |
| — (new) | `license_prices` | New table for fee tracking |
| — (new) | `application_deadlines` | New table |
| — (new) | `otc_availability` | New table |
| — (new) | `landowner_programs` | New table |

### Key Migration Steps

1. Create `states` table; insert NM as first row
2. Add `state_id` FK to `gmus`, `hunts`, `pools`
3. Backfill `state_id = 1` (NM) for all existing rows
4. Normalize `draw_results` from pivoted to per-pool format
5. Create new tables (`point_distribution`, `license_prices`, etc.)
6. Update Flask app queries to include `state_code` filter
7. Update views to be cross-state aware

---

## Why This Works for All State Variations

### NM (Pure Lottery, 3 Pools, No Points)
- `states.draw_type = 'lottery'`, `point_system = NULL`
- 3 pool rows: RES (84%), NR (6%), OUTF (10%)
- `point_distribution` table stays empty for NM
- Draw odds = simple `tags_available / applications`

### AZ (Bonus Points, Linear)
- `states.draw_type = 'bonus'`, `point_system = 'bonus_linear'`
- 2 pool rows: RES, NR
- `point_distribution` populated with per-point-level data
- App layer applies `(points + 1)` weighting for odds estimation

### CO (Hybrid: Preference + Weighted)
- `states.draw_type = 'hybrid'`, `point_system = 'hybrid_split'`
- `point_math_desc = '80% of tags to highest preference points (ordered queue), 20% weighted random with bonus points (pts+1 entries)'`
- `point_distribution` captures both preference tier and random tier data

### NV (Bonus Points, Squared)
- `states.draw_type = 'bonus'`, `point_system = 'bonus_squared'`
- `point_math_desc = '(bonus points + 1)² entries in random draw'`

### WY (True Preference for Most, Random for Some)
- `states.draw_type = 'preference'`, `point_system = 'preference_queue'`
- `point_math_desc = 'Tags awarded in order of highest preference points; ties broken randomly; 25% of NR tags random'`

### UT (Hybrid Bonus)
- `states.draw_type = 'hybrid'`, `point_system = 'hybrid_bonus'`
- `point_math_desc = '50% of permits to top bonus point holders, 50% random weighted (points+1 entries)'`

### States with OTC + Draw (MT, ID, OR, WA)
- OTC availability tracked in `otc_availability` table
- Draw hunts (limited entry / controlled) tracked normally in `hunts` + `draw_results`
- `tag_types` distinguishes DRAW vs OTC_UNLIMITED vs OTC_QUOTA

---

## Indexing Recommendations

```sql
-- Essential indexes for common queries
CREATE INDEX idx_hunts_state ON hunts(state_id);
CREATE INDEX idx_hunts_species ON hunts(species_id);
CREATE INDEX idx_hunts_state_species ON hunts(state_id, species_id);
CREATE INDEX idx_draw_results_hunt_year ON draw_results(hunt_id, draw_year);
CREATE INDEX idx_draw_results_year_pool ON draw_results(draw_year, pool_id);
CREATE INDEX idx_harvest_stats_hunt_year ON harvest_stats(hunt_id, harvest_year);
CREATE INDEX idx_gmus_state ON gmus(state_id);
CREATE INDEX idx_point_dist_hunt_year ON point_distribution(hunt_id, draw_year);
CREATE INDEX idx_prices_state_year ON license_prices(state_id, effective_year);
```

---

## Summary

A **single unified schema** is recommended. The key insight is that **draw mechanics are metadata about the state** (stored in `states` and `pools`), not structural differences requiring different table shapes. All states produce the same fundamental data: hunts have applicants, tags are allocated, some people draw, and hunters report harvest outcomes. The variation in *how* tags are allocated (lottery vs preference vs bonus) is captured in configuration columns and the `point_distribution` table, while the app layer uses these to compute state-appropriate odds estimates.
