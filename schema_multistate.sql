-- =============================================================
-- GraysonsDrawOdds — Multi-State Schema
-- Extends the existing NM schema to cover all western states.
--
-- DESIGN RULES:
--   1. hunt_code is always the native agency string, exactly as
--      published. NM keeps "ELK-1-197". AZ keeps "1001". Never
--      prepend a state prefix — state_id is the namespace.
--   2. gmu_code is always TEXT. Never cast to INTEGER. Units like
--      "55A", "D3", "Valle Vidal" exist. The sort column handles
--      ordering, not the code itself.
--   3. State is always the first filter. The dropdown never mixes
--      units across states, so "55" typed in the unit box only
--      returns units for the already-selected state.
--   4. Subspecies, sex, and weapon restrictions live in bag_limits
--      and weapon_types, not in separate hunts. One hunt row per
--      distinct drawing opportunity.
--   5. draw_results_by_pool replaces the pivoted draw_results
--      columns. NM data migrates into this table too (see bottom).
--      The old draw_results table stays for backward compat during
--      migration — remove it when migration is confirmed complete.
-- =============================================================

PRAGMA foreign_keys = ON;

-- =============================================================
-- STATES
-- Top-level dimension. Every hunt, GMU, pool, and draw result
-- belongs to a state.
-- =============================================================

DROP TABLE IF EXISTS states;
CREATE TABLE states (
    state_id            INTEGER PRIMARY KEY,
    state_code          TEXT NOT NULL UNIQUE,   -- NM, AZ, CO, UT, NV, MT, ID, WY, OR, WA, CA
    state_name          TEXT NOT NULL,

    -- Draw mechanics (drives display logic and odds calculations)
    draw_type           TEXT NOT NULL,
    -- 'lottery'    — pure random, no points (NM, ID)
    -- 'preference' — ordered queue, highest pts draw first (CO, CA)
    -- 'bonus'      — weighted random, more pts = more entries (AZ, NV, WA)
    -- 'hybrid'     — combination (UT, MT, WY, OR)

    point_math          TEXT,
    -- NULL for lottery states
    -- 'linear'       — each point = 1 additional entry (AZ)
    -- 'squared'      — entries = (pts+1)^2 (NV, WA, MT bonus)
    -- 'queue_90_10'  — 90% to max-pt holders, 10% random (ID controlled — no pts, but split logic)
    -- 'queue_75_25'  — 75% preference queue, 25% random (WY, OR, MT NR combo)
    -- 'queue_50_50'  — 50% preference queue, 50% bonus (UT limited entry)
    -- 'queue_pure'   — 100% pure preference queue (CO current, CA)
    point_math_note     TEXT,   -- human-readable description of above for display

    choices_per_app     INTEGER DEFAULT 1,  -- how many hunt codes per application

    can_buy_points      INTEGER DEFAULT 0,  -- 1 if hunter can buy a point without applying
    tag_turnback        INTEGER DEFAULT 0,  -- 1 if drawing a tag and returning it restores points
    points_expire       INTEGER DEFAULT 0,  -- 1 if points expire after N years of non-application
    points_expire_years INTEGER,            -- NULL if no expiry; 2 for NV, 5 for CA

    -- Unit labeling — controls the dropdown header text
    unit_type_label     TEXT NOT NULL DEFAULT 'Unit',
    -- NM: 'Unit'
    -- CO: 'GMU'
    -- MT: 'Hunting District'
    -- WY: 'Hunt Area'
    -- OR: 'Hunt Area'    (restructured 2026; was 'Wildlife Management Unit')
    -- ID: see species_context column on gmus — deer='Unit', elk='Zone'
    -- CA: 'Zone'
    -- WA: 'GMU'
    -- AZ: 'Unit'         (geographic unit; hunt numbers are on the hunt row)
    -- NV: 'Hunt Unit'
    -- UT: 'Unit'

    -- Nonresident rules
    nr_allocation_note  TEXT,   -- plain-English: "10% per hunt code", "20-25% per hunt code", etc.
    nr_waiting_period   TEXT,   -- NULL if none; "5 years (LE deer/elk)" for UT

    -- Residency requirement to qualify as a state resident
    residency_req       TEXT,   -- "6 months continuous domicile", "1 year", etc.

    has_otc_tags        INTEGER DEFAULT 0,  -- 1 if OTC draw tags exist for deer or elk
    has_landowner       INTEGER DEFAULT 0,  -- 1 if state has a landowner tag program
    landowner_transferable INTEGER DEFAULT 0, -- 1 if landowner tags can be sold/given to NR hunters

    -- Application deadlines (informational; year-specific dates go in a separate table)
    app_deadline_month  TEXT,   -- 'February', 'April', etc.
    results_month       TEXT,   -- month draw results are typically announced

    notes               TEXT
);

