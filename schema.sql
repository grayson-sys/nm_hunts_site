PRAGMA foreign_keys = ON;

----------------------------------------------------------------
-- CORE LOOKUP TABLES
----------------------------------------------------------------

DROP TABLE IF EXISTS species;
CREATE TABLE species (
    species_id     INTEGER PRIMARY KEY,
    species_code   TEXT NOT NULL UNIQUE,   -- ELK, DER, ANT, ORX, IBX, BHS, BBY
    common_name    TEXT NOT NULL,
    notes          TEXT
);

-- Seed species (you can edit or extend later)
INSERT INTO species (species_code, common_name) VALUES
    ('ELK', 'Elk'),
    ('DER', 'Deer'),
    ('ANT', 'Pronghorn'),
    ('ORX', 'Oryx'),
    ('IBX', 'Ibex'),
    ('BHS', 'Bighorn sheep'),
    ('BBY', 'Barbary sheep');

----------------------------------------------------------------
-- BAG LIMIT TABLE
----------------------------------------------------------------

DROP TABLE IF EXISTS bag_limits;
CREATE TABLE bag_limits (
    bag_limit_id      INTEGER PRIMARY KEY,
    bag_code          TEXT NOT NULL UNIQUE,  -- A, ES, MB, MB/A, etc.
    label             TEXT NOT NULL,
    plain_definition  TEXT NOT NULL,
    notes             TEXT
);

-- Canonical bag limit values
INSERT INTO bag_limits (bag_code, label, plain_definition, notes) VALUES
    ('A',
     'Antlerless',
     'Any one elk or deer without antlers. For elk this is defined as an antlerless elk.',
     'Antlers absent or not visible; excludes spike bulls.'
    ),
    ('APRE/6',
     'Antler point restricted elk (6-point)',
     'Any bull elk that has at least six visible points on one antler. A brow tine or eye guard counts as a point. The burr does not count.',
     'Restriction applies to one antler only; the other antler may have fewer points.'
    ),
    ('APRE/6/A',
     'Antler point restricted or antlerless elk',
     'Either a legal APRE/6 bull elk or an antlerless elk.',
     'Functionally allows harvest of a qualifying mature bull or a cow.'
    ),
    ('BHO',
     'Broken-horned oryx',
     'An oryx of either sex with at least one horn missing at least 25 percent of its normal length.',
     'Percent judged by comparing to the other horn or expected taper; horn must clearly be truncated before the final quarter of length.'
    ),
    ('ES',
     'Either sex',
     'Any one animal of that species, male or female.',
     'Meaning depends on species and hunt rule context.'
    ),
    ('ESWTD',
     'Either sex white-tailed deer',
     'Any one white-tailed deer, buck or doe.',
     'White-tailed deer only.'
    ),
    ('F-IM',
     'Female or immature',
     'Any female of that species, or a young male that does not meet the species-specific horn-length or maturity standard.',
     'Exact criteria vary by species and are defined in rule.'
    ),
    ('FAD',
     'Fork-antlered deer',
     'A deer where at least one antler has a clear fork with two or more distinct points. The burr does not count as a point.',
     'Species agnostic wording.'
    ),
    ('FAMD',
     'Fork-antlered mule deer',
     'A mule deer where at least one antler has a clear fork with two or more distinct points. The burr does not count.',
     'Mule deer only.'
    ),
    ('FAWTD',
     'Fork-antlered white-tailed deer',
     'A white-tailed deer where at least one antler has a clear fork with two or more distinct points. The burr does not count.',
     'White-tailed deer only.'
    ),
    ('MB',
     'Mature bull elk',
     'A male elk with either (1) at least one brow tine six inches or longer, or (2) at least one forked antler where both branches are six inches or longer. Spike bulls do not qualify.',
     'Legal maturity threshold tied to antler structure or tine length.'
    ),
    ('MB/A',
     'Mature bull or antlerless elk',
     'Any mature bull elk that meets the MB definition, or any antlerless elk.',
     'Considered a bull-elk license for once-in-a-lifetime classification in Valle Vidal rules.'
    );

----------------------------------------------------------------
-- GMU TABLES (FUTURE EXPANSION)
----------------------------------------------------------------

DROP TABLE IF EXISTS gmus;
CREATE TABLE gmus (
    gmu_id    INTEGER PRIMARY KEY,
    gmu_code  TEXT NOT NULL UNIQUE,   -- 51, 52, 34, etc.
    gmu_name  TEXT
);

