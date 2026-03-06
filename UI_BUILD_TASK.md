# UI Build Task — GraysonsDrawOdds

Build a beautiful, clean, NYT-data-page-quality frontend for the multi-state
draw odds tool. Do NOT stop to ask questions. Make best judgment on all design
decisions and keep going.

## Output
Replace/rewrite: /Users/openclaw/Documents/GraysonsDrawOdds/app/static/index.html
All CSS and JS must be inline in this single file (no external files needed).

---

## Design Specification: NYT Data Page Aesthetic

### Typography
- Font stack: 'Helvetica Neue', Helvetica, Arial, sans-serif
- Body text: 16px, line-height 1.6, color #1a1a1a
- Headlines: font-weight 700, tight letter-spacing
- Data labels: 11px uppercase, letter-spacing 0.08em, color #666
- Numbers/odds: tabular figures, monospace where appropriate (use font-variant-numeric: tabular-nums)
- No decorative fonts. No rounded corners on typography.

### Color palette
- Background: #ffffff
- Surface/card: #f7f7f5 (NYT warm off-white)
- Border: #e2e2e2
- Text primary: #1a1a1a
- Text secondary: #666666
- Text muted: #999999
- Accent/interactive: #000000 (black — NYT style)
- Odds green (good): #00732f
- Odds yellow (medium): #b7791f
- Odds red (hard): #c0392b
- Link: #326891 (NYT blue)
- Divider: #e2e2e2 1px solid