INSERT INTO states (
    state_code, state_name, draw_type, point_math, point_math_note,
    choices_per_app, can_buy_points, tag_turnback, points_expire, points_expire_years,
    unit_type_label, nr_allocation_note, nr_waiting_period, residency_req,
    has_otc_tags, has_landowner, landowner_transferable,
    app_deadline_month, results_month, notes
) VALUES

('NM', 'New Mexico', 'lottery', NULL, 'Pure random draw. No points system. Three pools: resident, nonresident, outfitter.',
 1, 0, 0, 0, NULL,
 'Unit', '6% NR + 10% outfitter of total tags per hunt', NULL, 'Physical presence with intent to remain',
 0, 0, 0,
 'March', 'April', 'Existing app. Points system not applicable.'),

('AZ', 'Arizona', 'bonus', 'linear', 'Three-pass draw. Pass 1 (20%): max-point holders only. Pass 2 (60%): weighted random, each bonus point = 1 extra entry. Pass 3 (20%): random, 0-point applicants. Loyalty and Hunter Ed points available.',
 3, 1, 1, 0, NULL,
 'Unit', '10% NR per hunt number (5% in Pass 1 + 5% in Pass 3)', NULL, 'Domicile with intent; driver license or voter reg',
 1, 0, 0,
 'February', 'March–April', 'Hunt numbers (4-digit) encode unit+species+sex+weapon+season. Unit dropdown narrows to hunt numbers within it.'),

('CO', 'Colorado', 'preference', 'queue_pure', 'True preference queue: applicants ranked by points, highest draws first on 1st choice. 2nd–4th choices: draw even if lower points, but do not earn points. Switching to queue_50_50 in 2028.',
 4, 1, 1, 0, NULL,
 'GMU', '20–25% NR per hunt code', NULL, '12 months continuous domicile before license purchase',
 1, 1, 1,
 'April', 'May–June', 'CO switches to 50/50 hybrid system in 2028. Schema draw_type will update to hybrid then.'),

('UT', 'Utah', 'hybrid', 'queue_50_50', 'Limited-entry hunts: 50% to max-point holders (pure preference), 50% weighted random (pts²+1 entries). General-season hunts: pure preference queue (highest pts draw first).',
 3, 1, 1, 0, NULL,
 'Unit', '10% NR per individual hunt', '5 years between LE deer/elk tags (NR only)', '12 months continuous domicile',
 1, 1, 1,
 'April', 'May', NULL),

('NV', 'Nevada', 'bonus', 'squared', 'Weighted random. Entries = (bonus_points + 1)^2. No max-point reserve pass. Separate resident and NR applicant pools with NR quota. Points lost if applicant misses 2 consecutive years.',
 5, 1, 1, 1, 2,
 'Hunt Unit', '~10% NR (separate NR pool per hunt code)', '7 years between NR bull elk tags', '6 months domicile',
 0, 1, 1,
 'May', 'Late May', 'Very limited elk tags statewide (~150–300/yr). NR elk extremely difficult.'),

('MT', 'Montana', 'hybrid', 'queue_75_25', 'NR combo licenses: 75% to highest pref-point holders (max 3 pts), 25% random. Limited-entry permits: squared bonus points (pts²+1). Resident general licenses OTC — no draw. NR pref pts reset to 0 after drawing.',
 1, 1, 0, 0, NULL,
 'Hunting District', '~10% LE permits; NR combo cap ~17K elk+BG / ~12K deer statewide', NULL, '6 months domicile',
 1, 1, 0,
 'April 1', 'Mid-April', 'Residents buy OTC. Odds data is essentially NR-only. Pref points DO NOT restore on tag refund.'),

('ID', 'Idaho', 'lottery', NULL, 'Pure random draw. No preference or bonus points. Controlled hunts: 90% of tags random among all applicants, 10% random among nonresidents specifically (separate NR pool). General/OTC tags available for residents; NR general tags now drawn (2026+).',
 2, 0, 0, 0, NULL,
 'Unit',   -- note: elk uses 'Zone'; handled via species_context on gmus
 '10–15% NR per unit/zone (general season); variable per controlled hunt', NULL, '6 months domicile',
 1, 1, 0,
 'June 5 (controlled)', 'July (controlled)', 'Deer units and elk zones are different geographic entities. See species_context on gmus. NR general tags moved to draw starting 2026.'),

('WY', 'Wyoming', 'hybrid', 'queue_75_25', '75% of tags per hunt area go to highest-preference-point holders (ordered queue). 25% random. NR only: separate Regular (lower price, lower odds) vs Special (higher price, slightly better odds) license pools. Resident elk/deer often OTC or general license — no points for residents on deer/elk.',
 3, 1, 0, 0, NULL,
 'Hunt Area', '16% elk / 20% deer NR per hunt area', NULL, '1 year domicile + proof of domicile',
 1, 1, 0,
 'February (NR elk) / June (deer)', 'May (NR elk) / June (deer)', 'NR preference points for elk/deer only. Residents: general OTC for many units. Special vs Regular license is a WY-specific pool distinction.'),