DROP TABLE IF EXISTS hunt_gmus;
CREATE TABLE hunt_gmus (
    hunt_gmu_id  INTEGER PRIMARY KEY,
    hunt_id      INTEGER NOT NULL,
    gmu_id       INTEGER NOT NULL,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    FOREIGN KEY (gmu_id)  REFERENCES gmus(gmu_id),
    UNIQUE (hunt_id, gmu_id)
);

----------------------------------------------------------------
-- HUNTS (STATIC ACROSS YEARS)
----------------------------------------------------------------

DROP TABLE IF EXISTS hunts;
CREATE TABLE hunts (
    hunt_id          INTEGER PRIMARY KEY,
    hunt_code        TEXT NOT NULL UNIQUE,  -- ELK-1-195 etc.
    species_id       INTEGER NOT NULL,
    bag_limit_id     INTEGER,               -- optional, from bag_limits
    unit_description TEXT,                  -- raw "Unit" text from proclamation / report
    is_active        INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (species_id)   REFERENCES species(species_id),
    FOREIGN KEY (bag_limit_id) REFERENCES bag_limits(bag_limit_id)
);

----------------------------------------------------------------
-- HUNT DATES / SEASONS (PER YEAR)
----------------------------------------------------------------

DROP TABLE IF EXISTS hunt_dates;
CREATE TABLE hunt_dates (
    hunt_date_id  INTEGER PRIMARY KEY,
    hunt_id       INTEGER NOT NULL,
    season_year   INTEGER NOT NULL,      -- 2024, 2025, 2026
    start_date    TEXT,                  -- ISO date string YYYY-MM-DD
    end_date      TEXT,                  -- ISO date string YYYY-MM-DD
    hunt_name     TEXT,                  -- cleaned English name: "Unit 51 elk, first rifle"
    notes         TEXT,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, season_year)
);

----------------------------------------------------------------
-- DRAW RESULTS (AGGREGATED PER HUNT, PER YEAR)
-- Backed by draw_results_2025_clean.csv
----------------------------------------------------------------

DROP TABLE IF EXISTS draw_results;
CREATE TABLE draw_results (
    draw_result_id          INTEGER PRIMARY KEY,
    hunt_id                 INTEGER NOT NULL,
    draw_year               INTEGER NOT NULL,   -- 2025 for now
    resident_applications   INTEGER,
    nonresident_applications INTEGER,
    outfitter_applications  INTEGER,
    licenses_total          INTEGER,
    resident_licenses       INTEGER,
    nonresident_licenses    INTEGER,
    outfitter_licenses      INTEGER,
    resident_results        INTEGER,
    nonresident_results     INTEGER,
    outfitter_results       INTEGER,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, draw_year)
);

----------------------------------------------------------------
-- HARVEST STATS (PER HUNT, PER YEAR, PER ACCESS TYPE)
-- Backed by harvest_reports_public_with_licenses_2016_2024_cleaned.csv
----------------------------------------------------------------

DROP TABLE IF EXISTS harvest_stats;
CREATE TABLE harvest_stats (
    harvest_id     INTEGER PRIMARY KEY,
    hunt_id        INTEGER NOT NULL,
    harvest_year   INTEGER NOT NULL,
    access_type    TEXT NOT NULL DEFAULT 'Public',   -- 'Public' for all your current rows
    success_rate   REAL,                             -- percent as numeric, e.g. 37.5
    satisfaction   REAL,                             -- 1–5 scale
    days_hunted    REAL,
    licenses_sold  REAL,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, harvest_year, access_type)
);

----------------------------------------------------------------
-- OPTIONAL: POOLS LOOKUP (FOR FRONT END / ODDS LANGUAGE)
----------------------------------------------------------------

DROP TABLE IF EXISTS pools;
CREATE TABLE pools (
    pool_id     INTEGER PRIMARY KEY,
    pool_code   TEXT NOT NULL UNIQUE,   -- 'RES', 'NR', 'OUTF'
    description TEXT NOT NULL
);

INSERT INTO pools (pool_code, description) VALUES
    ('RES',  'Resident pool'),
    ('NR',   'Nonresident pool'),
    ('OUTF', 'Outfitter pool');

----------------------------------------------------------------
-- VIEWS FOR COMMON FRONT END QUERIES
----------------------------------------------------------------

