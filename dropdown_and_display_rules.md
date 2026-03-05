# Dropdown & Display Rules — GraysonsDrawOdds

Answers two questions:
1. How do hunt codes display to hunters?
2. How do unit dropdowns work without showing the wrong units?

---

## Rule 1: Hunt Codes Display Exactly As Published

The `hunt_code` column stores the native agency string, unchanged.  
The `hunt_code_display` column is an optional label shown alongside it.

| State | What hunter sees | hunt_code | hunt_code_display |
|-------|-----------------|-----------|-------------------|
| NM    | ELK-1-197       | ELK-1-197 | NULL              |
| AZ    | 1001 — Unit 1 Early Rifle Bull | 1001 | Unit 1 Early Rifle Bull |
| CO    | DE007R1         | DE007R1   | NULL (already readable) |
| ID    | 3241            | 3241      | NULL or loaded from IDFG |
| WY    | 7-BULL-T1-REG — Hunt Area 7, Bull Elk Type 1 Regular | 7-BULL-T1-REG | Hunt Area 7, Bull Elk Type 1 Regular |
| OR    | 217             | 217       | NULL or loaded from ODFW |
| CA    | X3A             | X3A       | NULL (zone code is well-known) |

**Never prepend a state code to hunt_code.** The state is always the first
filter in the UI. A hunter in the AZ screen only sees AZ codes. There is no
scenario where 'AZ-1001' is clearer than '1001' — it's confusing noise.

The SQL pattern the UI uses:
```sql
SELECT hunt_code,
       COALESCE(hunt_code_display, hunt_code) AS hunt_label
FROM   hunts
WHERE  state_id = ? AND species_id = ?
ORDER  BY hunt_code;
```

---

## Rule 2: Unit Dropdowns Are State-Scoped and Species-Aware

**The unit dropdown never appears until a state is selected.**  
This eliminates all cross-state collision. "55" in Colorado only returns  
Colorado GMUs. There is no case where CO-55 and NV-55 appear together.

### The Search Problem

`gmu_code` is always TEXT. Ordering and search use `gmu_sort_key` instead.

**Sort key construction rule** (applied at data load time, not query time):

```
Pure numeric codes:  left-pad to 5 digits
    "1"   → "00001"
    "55"  → "00055"
    "100" → "00100"

Alphanumeric codes: pad the leading number, keep the suffix
    "55A"  → "00055A"
    "55B"  → "00055B"
    "D3"   → "D00003"
    "1A"   → "00001A"
    "X"    → "X"

Named units (no leading number):
    "Valle Vidal" → "Valle Vidal"   (sort alphabetically at end)
```

This produces the dropdown ordering hunters expect:
`1, 2, 10, 55, 55A, 55B, 100, 101, D3, Valle Vidal`
instead of lexicographic: `1, 10, 100, 101, 2, 55, 55A, 55B, D3, Valle Vidal`

### The "I Typed 55" Problem

Use `LIKE 'search%'` (starts-with), not `LIKE '%search%'` (contains).

Correct query for unit search within a selected state:
```sql
SELECT gmu_id, gmu_code, dropdown_label
FROM   gmu_dropdown
WHERE  state_code     = :state          -- required first
  AND  (species_context IS NULL         -- not species-restricted
        OR species_context = :species)  -- or matches selected species
  AND  (gmu_code    LIKE :q || '%'      -- starts-with the typed string
        OR gmu_name LIKE '%' || :q || '%')  -- OR name contains it
ORDER  BY gmu_sort_key
LIMIT  50;
```

What this means for "55" typed in Colorado Elk:
- Returns: 55, 55A, 55B (all start with "55")
- Does NOT return: 155, 255, 550 (do not start with "55")
- DOES return a unit named "Fifty-Five Valley" if the name contains "55"

This is correct behavior. A hunter typing "55" wants the 55-series.  
If they want unit 155 specifically they type "155".

### The Idaho Species-Context Problem

Idaho deer are managed in numbered **Units**.  
Idaho elk are managed in numbered **Zones**.  
Unit 39 (deer) and Zone 39 (elk) are DIFFERENT geographic areas.

The `gmus` table handles this with `species_context`:

```sql
-- Two separate rows in gmus for Idaho:
(state_id=ID, gmu_code='39', species_context='MDR', gmu_name='Deer Unit 39', ...)
(state_id=ID, gmu_code='39', species_context='ELK', gmu_name='Elk Zone 39', ...)
```

The dropdown query filters on `species_context IS NULL OR species_context = :species`,
so a hunter who has selected Elk in Idaho only sees Elk Zones,  
and a hunter who has selected Deer only sees Deer Units.

The `unit_type_label` on the states table changes the dropdown header:
- Idaho + Elk selected → header reads "Elk Zone"
- Idaho + Deer selected → header reads "Deer Unit"