('OR', 'Oregon', 'hybrid', 'queue_75_25', '75% to highest pref-point holders on 1st choice (queue). 25% random on 1st choice. Point earned if 1st choice unsuccessful (even if 2nd–5th choice drawn). Premium hunts (L/M/N series): pure random, no points. Eastern OR deer restructured to Hunt Areas 2026.',
 5, 1, 0, 0, NULL,
 'Hunt Area', '5% NR (deer and elk)', NULL, '6 months domicile',
 1, 1, 1,
 'May 15', 'June', 'Series-based hunt codes: 100=deer, 200=elk, 600=antlerless deer. Eastern OR deer moved from WMU codes to Hunt Area codes in 2026 — crosswalk needed for historical data.'),

('WA', 'Washington', 'bonus', 'squared', 'Weighted random. Entries = bonus_points^2. No max-point reserve pass. Residents and nonresidents compete in the same pool — no NR quota at all. Points tracked by species category (Quality Deer, Buck Deer, Elk), not by specific hunt.',
 2, 1, 1, 0, NULL,
 'GMU', 'No NR quota — R/NR compete equally in same pool', NULL, 'Domicile + WA driver license or voter reg',
 1, 1, 0,
 'Late May', 'Late June', 'WA is unique: no NR cap. NR application fee ($152.30) vs resident ($9.61) is high. Draw odds data locked in Power BI — may require direct WDFW contact for structured export.'),

('CA', 'California', 'preference', 'queue_pure', 'Deer: 90% preference queue (highest pts draw first), 10% random. Elk: 75% preference queue, 25% random (for hunts with 4+ tags; otherwise 100% preference). Points expire after 5-year gap in applications.',
 3, 1, 0, 1, 5,
 'Zone', 'Deer: no NR quota. Elk: 1 NR tag per year statewide (effectively zero access)', NULL, '1 year domicile',
 1, 1, 1,
 'June', 'Mid-June', 'CA elk is split: Tule elk, Roosevelt elk, Rocky Mountain elk — separate species pools. ~362 total elk tags statewide. Deer zones are letter-based (A–X, D3, D5, etc.). Blacktail deer in western zones — note in bag_limits.');

-- =============================================================
-- SPECIES
-- Extends existing NM table. Add subspecies that matter for
-- the multi-state scope. Subspecies distinction goes in notes
-- and bag_limits, not in a separate hunt row.
-- =============================================================

DROP TABLE IF EXISTS species;
CREATE TABLE species (
    species_id      INTEGER PRIMARY KEY,
    species_code    TEXT NOT NULL UNIQUE,
    common_name     TEXT NOT NULL,
    notes           TEXT
);

INSERT INTO species (species_code, common_name, notes) VALUES
    ('ELK',  'Elk',                'Rocky Mountain elk unless noted otherwise in hunt'),
    ('MDR',  'Mule Deer',          NULL),
    ('WTD',  'White-tailed Deer',  'Includes Coues deer (note in bag_limit); includes blacktail where applicable'),
    ('RELT', 'Tule Elk',           'California only — distinct subspecies managed separately'),
    ('RELT', 'Roosevelt Elk',      'WA, OR, CA coastal/NW — managed separately from Rocky Mountain elk'),
    ('ANT',  'Pronghorn',          NULL),
    ('ORX',  'Oryx',               'NM only'),
    ('IBX',  'Ibex',               'NM only'),
    ('BHS',  'Bighorn Sheep',      NULL),
    ('BBY',  'Barbary Sheep',      'NM only — Aoudad');

-- =============================================================
-- WEAPON TYPES
-- Factored out of hunt_code — each state encodes weapon type
-- differently in its codes, but we normalize it here.
-- =============================================================

DROP TABLE IF EXISTS weapon_types;
CREATE TABLE weapon_types (
    weapon_type_id  INTEGER PRIMARY KEY,
    weapon_code     TEXT NOT NULL UNIQUE,   -- RIFLE, ARCHERY, MUZZ, ANY, SHOTGUN, SRW
    label           TEXT NOT NULL,
    notes           TEXT
);

INSERT INTO weapon_types (weapon_code, label, notes) VALUES
    ('ANY',     'Any Legal Weapon',     'No restriction on weapon type'),
    ('RIFLE',   'Rifle',                'Modern firearm'),
    ('ARCHERY', 'Archery',              'Bow only; specific rules vary by state'),
    ('MUZZ',    'Muzzleloader',         'Primitive firearm; inline muzzleloaders allowed in some states'),
    ('SRW',     'Short-Range Weapon',   'ID-specific: shotgun, pistol, or muzz within defined range'),
    ('SHOTGUN', 'Shotgun',              'Slug or buckshot as defined by state');