-- Join hunts with species and GMUs
DROP VIEW IF EXISTS hunt_gmu_view;
CREATE VIEW hunt_gmu_view AS
SELECT
    h.hunt_id,
    h.hunt_code,
    s.species_code,
    s.common_name AS species_name,
    h.unit_description,
    bl.bag_code,
    bl.label AS bag_label,
    GROUP_CONCAT(g.gmu_code, ',') AS gmus
FROM hunts h
JOIN species s      ON s.species_id = h.species_id
LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
LEFT JOIN hunt_gmus hg  ON hg.hunt_id = h.hunt_id
LEFT JOIN gmus g        ON g.gmu_id = hg.gmu_id
GROUP BY
    h.hunt_id,
    h.hunt_code,
    s.species_code,
    s.common_name,
    h.unit_description,
    bl.bag_code,
    bl.label;

-- Unpivot draw_results into one row per pool
DROP VIEW IF EXISTS draw_results_long;
CREATE VIEW draw_results_long AS
SELECT
    dr.draw_result_id,
    dr.hunt_id,
    h.hunt_code,
    dr.draw_year,
    'RES' AS pool_code,
    dr.resident_applications   AS applications,
    dr.resident_licenses       AS licenses_available,
    dr.resident_results        AS tags_awarded
FROM draw_results dr
JOIN hunts h ON h.hunt_id = dr.hunt_id

UNION ALL

SELECT
    dr.draw_result_id,
    dr.hunt_id,
    h.hunt_code,
    dr.draw_year,
    'NR' AS pool_code,
    dr.nonresident_applications   AS applications,
    dr.nonresident_licenses       AS licenses_available,
    dr.nonresident_results        AS tags_awarded
FROM draw_results dr
JOIN hunts h ON h.hunt_id = dr.hunt_id

UNION ALL

SELECT
    dr.draw_result_id,
    dr.hunt_id,
    h.hunt_code,
    dr.draw_year,
    'OUTF' AS pool_code,
    dr.outfitter_applications   AS applications,
    dr.outfitter_licenses       AS licenses_available,
    dr.outfitter_results        AS tags_awarded
FROM draw_results dr
JOIN hunts h ON h.hunt_id = dr.hunt_id;

-- Harvest view, public only, joined to hunts and species
DROP VIEW IF EXISTS harvest_public_view;
CREATE VIEW harvest_public_view AS
SELECT
    hs.harvest_id,
    hs.harvest_year,
    h.hunt_id,
    h.hunt_code,
    s.species_code,
    s.common_name AS species_name,
    hs.success_rate        AS public_success_rate,
    hs.satisfaction,
    hs.days_hunted,
    hs.licenses_sold
FROM harvest_stats hs
JOIN hunts h   ON h.hunt_id = hs.hunt_id
JOIN species s ON s.species_id = h.species_id
WHERE hs.access_type = 'Public';

-- Convenience view that joins hunts, latest public harvest, and draw results
DROP VIEW IF EXISTS hunt_summary_view;
CREATE VIEW hunt_summary_view AS
WITH latest_harvest AS (
    SELECT
        hunt_id,
        MAX(harvest_year) AS latest_year
    FROM harvest_stats
    WHERE access_type = 'Public'
    GROUP BY hunt_id
)
SELECT
    h.hunt_id,
    h.hunt_code,
    s.species_code,
    s.common_name AS species_name,
    h.unit_description,
    bl.bag_code,
    bl.label AS bag_label,
    dr.draw_year,
    dr.resident_applications,
    dr.nonresident_applications,
    dr.outfitter_applications,
    dr.licenses_total,
    hs.harvest_year        AS latest_harvest_year,
    hs.success_rate        AS latest_public_success_rate,
    hs.satisfaction        AS latest_satisfaction,
    hs.days_hunted         AS latest_days_hunted,
    hs.licenses_sold       AS latest_licenses_sold
FROM hunts h
JOIN species s ON s.species_id = h.species_id
LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
LEFT JOIN draw_results dr ON dr.hunt_id = h.hunt_id
LEFT JOIN latest_harvest lh ON lh.hunt_id = h.hunt_id
LEFT JOIN harvest_stats hs
    ON hs.hunt_id = lh.hunt_id
   AND hs.harvest_year = lh.latest_year
   AND hs.access_type = 'Public';