### Layout
- Max content width: 1200px, centered, padding 0 24px
- Section dividers: thin 1px #e2e2e2 lines, generous whitespace
- No drop shadows. No gradients. No border-radius > 4px.
- Tables: no zebra stripes — use row hover (#f7f7f5) instead
- Mobile responsive: stack columns below 768px

---

## Page Structure

### 1. Masthead / Header
- Left: "GRAYSON'S DRAW ODDS" in bold 13px uppercase tracking
- Right: tagline "Western big game draw data for serious hunters"
- Below: thin rule, then a 1-line description:
  "Draw odds, harvest success rates, and application strategy for elk and deer
   across 11 western states."
- No hero images. No banner. Clean and editorial.

### 2. State Selector Bar
Horizontal pill/tab row of all 11 states:
NM | AZ | CO | UT | NV | MT | ID | WY | OR | WA | CA
- Active state: black background, white text
- Inactive: white background, black border, black text
- On mobile: horizontal scroll or 2-row grid
- Selecting a state loads that state's content below and updates the URL hash (#NM, #AZ, etc.)

### 3. State Info Panel (loads when state selected)
Two-column layout (sidebar + main) on desktop, stacked on mobile.

LEFT SIDEBAR (280px, sticky):
  - State name as H1 (e.g., "Montana")
  - Draw type badge: e.g., "HYBRID SYSTEM" in small caps
  - Key facts as a clean definition list:
      Points system: Bonus (squared)
      NR allocation: ~10% LE; combo cap
      NR waiting period: None (deer/elk)
      Application deadline: April 1
      Results announced: Mid-April
      OTC available: General season (residents)
      Landowner tags: Yes (not transferable)
  - [Link to official draw portal] — opens in new tab

RIGHT MAIN AREA:
  - "Draw System" section (see §4)
  - "Strategy Guide" section (see §5)
  - "Odds Explorer" section (see §6)

### 4. Draw System Explanation (per state)
Clear, editorial prose explaining how that state's system works.
Use H3 subheads, short paragraphs. No bullet soup — write in sentences.
Include a simple visual schematic of the draw flow where helpful
(pure CSS/HTML, no images — e.g., a flowchart using divs and borders).

Write full explanations for all 11 states:

**NM — New Mexico**
Pure random lottery. No points accumulate. Three separate pools: resident (84%),
nonresident (6%), outfitter/guide (10%). One application per year per species —
list up to 3 hunt codes in order of preference. The computer rolls one random
number per applicant; that number is checked against each choice in order until
a tag is awarded or all three choices fail. Strategy is simple: put your dream
hunt first and a high-odds hunt last to protect your chance of going hunting.
Points are irrelevant here — a first-time applicant has identical odds to a
30-year veteran.

**AZ — Arizona**
Three-pass bonus point system. Pass 1 (20% of tags): open only to applicants
with the maximum bonus points for that hunt. Pass 2 (60% of tags): weighted
random draw — each bonus point earns one additional entry, so an applicant
with 5 points gets 6 chances vs. 1 chance for a zero-point hunter. Pass 3
(20% of tags): pure random, open to all remaining applicants. Loyalty points
(consecutive years applying) and Hunter Education completion add fractional
bonus points. Nonresidents are capped at 10% of tags per hunt number. Arizona
is the most difficult draw in the West for premium bull elk — expect 15-20+
years of points for the best rifle units. Deer tags are more accessible.
The PointGuard program lets you turn back a tag and keep your points for a
$10-25 fee.

**CO — Colorado**
True preference point system — the strictest queue in the West. The highest
point holder draws first. Period. No randomness in the preference round.
Points accumulate by species (not by unit), so your elk points work for any
elk hunt code. You can list up to 4 hunt code choices; first-choice failures
earn a point, but if you draw on choices 2-4 you keep your existing points
without earning a new one. Over-the-counter licenses exist for many deer and
elk units (2nd and 3rd rifle especially) — no draw required. Strategy: stack
your max-point first choice, use remaining choices as fallbacks, and consider
OTC as your guaranteed safety valve while banking points for premium units.
Colorado switches to a 50/50 hybrid system in 2028.

**UT — Utah**
Two-track system within one state. Limited-entry hunts (trophy bull elk, trophy
buck deer) use bonus points in a 50/50 split: half the tags go to the top
point holders (preference queue), half go to a weighted random draw where each
bonus point squared plus one determines your entries. General season hunts
(spike elk, general buck deer) use a pure preference queue — highest points
draw first. You can buy a bonus point without applying, which matters for
long-term planning. Utah has a 5-year waiting period after drawing a limited-
entry deer or elk tag before nonresidents can reapply. The Dedicated Hunter
Program offers a guaranteed 3-year tag in exchange for conservation work.

**NV — Nevada**
Weighted random draw using the squared formula: entries = (bonus points + 1)².
A hunter with 4 points gets 25 entries; a zero-point hunter gets 1. No
reserve pass for max-point holders — everyone competes in the same pool.
Resident and nonresident pools are separate. Nevada issues very few elk tags
(150-300 statewide annually) — nonresident elk is one of the hardest draws
in North America with a 7-year waiting period after drawing. Deer is more
accessible. Points expire if you miss two consecutive years of applications.
The 2024 Big Game Hunt Data Excel file has quota information by unit.

**MT — Montana**
Two completely different systems in one state. For general season: residents
buy OTC licenses; nonresidents enter a preference point draw for combination
licenses (75% to highest point holders, 25% random, max 3 points). For
limited-entry permits — the prestigious units like Missouri Breaks, Sun River,
Breaks country trophy bull elk — BOTH residents and nonresidents compete in a
bonus point draw using the squared formula. A Montana resident cannot walk in
and buy a Missouri Breaks elk tag. They accumulate bonus points over years,
exactly like a nonresident. The limited-entry permit draw is where the real
trophy opportunity lives, and resident odds matter as much as nonresident odds.

**ID — Idaho**
Pure random draw. No points. No advantage for applying multiple years.
Each controlled hunt number (4-digit code) is drawn fresh every year.
90% of tags are awarded in an open random draw; 10% are reserved for
nonresidents specifically. General season tags are OTC for residents; starting
2026, nonresidents must apply for general season tags in a separate draw.
Deer are managed in numbered units; elk in numbered zones — these are different
geographic areas. The Hunt Planner at fishandgame.idaho.gov is the best public
draw odds tool in the West with CSV/Excel export.

**WY — Wyoming**
Preference point system with a 75/25 split: 75% of tags in each hunt area go
to the highest point holders (ordered queue), 25% are random. Nonresidents
only have two license tiers: Regular (lower price, lower priority pool) and
Special (higher price, smaller applicant pool, often better odds per dollar).
Residents can buy OTC licenses for many units. Preference points for elk and
deer are nonresident-only — residents have no point system for these species.
Wyoming is notable for having some of the best public land elk hunting in the
country in its general units, making OTC a legitimate strategy.

**OR — Oregon**
75/25 split with a twist: you earn a preference point whenever your first
choice doesn't draw — even if you drew on choices 2-5. Points are tracked
by hunt series (100-series = deer, 200-series = elk), not by individual hunt.
Premium hunts (L/M/N series) are pure random with no points. You can apply
for a Point Saver to buy a point without hunting for $10. Eastern Oregon deer
was completely restructured in 2026 from Wildlife Management Units to Hunt
Areas based on GPS data — historical data before 2026 uses old unit codes
that don't map directly to current areas. Oregon has some of the best
structured draw data in the West — Excel exports with applicants by hunt
choice going back multiple years.

**WA — Washington**
Squared bonus point system where residents and nonresidents compete in exactly
the same pool with no NR quota — unique among all western states. Points are
tracked by species category (Quality Deer, Buck Deer, Elk) rather than by
specific unit, and entries = bonus_points². The nonresident application fee
is significantly higher ($152 vs $10 resident) but both compete equally.
General season deer and elk are OTC for everyone. Washington has excellent
OTC opportunities, particularly for Roosevelt elk on the Olympic Peninsula
(one of the largest elk subspecies in North America) and general season elk
statewide. Draw odds data is locked in Power BI dashboards — the least
accessible state for automated data retrieval.

**CA — California**
Preference point system with a 90/10 split for deer (90% preference queue,
10% random) and 75/25 for elk. California is an extreme outlier: only about
362 elk tags issued statewide per year across three subspecies (Tule elk,
Roosevelt elk, Rocky Mountain elk), and only 1 nonresident elk tag is issued
annually statewide — for practical purposes, nonresidents cannot draw
California elk. Deer zones use a letter system (A through X, with subzones).
Points expire after a 5-year gap in applications. The X zones are the premium
deer tags and require many years of points. Most of the state's deer zones
have accessible draw odds for residents with a few points.

### 5. Strategy Guide (per state)
After the system explanation, a "Strategy" section with 2-4 actionable
recommendations for both residents and nonresidents. Keep it editorial,
specific, and useful. Examples:
- "If you're a nonresident planning your first AZ elk application, start
  accumulating bonus points now — the best rifle bull hunts require 15-20 years.
  Meanwhile, cow elk and some archery units are drawable in 3-5 years."
- "Colorado's OTC 2nd and 3rd rifle seasons are legitimate alternatives while
  banking points for premium units."

### 6. Odds Explorer (interactive data section)
Below the editorial content, the data explorer.

Filter bar (horizontal, sticky below header on scroll):
[ Species: Elk ▼ ] [ Pool: Resident ▼ ] [ Unit: All ▼ ] [ Year: 2025 ▼ ]

Results as a clean editorial table:
Columns: Hunt Code | Unit | Bag Limit | Weapon | Season | Odds | Apps | Tags | Harvest %

- Hunt code displayed exactly as agency publishes (never prefixed)
- Odds column: colored number — green >20%, amber 5-20%, red <5%, gray = no data
- Sort by any column header click
- Row click expands to show multi-year trend (if data available) and full details
- Empty state: "No draw data loaded yet for [State]. Check back soon." with
  a note about which raw files are available

### 7. Application Plan Tool
Tab or section below Odds Explorer.
Title: "Build Your Application"
- Pick up to 3 hunt codes (searchable dropdown, filtered by current state/species)
- Shows odds for each choice and combined probability
- Ordering advice (same logic as existing app for NM; generalized for other states)
- For states with points: shows how odds change at 0, 3, 5, 10 points

---

## API Endpoints Available (all working)
- GET /api/states → list of all 11 states with metadata
- GET /api/species?state_code=NM → species with data for state
- GET /api/units?state_code=NM&species_code=ELK → GMUs ordered by sort key
- GET /api/pools?state_code=NM → pools for state
- GET /api/hunts?state_code=NM&species_code=ELK&pool_code=RES → hunt table
- GET /api/draw_years?state_code=NM&species_code=ELK → available years
- POST /api/recommend → top 10 scored hunts
- POST /api/application_plan → 3-choice odds analysis
- GET /api/bag_limits?state_code=NM → bag limits for state
- GET /api/hunt_detail?state_code=NM&hunt_code=ELK-1-197 → full hunt detail

---

## Implementation Notes
- Single HTML file, all CSS and JS inline
- Use fetch() for all API calls — no jQuery, no frameworks
- Handle empty/no-data states gracefully (most states have no draw_results yet)
- State descriptions and strategy text are hardcoded in JS (not from API) —
  it's editorial content, not database content
- URL hash routing: clicking AZ → URL becomes #AZ, back button works
- On page load: if hash exists, load that state; otherwise load NM as default
- Smooth transitions between states (CSS opacity transition, no jarring reloads)
- Print-friendly: the editorial content should print cleanly

---

## Quality Bar
Ask yourself: does this look like it belongs on nytimes.com/interactive?
- Sharp typography hierarchy
- Generous whitespace
- Data presented with editorial context, not just raw numbers
- Every state's explanation good enough that a hunter who knows nothing
  about that state walks away understanding how to approach it
- The odds table feels like a Bloomberg or NYT data table — clean, sortable,
  color-coded but not garish

When done, verify the server is running and test:
curl http://localhost:5001/ → should return the new index.html
curl http://localhost:5001/api/states → should return JSON with all 11 states