-- =============================================================
-- BAG LIMITS
-- Extends existing NM table. Subspecies notes go here.
-- Add new entries for multi-state scope.
-- Existing NM bag limits are preserved below.
-- =============================================================

DROP TABLE IF EXISTS bag_limits;
CREATE TABLE bag_limits (
    bag_limit_id      INTEGER PRIMARY KEY,
    bag_code          TEXT NOT NULL UNIQUE,
    label             TEXT NOT NULL,
    plain_definition  TEXT NOT NULL,
    notes             TEXT
);

INSERT INTO bag_limits (bag_code, label, plain_definition, notes) VALUES
    -- Existing NM codes (preserved exactly)
    ('A',
     'Antlerless',
     'Any one elk or deer without antlers.',
     'For elk: antlerless = no antlers or antlers not visible. Excludes spike bulls.'),
    ('APRE/6',
     'Antler point restricted elk (6-point)',
     'Any bull elk with at least six visible points on one antler. Brow tine counts. Burr does not.',
     'Restriction applies to one antler only.'),
    ('APRE/6/A',
     'Antler point restricted or antlerless elk',
     'Either a legal APRE/6 bull elk or an antlerless elk.',
     'Allows harvest of qualifying mature bull or cow.'),
    ('BHO',
     'Broken-horned oryx',
     'Oryx of either sex with at least one horn missing at least 25% of normal length.',
     NULL),
    ('ES',
     'Either sex',
     'Any one animal of that species, male or female.',
     NULL),
    ('ESWTD',
     'Either sex white-tailed deer',
     'Any one white-tailed deer, buck or doe.',
     'White-tailed deer only.'),
    ('F-IM',
     'Female or immature',
     'Any female, or young male not meeting horn-length or maturity standard.',
     'Exact criteria vary by species and state.'),
    ('FAD',
     'Fork-antlered deer',
     'Deer where at least one antler has a clear fork with two or more distinct points.',
     NULL),
    ('FAMD',
     'Fork-antlered mule deer',
     'Mule deer where at least one antler has a clear fork with two or more distinct points.',
     NULL),
    ('FAWTD',
     'Fork-antlered white-tailed deer',
     'White-tailed deer where at least one antler has a clear fork with two or more distinct points.',
     NULL),
    ('MB',
     'Mature bull elk',
     'Male elk with brow tine ≥6 in. or at least one forked antler with both branches ≥6 in. Spike bulls excluded.',
     'NM legal maturity definition.'),
    ('MB/A',
     'Mature bull or antlerless elk',
     'Any MB-qualifying bull elk, or any antlerless elk.',
     'Considered bull-elk license for Valle Vidal once-in-a-lifetime rules.'),

    -- Multi-state additions
    ('BULL',
     'Any Bull Elk',
     'Any male elk with visible antlers, regardless of size or point count.',
     'Common in western states without antler restrictions.'),
    ('SPIKE',
     'Spike Bull Elk',
     'A male elk whose antlers consist only of a single unbranched beam on each side, with no forks.',
     'Used in UT general elk, some CO/ID units. Easier to draw than branch-antlered bull tags.'),
    ('COW',
     'Cow Elk (Antlerless)',
     'Any antlerless elk — functionally equivalent to A (antlerless) for elk hunts.',
     'Use A for NM hunts; COW for other states where agency uses this term explicitly.'),
    ('BUCK',
     'Any Buck Deer',
     'Any male deer with visible antlers, regardless of size or point count.',
     'Western states general buck deer tag.'),
    ('BUCK-FORK',
     'Fork-antlered buck or better',
     'Any buck deer where at least one antler has a fork — equivalent to FAMD for mule deer, FAWTD for whitetail.',
     'Consolidates state variants of the fork-antler restriction.'),
    ('DOE',
     'Doe / Antlerless Deer',
     'Any antlerless deer — doe or fawn.',
     NULL),
    ('COUES',
     'Coues White-tailed Deer (any sex or buck)',
     'Coues deer (Odocoileus virginianus couesi) — a desert whitetail subspecies found in AZ, NM, and parts of Mexico. Smaller than Rocky Mountain whitetail.',
     'Note subspecies in hunt description. Draw odds separate from standard WTD hunts in AZ.'),
    ('TULE-ELK',
     'Tule Elk',
     'Cervus canadensis nannodes — California endemic subspecies. Managed under California elk allocation separately from Rocky Mountain elk.',
     'CA only.'),
    ('ROOSE-ELK',
     'Roosevelt Elk',
     'Cervus canadensis roosevelti — larger subspecies found in coastal WA, OR, and northwest CA. Managed separately from Rocky Mountain elk.',
     'WA Olympic Peninsula and OR coast units. Some of the largest elk in North America.'),
    ('BKTL-DEER',
     'Blacktail Deer',
     'Odocoileus hemionus columbianus — a subspecies of mule deer found in coastal CA, OR, and WA. Often managed under the same draw as mule deer but worth noting.',
     'CA western zones (A, B, C), western OR and WA. Hunted differently from interior mule deer.');