Implementation note: `unit_type_label` on the states row is a default  
for all species. For Idaho's split case, derive the label from  
`species_context` when it's set on the gmu row, overriding the state default.

### The AZ Two-Level Problem

Arizona has:
- **Units** (geographic, ~45 numbered areas) — what hunters think in terms of
- **Hunt numbers** (4-digit codes, ~400+) — what AZGFD uses in the draw

One AZ unit contains many hunt numbers:
- Unit 1: 1001 (early rifle bull), 1002 (late rifle bull), 1003 (archery bull),
  1004 (cow), 1005 (Coues deer rifle), 1006 (Coues deer archery), ...

**Dropdown flow for Arizona:**
1. State = AZ, Species = Elk
2. Unit dropdown shows: 1, 2, 3, 4A, 4B, 6A, 6B, ...  ← geographic units
3. Hunter picks Unit 1
4. Hunt number list appears below: 1001, 1002, 1003, 1004 ← filtered by gmu
5. Hunter picks hunt number 1001
6. Draw odds for 1001 are shown

This is implemented via the `hunt_gmus` link table:
```sql
-- After hunter selects AZ + Elk + Unit 1:
SELECT h.hunt_id, h.hunt_code,
       COALESCE(h.hunt_code_display, h.hunt_code) AS hunt_label,
       h.season_type, wt.label AS weapon_label, bl.label AS bag_label
FROM   hunts h
JOIN   hunt_gmus hg ON hg.hunt_id = h.hunt_id
JOIN   gmus     g   ON g.gmu_id   = hg.gmu_id
JOIN   weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
WHERE  h.state_id   = (SELECT state_id FROM states WHERE state_code='AZ')
  AND  h.species_id = (SELECT species_id FROM species WHERE species_code='ELK')
  AND  g.gmu_code   = '1'
ORDER  BY h.hunt_code;
```

For states where the hunt code IS the unit (e.g., NM 'ELK-1-197'),
the two-level dropdown collapses to one level — unit selection and hunt
selection are the same step.

---

## Rule 3: The Dropdown Label Header

The `unit_type_label` column on the states table controls what the  
dropdown says above the unit field. Frontend should render:

```
[ State: Colorado ▼ ]  [ Species: Elk ▼ ]  [ GMU: ________ ▼ ]
                                              ↑
                                    states.unit_type_label
```

Reference:
| State | unit_type_label |
|-------|----------------|
| NM    | Unit           |
| AZ    | Unit           |
| CO    | GMU            |
| UT    | Unit           |
| NV    | Hunt Unit      |
| MT    | Hunting District |
| ID    | Unit / Zone*   |
| WY    | Hunt Area      |
| OR    | Hunt Area      |
| WA    | GMU            |
| CA    | Zone           |

*ID: override with species-specific label when species_context is set on gmu row.

---

## Rule 4: Subspecies and Sex Are in Bag Limits, Not Separate Hunts

A Coues deer hunt in AZ is a hunt with `species_id=WTD` and  
`bag_limit_id → COUES`. It is NOT a separate species row.

A spike bull elk hunt in UT is `species_id=ELK` and `bag_limit_id → SPIKE`.  
A cow elk hunt is `species_id=ELK` and `bag_limit_id → COW`.  
A branch-antlered bull hunt is `species_id=ELK` and `bag_limit_id → BULL`.

This means the species dropdown always shows ELK or DEER (or MDR/WTD  
if the state distinguishes mule deer from whitetail in separate draws).  
The bag limit detail lives one level deeper in the results, not in the filter.

Roosevelt elk and Tule elk (CA) ARE separate species rows (`RELT`, `ROOSE-ELK`)
because they have completely separate tag pools and draw systems from Rocky  
Mountain elk in the same state.

---

## Summary Checklist for Frontend Developer

- [ ] State selector always appears first and is required
- [ ] Species selector appears after state (filters to species this state has draw data for)
- [ ] Unit dropdown only appears after state + species are selected
- [ ] Unit dropdown header text comes from `states.unit_type_label`
         (or `gmus.species_context`-derived label for Idaho)
- [ ] Unit search uses `gmu_code LIKE :q || '%' OR gmu_name LIKE '%' || :q || '%'`
- [ ] Units ordered by `gmu_sort_key`, not by `gmu_code`
- [ ] AZ shows a two-level picker: Unit → Hunt Number within unit
- [ ] Hunt codes display as `COALESCE(hunt_code_display, hunt_code)` — never modified
- [ ] NM hunt codes (e.g., 'ELK-1-197') display unchanged — no state prefix
- [ ] Draw odds table shows pool name (RES, NR, OUTF) from `pools.description`
- [ ] Bag limit (bull/cow/spike/antlerless) shown as secondary info, not a primary filter