-- =============================================================
-- GMUs
-- Unit_type_label lives on states. gmu_code is always TEXT.
-- gmu_sort_key enables natural ordering in dropdowns.
-- species_context handles the Idaho deer-unit vs elk-zone case.
-- =============================================================

DROP TABLE IF EXISTS gmus;
CREATE TABLE gmus (
    gmu_id          INTEGER PRIMARY KEY,
    state_id        INTEGER NOT NULL,
    gmu_code        TEXT NOT NULL,
    -- Always stored as TEXT. Examples: '51', '55A', 'D3', 'Valle Vidal',
    -- 'Unit 1A', '316', 'X'. Never cast to integer for comparison or sort.
    -- The code should match exactly what the state agency prints —
    -- what a hunter would type into the state's own draw portal.

    gmu_name        TEXT,
    -- Official name of the unit if the state publishes one.
    -- E.g. 'Gila', 'Valle Vidal', 'Bob Marshall Wilderness', 'Olympic Peninsula'.
    -- Searchable. Hunter can type "gila" and find the right unit.

    gmu_sort_key    TEXT NOT NULL,
    -- Zero-padded version of gmu_code for consistent ordering in dropdowns.
    -- Rule: left-pad pure-numeric codes to 5 digits; append letters as-is.
    -- Examples: '1' → '00001', '55' → '00055', '55A' → '00055A',
    --           '100' → '00100', 'D3' → 'D0003', 'X' → 'X'.
    -- Loaders compute this at ingest. Allows ORDER BY gmu_sort_key
    -- to produce 1, 2, 10, 55, 55A, 55B, 100 instead of 1, 10, 100, 2, 55.

    species_context TEXT DEFAULT NULL,
    -- NULL  = this unit applies to all species (most states)
    -- 'ELK' = Idaho elk zone (not a deer unit)
    -- 'MDR' = Idaho deer unit (not an elk zone)
    -- 'WTD' = whitetail-specific unit
    -- Prevents Idaho deer unit 39 and elk zone 39 from appearing
    -- together when hunter selects Elk as species.

    region          TEXT,
    -- Optional regional grouping for UI hierarchy.
    -- E.g. CO: 'Northwest', 'Northeast', 'Southwest', 'Southeast', 'Central'
    -- AZ: 'Region 1' through 'Region 6'
    -- Allows a two-level dropdown: Region → Unit within region.
    -- NULL = no regional grouping for this state.

    notes           TEXT,

    FOREIGN KEY (state_id) REFERENCES states(state_id),
    UNIQUE (state_id, gmu_code, COALESCE(species_context, ''))
    -- The COALESCE handles the Idaho case: (ID, '39', 'ELK') and
    -- (ID, '39', 'MDR') are two distinct rows.
);

-- Index for fast dropdown queries
CREATE INDEX IF NOT EXISTS idx_gmus_state_sort    ON gmus(state_id, gmu_sort_key);
CREATE INDEX IF NOT EXISTS idx_gmus_state_species ON gmus(state_id, species_context);
CREATE INDEX IF NOT EXISTS idx_gmus_name          ON gmus(gmu_name);

-- =============================================================
-- HUNTS
-- One row per distinct drawing opportunity per state.
-- hunt_code = the agency's native code, exactly as published.
-- hunt_code_display = optional friendly label for opaque codes.
-- =============================================================

DROP TABLE IF EXISTS hunts;
CREATE TABLE hunts (
    hunt_id             INTEGER PRIMARY KEY,
    state_id            INTEGER NOT NULL,
    species_id          INTEGER NOT NULL,
    hunt_code           TEXT NOT NULL,
    -- The native agency code, exactly as printed.
    -- NM: 'ELK-1-197'    (existing format, unchanged)
    -- AZ: '1001'         (four-digit hunt number)
    -- CO: 'DE007R1'      (CPW alphanumeric)
    -- ID: '3241'         (four-digit controlled hunt number)
    -- OR: '217'          (series-based)
    -- WY: '7-BULL-T1-REG' (area + license type, concatenated at load)
    -- CA: 'X3A'          (zone + weapon)
    -- Never modified or prefixed — state_id provides the namespace.

    hunt_code_display   TEXT,
    -- Optional human-readable label shown ALONGSIDE the code in the UI.
    -- NULL for most states where the code is already readable.
    -- Use for AZ where '1001' means nothing without context:
    --   hunt_code='1001', hunt_code_display='Unit 1 Early Rifle Bull'
    -- The UI shows: "1001 — Unit 1 Early Rifle Bull"
    -- For NM, this can be the existing hunt_name from hunt_dates, or NULL.

    weapon_type_id      INTEGER,            -- FK to weapon_types; NULL = any/unspecified
    bag_limit_id        INTEGER,            -- FK to bag_limits; bull/cow/spike/antlerless/either-sex
    season_type         TEXT,
    -- 'archery', 'rifle_1', 'rifle_2', 'rifle_3', 'rifle_4',
    -- 'muzzleloader', 'any_weapon', 'late', 'general', 'premium'
    -- States encode this in hunt codes; we normalize it here so
    -- hunters can filter by season type across states.

    tag_type            TEXT NOT NULL DEFAULT 'draw',
    -- 'draw'         — requires entering the annual drawing
    -- 'otc_unlimited' — over-the-counter, no quota (buy anytime)
    -- 'otc_quota'    — OTC but first-come-first-served until quota fills
    -- 'landowner'    — allocated to qualifying landowners
    -- 'leftover'     — surplus tags offered after main draw; often FCFS

    is_active           INTEGER NOT NULL DEFAULT 1,
    unit_description    TEXT,
    -- Raw "Unit" text from proclamation for edge cases not covered by hunt_gmus.
    -- E.g. 'Units 1, 2, and 3 (archery zone A)' when the hunt spans many units.

    notes               TEXT,

    FOREIGN KEY (state_id)        REFERENCES states(state_id),
    FOREIGN KEY (species_id)      REFERENCES species(species_id),
    FOREIGN KEY (weapon_type_id)  REFERENCES weapon_types(weapon_type_id),
    FOREIGN KEY (bag_limit_id)    REFERENCES bag_limits(bag_limit_id),
    UNIQUE (state_id, hunt_code)
    -- Uniqueness is per-state. NM 'ELK-1-197' and AZ '1001' coexist.
    -- NV resident and NR codes for the same physical hunt are stored
    -- as ONE hunt row; the pool table handles the R/NR split.
);

CREATE INDEX IF NOT EXISTS idx_hunts_state_species ON hunts(state_id, species_id);
CREATE INDEX IF NOT EXISTS idx_hunts_tag_type       ON hunts(tag_type);

-- =============================================================
-- HUNT × GMU LINK
-- Many-to-many: one hunt can span many GMUs (e.g. 'Units 1, 2, 3'),
-- and one GMU can host many hunts (multiple seasons in same unit).
-- =============================================================

DROP TABLE IF EXISTS hunt_gmus;
CREATE TABLE hunt_gmus (
    hunt_gmu_id     INTEGER PRIMARY KEY,
    hunt_id         INTEGER NOT NULL,
    gmu_id          INTEGER NOT NULL,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    FOREIGN KEY (gmu_id)  REFERENCES gmus(gmu_id),
    UNIQUE (hunt_id, gmu_id)
);

-- =============================================================
-- POOLS
-- Generic per-state. Replaces the hardcoded RES/NR/OUTF columns
-- from the original NM schema. States define their own pools.
-- NM has RES/NR/OUTF. WY has RES_REG/NR_REG/NR_SPEC. MT has
-- RES_GEN/NR_PREF/NR_RAND. Etc.
-- =============================================================

DROP TABLE IF EXISTS pools;
CREATE TABLE pools (
    pool_id         INTEGER PRIMARY KEY,
    state_id        INTEGER NOT NULL,
    pool_code       TEXT NOT NULL,
    -- NM:  'RES', 'NR', 'OUTF'
    -- AZ:  'RES', 'NR'          (10% NR of total)
    -- WY:  'RES', 'NR_REG', 'NR_SPEC'  (regular vs special license NR)
    -- MT:  'RES_OTC', 'NR_PREF', 'NR_RAND', 'LE_RES', 'LE_NR'
    -- WA:  'OPEN'               (R/NR compete equally — one pool)
    description     TEXT NOT NULL,
    allocation_pct  REAL,       -- NULL if dynamic/variable; e.g. 84.0 for NM resident
    allocation_note TEXT,       -- 'Up to 10% NR', '75% preference queue', etc.
    FOREIGN KEY (state_id) REFERENCES states(state_id),
    UNIQUE (state_id, pool_code)
);

-- Seed NM pools (matches existing app)
INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
SELECT state_id, 'RES',  'Resident pool',   84.0, '84% of tags'  FROM states WHERE state_code='NM'
UNION ALL
SELECT state_id, 'NR',   'Nonresident pool', 6.0, '6% of tags'   FROM states WHERE state_code='NM'
UNION ALL
SELECT state_id, 'OUTF', 'Outfitter pool',  10.0, '10% of tags'  FROM states WHERE state_code='NM';

-- =============================================================
-- DRAW RESULTS (NORMALIZED)
-- One row per hunt × year × pool. Replaces the pivoted columns
-- of the original draw_results table. All states use this table.
-- Odds = tags_awarded / applications (computed in views/app layer).
-- =============================================================

DROP TABLE IF EXISTS draw_results_by_pool;
CREATE TABLE draw_results_by_pool (
    result_id       INTEGER PRIMARY KEY,
    hunt_id         INTEGER NOT NULL,
    draw_year       INTEGER NOT NULL,
    pool_id         INTEGER NOT NULL,
    applications    INTEGER,    -- applicants who chose this hunt in this pool
    tags_available  INTEGER,    -- total tags allocated to this pool
    tags_awarded    INTEGER,    -- tags actually issued in this pool
    avg_pts_drawn   REAL,       -- average points held by successful applicants (if published)
    min_pts_drawn   INTEGER,    -- minimum points needed to draw (if published)
    max_pts_held    INTEGER,    -- maximum points held by any applicant in this pool (if published)
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    FOREIGN KEY (pool_id) REFERENCES pools(pool_id),
    UNIQUE (hunt_id, draw_year, pool_id)
);

CREATE INDEX IF NOT EXISTS idx_draw_results_hunt_year ON draw_results_by_pool(hunt_id, draw_year);
CREATE INDEX IF NOT EXISTS idx_draw_results_pool      ON draw_results_by_pool(pool_id, draw_year);

-- =============================================================
-- HARVEST STATS
-- Extends existing NM table with state_id.
-- access_type stays (Public / Private / Combined) since NM uses it.
-- =============================================================

DROP TABLE IF EXISTS harvest_stats;
CREATE TABLE harvest_stats (
    harvest_id      INTEGER PRIMARY KEY,
    hunt_id         INTEGER NOT NULL,
    harvest_year    INTEGER NOT NULL,
    access_type     TEXT NOT NULL DEFAULT 'Public',   -- 'Public', 'Private', 'Combined'
    success_rate    REAL,       -- percent; e.g. 37.5 means 37.5%
    satisfaction    REAL,       -- 1–5 scale (NM specific; NULL for other states)
    days_hunted     REAL,
    licenses_sold   REAL,
    harvest_count   INTEGER,    -- actual animals harvested (some states report this)
    notes           TEXT,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, harvest_year, access_type)
);

-- =============================================================
-- HUNT DATES / SEASONS (PER YEAR)
-- =============================================================

DROP TABLE IF EXISTS hunt_dates;
CREATE TABLE hunt_dates (
    hunt_date_id    INTEGER PRIMARY KEY,
    hunt_id         INTEGER NOT NULL,
    season_year     INTEGER NOT NULL,
    start_date      TEXT,       -- YYYY-MM-DD
    end_date        TEXT,       -- YYYY-MM-DD
    hunt_name       TEXT,       -- readable name: 'Unit 51 Elk First Rifle'
    notes           TEXT,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, season_year)
);

-- =============================================================
-- DRAW RESULTS (ORIGINAL NM TABLE — KEEP DURING MIGRATION)
-- After NM data is migrated to draw_results_by_pool, this table
-- can be dropped. The draw_results_long view below still works
-- off the new normalized table.
-- =============================================================

DROP TABLE IF EXISTS draw_results;
CREATE TABLE draw_results (
    draw_result_id              INTEGER PRIMARY KEY,
    hunt_id                     INTEGER NOT NULL,
    draw_year                   INTEGER NOT NULL,
    resident_applications       INTEGER,
    nonresident_applications    INTEGER,
    outfitter_applications      INTEGER,
    licenses_total              INTEGER,
    resident_licenses           INTEGER,
    nonresident_licenses        INTEGER,
    outfitter_licenses          INTEGER,
    resident_results            INTEGER,
    nonresident_results         INTEGER,
    outfitter_results           INTEGER,
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id),
    UNIQUE (hunt_id, draw_year)
);

-- =============================================================
-- APPLICATION DEADLINES (YEAR-SPECIFIC)
-- Stores exact dates when known; the states.app_deadline_month
-- is just the general month for display when exact date unknown.
-- =============================================================

DROP TABLE IF EXISTS app_deadlines;
CREATE TABLE app_deadlines (
    deadline_id     INTEGER PRIMARY KEY,
    state_id        INTEGER NOT NULL,
    species_id      INTEGER,            -- NULL = applies to all species for this state
    season_year     INTEGER NOT NULL,
    app_open_date   TEXT,               -- YYYY-MM-DD
    app_close_date  TEXT,               -- YYYY-MM-DD
    results_date    TEXT,               -- YYYY-MM-DD (when draw results published)
    notes           TEXT,
    FOREIGN KEY (state_id)   REFERENCES states(state_id),
    FOREIGN KEY (species_id) REFERENCES species(species_id)
);

-- =============================================================
-- VIEWS
-- =============================================================

-- Replaces draw_results_long. Works off normalized table.
-- Computes odds on the fly. App layer can further filter by pool.
DROP VIEW IF EXISTS draw_odds_view;
CREATE VIEW draw_odds_view AS
SELECT
    drp.result_id,
    s.state_code,
    s.state_name,
    h.hunt_id,
    h.hunt_code,
    COALESCE(h.hunt_code_display, h.hunt_code) AS hunt_label,
    sp.species_code,
    sp.common_name                             AS species_name,
    bl.bag_code,
    bl.label                                   AS bag_label,
    wt.weapon_code,
    wt.label                                   AS weapon_label,
    h.season_type,
    h.tag_type,
    drp.draw_year,
    p.pool_code,
    p.description                              AS pool_description,
    drp.applications,
    drp.tags_available,
    drp.tags_awarded,
    CASE
        WHEN drp.applications > 0
        THEN ROUND(CAST(drp.tags_awarded AS REAL) / drp.applications * 100, 2)
        ELSE NULL
    END                                        AS draw_odds_pct,
    drp.avg_pts_drawn,
    drp.min_pts_drawn,
    drp.max_pts_held
FROM draw_results_by_pool drp
JOIN hunts        h   ON h.hunt_id   = drp.hunt_id
JOIN states       s   ON s.state_id  = h.state_id
JOIN species      sp  ON sp.species_id = h.species_id
JOIN pools        p   ON p.pool_id   = drp.pool_id
LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id;

-- Unit dropdown query helper view.
-- Frontend queries: SELECT * FROM gmu_dropdown WHERE state_code='CO' AND (species_context IS NULL OR species_context='ELK') ORDER BY gmu_sort_key
DROP VIEW IF EXISTS gmu_dropdown;
CREATE VIEW gmu_dropdown AS
SELECT
    g.gmu_id,
    s.state_code,
    s.unit_type_label,
    g.gmu_code,
    g.gmu_name,
    g.gmu_sort_key,
    g.species_context,
    g.region,
    -- Display string for dropdown option:
    -- If unit has a name: "55A — Valle Vidal"
    -- If no name: "55A"
    CASE
        WHEN g.gmu_name IS NOT NULL
        THEN g.gmu_code || ' — ' || g.gmu_name
        ELSE g.gmu_code
    END AS dropdown_label
FROM gmus g
JOIN states s ON s.state_id = g.state_id;

-- Hunt summary with latest harvest and draw odds.
DROP VIEW IF EXISTS hunt_summary_view;
CREATE VIEW hunt_summary_view AS
WITH latest_harvest AS (
    SELECT hunt_id, MAX(harvest_year) AS latest_year
    FROM harvest_stats WHERE access_type = 'Public'
    GROUP BY hunt_id
),
latest_draw AS (
    SELECT hunt_id, MAX(draw_year) AS latest_year
    FROM draw_results_by_pool
    GROUP BY hunt_id
)
SELECT
    h.hunt_id,
    s.state_code,
    sp.species_code,
    sp.common_name                             AS species_name,
    h.hunt_code,
    COALESCE(h.hunt_code_display, h.hunt_code) AS hunt_label,
    bl.bag_code,
    bl.label                                   AS bag_label,
    wt.weapon_code,
    h.season_type,
    h.tag_type,
    h.unit_description,
    -- Latest draw odds (resident pool where available, else first pool)
    ld.latest_year                             AS latest_draw_year,
    -- Latest harvest
    lh.latest_year                             AS latest_harvest_year,
    hs.success_rate                            AS latest_success_rate,
    hs.satisfaction,
    hs.days_hunted,
    hs.licenses_sold
FROM hunts h
JOIN states       s   ON s.state_id    = h.state_id
JOIN species      sp  ON sp.species_id = h.species_id
LEFT JOIN bag_limits  bl ON bl.bag_limit_id    = h.bag_limit_id
LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
LEFT JOIN latest_draw  ld ON ld.hunt_id = h.hunt_id
LEFT JOIN latest_harvest lh ON lh.hunt_id = h.hunt_id
LEFT JOIN harvest_stats hs
    ON hs.hunt_id    = lh.hunt_id
   AND hs.harvest_year = lh.latest_year
   AND hs.access_type  = 'Public';

-- =============================================================
-- INDEXES
-- =============================================================

CREATE INDEX IF NOT EXISTS idx_hunts_state        ON hunts(state_id);
CREATE INDEX IF NOT EXISTS idx_hunt_gmus_hunt      ON hunt_gmus(hunt_id);
CREATE INDEX IF NOT EXISTS idx_hunt_gmus_gmu       ON hunt_gmus(gmu_id);
CREATE INDEX IF NOT EXISTS idx_harvest_hunt_year   ON harvest_stats(hunt_id, harvest_year);
CREATE INDEX IF NOT EXISTS idx_deadlines_state_yr  ON app_deadlines(state_id, season_year);
