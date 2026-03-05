"""
GraysonsDrawOdds — Multi-state Flask app.
Connects to PostgreSQL draws database.
"""

import os
import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

DB_CONFIG = {
    "host": os.environ.get("DRAWS_DB_HOST", "localhost"),
    "port": os.environ.get("DRAWS_DB_PORT", "5432"),
    "dbname": os.environ.get("DRAWS_DB_NAME", "draws"),
    "user": os.environ.get("DRAWS_DB_USER", "draws"),
    "password": os.environ.get("DRAWS_DB_PASS", "drawspass"),
}

# NM species code mapping: the original NM app uses 'DER' but PG uses 'MDR'
NM_SPECIES_ALIAS = {"DER": "MDR"}


def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


def dict_rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _run_migration():
    """Add season_label column to hunts table if it doesn't exist."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "ALTER TABLE hunts ADD COLUMN IF NOT EXISTS season_label TEXT"
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


_run_migration()


# ─── Static ──────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ─── GET /api/states ──────────────────────────────────────────────────
@app.route("/api/states")
def api_states():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT state_id, state_code, state_name, draw_type, point_math,
               point_math_note, choices_per_app, can_buy_points, tag_turnback,
               unit_type_label, nr_allocation_note, has_otc_tags, has_landowner,
               app_deadline_month, results_month, residency_req, notes
        FROM states ORDER BY state_name
    """)
    rows = dict_rows(cur)
    conn.close()
    return jsonify({"states": rows})


# ─── GET /api/species ─────────────────────────────────────────────────
@app.route("/api/species")
def api_species():
    state_code = request.args.get("state_code")
    if not state_code:
        return jsonify({"error": "state_code is required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT sp.species_id, sp.species_code, sp.common_name
        FROM species sp
        JOIN hunts h ON h.species_id = sp.species_id
        JOIN states st ON st.state_id = h.state_id
        WHERE st.state_code = %s AND h.is_active = 1
        ORDER BY sp.common_name
    """, (state_code,))
    rows = dict_rows(cur)
    conn.close()
    return jsonify({"species": rows})


# ─── GET /api/units ───────────────────────────────────────────────────
@app.route("/api/units")
def api_units():
    state_code = request.args.get("state_code")
    species_code = request.args.get("species_code")
    if not state_code:
        return jsonify({"error": "state_code is required"}), 400

    conn = get_db()
    cur = conn.cursor()

    sql = """
        SELECT DISTINCT g.gmu_id, g.gmu_code, g.gmu_name, g.gmu_sort_key,
               st.unit_type_label
        FROM gmus g
        JOIN states st ON st.state_id = g.state_id
        WHERE st.state_code = %s
    """
    params = [state_code]

    if species_code:
        sql += """
            AND g.gmu_id IN (
                SELECT hg.gmu_id FROM hunt_gmus hg
                JOIN hunts h ON h.hunt_id = hg.hunt_id
                JOIN species sp ON sp.species_id = h.species_id
                WHERE sp.species_code = %s AND h.is_active = 1
                  AND h.state_id = st.state_id
            )
        """
        params.append(species_code)

    sql += " ORDER BY g.gmu_sort_key, g.gmu_code"
    cur.execute(sql, params)
    rows = dict_rows(cur)
    conn.close()

    for r in rows:
        if r["gmu_name"]:
            r["dropdown_label"] = f"{r['gmu_code']} — {r['gmu_name']}"
        else:
            r["dropdown_label"] = r["gmu_code"]

    return jsonify({"units": rows})


# ─── GET /api/pools ───────────────────────────────────────────────────
@app.route("/api/pools")
def api_pools():
    state_code = request.args.get("state_code")
    if not state_code:
        return jsonify({"error": "state_code is required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.pool_id, p.pool_code, p.description, p.allocation_pct,
               p.allocation_note
        FROM pools p
        JOIN states st ON st.state_id = p.state_id
        WHERE st.state_code = %s
        ORDER BY p.pool_id
    """, (state_code,))
    rows = dict_rows(cur)
    conn.close()
    return jsonify({"pools": rows})


# ─── GET /api/draw_years ─────────────────────────────────────────────
@app.route("/api/draw_years")
def api_draw_years():
    state_code = request.args.get("state_code")
    species_code = request.args.get("species_code")
    if not state_code:
        return jsonify({"error": "state_code is required"}), 400

    conn = get_db()
    cur = conn.cursor()
    sql = """
        SELECT DISTINCT dr.draw_year
        FROM draw_results_by_pool dr
        JOIN hunts h ON h.hunt_id = dr.hunt_id
        JOIN states st ON st.state_id = h.state_id
        WHERE st.state_code = %s
    """
    params = [state_code]
    if species_code:
        sql += " AND h.species_id = (SELECT species_id FROM species WHERE species_code = %s)"
        params.append(species_code)
    sql += " ORDER BY dr.draw_year DESC"

    cur.execute(sql, params)
    years = [r[0] for r in cur.fetchall()]
    conn.close()
    return jsonify({"draw_years": years})


# ─── GET /api/hunts ───────────────────────────────────────────────────
@app.route("/api/hunts")
def api_hunts():
    state_code = request.args.get("state_code")
    species_code = request.args.get("species_code")
    pool_code = request.args.get("pool_code")
    gmu_code = request.args.get("gmu_code")
    draw_year = request.args.get("draw_year", type=int)

    if not state_code:
        return jsonify({"error": "state_code is required"}), 400

    conn = get_db()
    cur = conn.cursor()

    sql = """
        SELECT
            h.hunt_id,
            h.hunt_code,
            COALESCE(h.hunt_code_display, h.hunt_code) AS hunt_label,
            h.unit_description,
            wt.weapon_code,
            h.season_type,
            h.tag_type,
            h.season_label,
            bl.bag_code,
            bl.label AS bag_label,
            dr.draw_year,
            dr.applications,
            dr.tags_available,
            dr.tags_awarded,
            CASE WHEN dr.applications > 0 AND dr.tags_awarded > 0
                 THEN ROUND(CAST(dr.tags_awarded AS NUMERIC) / dr.applications * 100, 1)
                 ELSE NULL END AS draw_odds_pct,
            dr.avg_pts_drawn,
            dr.min_pts_drawn,
            hs.harvest_year AS latest_harvest_year,
            hs.success_rate AS latest_success_rate,
            hs.days_hunted,
            latest_dates.start_date AS open_date,
            latest_dates.end_date AS close_date,
            latest_dates.season_year AS dates_season_year
        FROM hunts h
        JOIN states st ON st.state_id = h.state_id
        JOIN species sp ON sp.species_id = h.species_id
        LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
        LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
        LEFT JOIN (
            SELECT DISTINCT ON (hunt_id) hunt_id, start_date, end_date, season_year
            FROM hunt_dates
            ORDER BY hunt_id, season_year DESC
        ) latest_dates ON latest_dates.hunt_id = h.hunt_id
    """

    # Draw results join
    dr_join = """
        LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
    """
    params = []

    if pool_code:
        dr_join += " AND dr.pool_id = (SELECT pool_id FROM pools WHERE state_id = st.state_id AND pool_code = %s)"
        params.append(pool_code)
    if draw_year:
        dr_join += " AND dr.draw_year = %s"
        params.append(draw_year)

    sql += dr_join

    # Latest harvest join
    sql += """
        LEFT JOIN LATERAL (
            SELECT hs1.harvest_year, hs1.success_rate, hs1.days_hunted
            FROM harvest_stats hs1
            WHERE hs1.hunt_id = h.hunt_id AND hs1.access_type = 'Public'
            ORDER BY hs1.harvest_year DESC LIMIT 1
        ) hs ON true
    """

    sql += " WHERE st.state_code = %s AND h.is_active = 1"
    params.append(state_code)

    if species_code:
        sql += " AND sp.species_code = %s"
        params.append(species_code)

    if gmu_code:
        sql += """
            AND h.hunt_id IN (
                SELECT hg.hunt_id FROM hunt_gmus hg
                JOIN gmus g ON g.gmu_id = hg.gmu_id
                WHERE g.state_id = st.state_id AND g.gmu_code = %s
            )
        """
        params.append(gmu_code)

    sql += " ORDER BY h.hunt_code LIMIT 500"

    cur.execute(sql, params)
    rows = dict_rows(cur)
    conn.close()

    # Deduplicate by hunt_code (can happen when no pool filter is set)
    seen = set()
    deduped = []
    for r in rows:
        if r["hunt_code"] not in seen:
            seen.add(r["hunt_code"])
            deduped.append(r)
    rows = deduped

    # Serialize date objects to strings
    for r in rows:
        if r.get("open_date"):
            r["open_date"] = str(r["open_date"])
        if r.get("close_date"):
            r["close_date"] = str(r["close_date"])

    return jsonify({"hunts": rows})


# ─── GET /api/hunt_detail ─────────────────────────────────────────────
@app.route("/api/hunt_detail")
def api_hunt_detail():
    state_code = request.args.get("state_code")
    hunt_code = request.args.get("hunt_code")
    if not state_code or not hunt_code:
        return jsonify({"error": "state_code and hunt_code are required"}), 400

    conn = get_db()
    cur = conn.cursor()

    # Basic hunt info
    cur.execute("""
        SELECT h.hunt_id, h.hunt_code,
               COALESCE(h.hunt_code_display, h.hunt_code) AS hunt_label,
               h.unit_description, h.season_type, h.tag_type, h.season_label,
               wt.weapon_code, bl.bag_code, bl.label AS bag_label,
               bl.plain_definition AS bag_definition
        FROM hunts h
        JOIN states st ON st.state_id = h.state_id
        LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
        LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
        WHERE st.state_code = %s AND h.hunt_code = %s
    """, (state_code, hunt_code))
    hunt_rows = dict_rows(cur)
    if not hunt_rows:
        conn.close()
        return jsonify({"error": "Hunt not found"}), 404
    hunt = hunt_rows[0]
    hunt_id = hunt["hunt_id"]

    # All draw years
    cur.execute("""
        SELECT dr.draw_year, p.pool_code, dr.applications, dr.tags_available,
               dr.tags_awarded, dr.avg_pts_drawn, dr.min_pts_drawn
        FROM draw_results_by_pool dr
        JOIN pools p ON p.pool_id = dr.pool_id
        WHERE dr.hunt_id = %s
        ORDER BY dr.draw_year DESC, p.pool_code
    """, (hunt_id,))
    draw_history = dict_rows(cur)

    # All harvest years
    cur.execute("""
        SELECT harvest_year, access_type, success_rate, satisfaction,
               days_hunted, licenses_sold
        FROM harvest_stats
        WHERE hunt_id = %s
        ORDER BY harvest_year DESC
    """, (hunt_id,))
    harvest_history = dict_rows(cur)

    # Season dates
    cur.execute("""
        SELECT season_year, start_date, end_date, hunt_name
        FROM hunt_dates WHERE hunt_id = %s
        ORDER BY season_year DESC
    """, (hunt_id,))
    dates = dict_rows(cur)

    conn.close()
    hunt["draw_history"] = draw_history
    hunt["harvest_history"] = harvest_history
    hunt["season_dates"] = dates
    return jsonify(hunt)


# ─── POST /api/recommend ─────────────────────────────────────────────
@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    data = request.get_json(silent=True) or {}
    state_code = data.get("state_code")
    species_code = data.get("species_code")
    pool_code = data.get("pool_code", "RES")
    gmu_code = data.get("gmu_code")
    draw_year = data.get("draw_year")

    if not state_code or not species_code:
        return jsonify({"error": "state_code and species_code are required"}), 400

    conn = get_db()
    cur = conn.cursor()

    sql = """
        SELECT h.hunt_code, h.unit_description,
               COALESCE(h.hunt_code_display, h.hunt_code) AS hunt_label,
               sp.common_name AS species_name,
               bl.bag_code,
               wt.weapon_code,
               dr.applications, dr.tags_awarded,
               hs.success_rate, hs.harvest_year,
               hd.hunt_name
        FROM hunts h
        JOIN states st ON st.state_id = h.state_id
        JOIN species sp ON sp.species_id = h.species_id
        LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
        LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
        LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
            AND dr.pool_id = (SELECT pool_id FROM pools WHERE state_id = st.state_id AND pool_code = %s)
    """
    params = [pool_code]

    if draw_year:
        sql += " AND dr.draw_year = %s"
        params.append(draw_year)
    else:
        sql += " AND dr.draw_year = (SELECT MAX(draw_year) FROM draw_results_by_pool WHERE hunt_id = h.hunt_id)"

    sql += """
        LEFT JOIN LATERAL (
            SELECT hs1.success_rate, hs1.harvest_year
            FROM harvest_stats hs1
            WHERE hs1.hunt_id = h.hunt_id AND hs1.access_type = 'Public'
            ORDER BY hs1.harvest_year DESC LIMIT 1
        ) hs ON true
        LEFT JOIN LATERAL (
            SELECT hd1.hunt_name
            FROM hunt_dates hd1
            WHERE hd1.hunt_id = h.hunt_id
            ORDER BY hd1.season_year DESC LIMIT 1
        ) hd ON true
        WHERE st.state_code = %s AND sp.species_code = %s AND h.is_active = 1
    """
    params.extend([state_code, species_code])

    if gmu_code:
        sql += """
            AND h.hunt_id IN (
                SELECT hg.hunt_id FROM hunt_gmus hg
                JOIN gmus g ON g.gmu_id = hg.gmu_id
                WHERE g.state_id = st.state_id AND g.gmu_code = %s
            )
        """
        params.append(gmu_code)

    # Exclude youth and mobility impaired
    sql += """
        AND (h.unit_description IS NULL
             OR (LOWER(h.unit_description) NOT LIKE '%%youth%%'
                 AND LOWER(h.unit_description) NOT LIKE '%%mobility%%'))
        AND (hd.hunt_name IS NULL
             OR (LOWER(hd.hunt_name) NOT LIKE '%%youth%%'
                 AND LOWER(hd.hunt_name) NOT LIKE '%%mobility%%'))
    """

    cur.execute(sql, params)
    rows = dict_rows(cur)
    conn.close()

    scored = []
    for r in rows:
        apps = r["applications"]
        awarded = r["tags_awarded"]
        sr = r["success_rate"]
        if not apps or not awarded or sr is None:
            continue
        odds = awarded / apps
        if odds <= 0:
            continue

        # NM scoring: score = draw_odds * 0.4 + success * 0.6
        score = (odds * 100) * 0.4 + sr * 0.6
        note = _classify_note(odds, r["hunt_code"])

        scored.append({
            "hunt_code": r["hunt_code"],
            "hunt_label": r["hunt_label"],
            "unit_description": r["unit_description"],
            "hunt_name": r["hunt_name"],
            "species_name": r["species_name"],
            "bag_code": r["bag_code"],
            "weapon_code": r["weapon_code"],
            "draw_odds": odds,
            "success_rate": sr,
            "harvest_year": r["harvest_year"],
            "score": score,
            "note": note,
        })

    scored.sort(key=lambda x: (x["score"], x["draw_odds"]), reverse=True)
    return jsonify({"results": scored[:10], "pool_code": pool_code})


def _classify_note(odds, hunt_code):
    if odds >= 0.25:
        tier = "high"
    elif odds >= 0.10:
        tier = "mid"
    else:
        tier = "low"

    idx = ord(hunt_code[-1]) % 3

    templates = {
        "high": [
            "Textbook third choice safety hunt: very high odds without giving up much in the way of opportunity.",
            "Great safety pick. You are playing in the high odds tier here, which is exactly what you want for a third choice.",
            "This is the kind of hunt you park in the third slot when you actually want to go hunting instead of just buying a lottery ticket.",
        ],
        "mid": [
            "Nice middle of the road odds. This is a solid second choice if your first pick is a long shot.",
            "Good candidate for a second choice: odds are respectable and the success numbers say it is worth showing up prepared.",
            "Balanced odds for a second tier hunt. Not a gimme, but not a moonshot either.",
        ],
        "low": [
            "Classic first choice tag: low odds, but the kind of hunt you swing for when you want something special.",
            "Treat this as a swing for the fences first choice. Odds are tight enough that it should not be sitting in your third slot.",
            "This belongs in your dream hunt bucket. Odds are slim, which is exactly what you expect for a true first choice.",
        ],
    }
    return templates[tier][idx]


# ─── POST /api/application_plan ───────────────────────────────────────
@app.route("/api/application_plan", methods=["POST"])
def api_application_plan():
    data = request.get_json(silent=True) or {}
    state_code = data.get("state_code")
    species_code = data.get("species_code")
    pool_code = data.get("pool_code", "RES")
    choices = data.get("choices") or []

    if not state_code or not species_code:
        return jsonify({"error": "state_code and species_code are required"}), 400
    if len(choices) != 3:
        return jsonify({"error": "Exactly three choices are required"}), 400

    conn = get_db()
    cur = conn.cursor()

    # For NM legacy: use draw_results table with pivoted columns
    # For normalized: use draw_results_by_pool
    placeholders = ",".join(["%s"] * len(choices))

    sql = f"""
        SELECT h.hunt_code, sp.common_name AS species_name,
               dr.applications, dr.tags_awarded
        FROM hunts h
        JOIN states st ON st.state_id = h.state_id
        JOIN species sp ON sp.species_id = h.species_id
        JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
            AND dr.pool_id = (SELECT pool_id FROM pools WHERE state_id = st.state_id AND pool_code = %s)
            AND dr.draw_year = (SELECT MAX(draw_year) FROM draw_results_by_pool WHERE hunt_id = h.hunt_id)
        WHERE st.state_code = %s AND sp.species_code = %s
          AND h.hunt_code IN ({placeholders})
    """
    cur.execute(sql, [pool_code, state_code, species_code, *choices])
    rows = dict_rows(cur)
    conn.close()

    odds_map = {}
    species_name = None
    for r in rows:
        apps = r["applications"]
        awarded = r["tags_awarded"]
        p = awarded / apps if apps and awarded else None
        odds_map[r["hunt_code"]] = {
            "applications": apps,
            "tags_awarded": awarded,
            "p": p,
        }
        species_name = r["species_name"]

    choice_details = []
    probs = []
    for idx, code in enumerate(choices, start=1):
        rec = odds_map.get(code)
        if not rec:
            choice_details.append({
                "choice_number": idx, "hunt_code": code,
                "applications": None, "tags_awarded": None, "p": None,
            })
            probs.append(None)
        else:
            choice_details.append({
                "choice_number": idx, "hunt_code": code,
                "applications": rec["applications"],
                "tags_awarded": rec["tags_awarded"],
                "p": rec["p"],
            })
            probs.append(rec["p"])

    p1, p2, p3 = probs
    eps = 0.005
    logical = (
        p1 is not None and p2 is not None and p3 is not None
        and p1 <= p2 + eps and p2 <= p3 + eps
    )

    valid_probs = [p for p in probs if p is not None and p > 0]
    application_odds = max(valid_probs) if valid_probs else None
    one_in_n = round(1.0 / application_odds) if application_odds and application_odds > 0 else None

    advice = _build_advice(state_code, species_code, logical, p1, p2, p3, eps)

    return jsonify({
        "state_code": state_code,
        "pool_code": pool_code,
        "species_code": species_code,
        "species_name": species_name,
        "choices": choice_details,
        "logical_order": logical,
        "application_odds": application_odds,
        "one_in_n": one_in_n,
        "advice": advice,
    })


def _build_advice(state_code, species_code, logical, p1, p2, p3, eps):
    parts = []
    if not logical:
        parts.append(
            "Your three hunts are not ordered from hardest to easiest to draw in your pool."
        )
        if p1 is not None and p2 is not None and p1 > p2 + eps:
            parts.append(
                "Your first choice has better odds than your second choice, "
                "so in practical terms you will almost never see that second choice tag."
            )
        if p2 is not None and p3 is not None and p2 > p3 + eps:
            parts.append(
                "Your second choice has better odds than your third choice, "
                "so the third choice is not acting as a true safety hunt."
            )
        # NM-specific advice
        if state_code == "NM":
            if species_code in ("ELK", "MDR"):
                sc = species_code
                # Map MDR back to old code for advice text
                if sc == "MDR":
                    sc = "DER"
                if sc == "ELK":
                    parts.append(
                        "For elk, it is totally reasonable to run a dream first choice in the Gila, "
                        "Valle Vidal, or Valles Caldera and then stack easier hunts behind it. "
                        "As long as one of your later choices is a true high odds tag, you are not "
                        "hurting your overall chance of going hunting."
                    )
                elif sc == "DER":
                    parts.append(
                        "For deer, units like 2B and 23 Burro Mountains are classic dream draws. "
                        "You can put one of those first and still use a high odds tag later in the "
                        "list to protect your overall chances."
                    )
        else:
            parts.append(
                "Consider reordering so the hardest hunt is first and the easiest is last."
            )
    else:
        if state_code == "NM":
            parts.append(
                "Your application is logically ordered: toughest hunt first, easiest last. "
                "In the real New Mexico system that is exactly what you want."
            )
            parts.append(
                "Because the computer walks your choices in order for one random number, "
                "the hunt with the highest odds on your list is what really sets your overall "
                "chance of drawing something."
            )
        else:
            parts.append(
                "Your application is logically ordered: toughest hunt first, easiest last."
            )
            parts.append(
                "The hunt with the highest odds on your list is what really drives your "
                "overall chance of drawing something."
            )

    return " ".join(parts) if parts else None


# ─── GET /api/bag_limits ──────────────────────────────────────────────
@app.route("/api/bag_limits")
def api_bag_limits():
    state_code = request.args.get("state_code")
    conn = get_db()
    cur = conn.cursor()

    if state_code:
        cur.execute("""
            SELECT DISTINCT bl.bag_code, bl.label, bl.plain_definition
            FROM bag_limits bl
            JOIN hunts h ON h.bag_limit_id = bl.bag_limit_id
            JOIN states st ON st.state_id = h.state_id
            WHERE st.state_code = %s
            ORDER BY bl.bag_code
        """, (state_code,))
    else:
        cur.execute("SELECT bag_code, label, plain_definition FROM bag_limits ORDER BY bag_code")

    rows = dict_rows(cur)
    conn.close()
    return jsonify({"bag_limits": rows})


def _compute_season_labels_nm():
    """Compute season_label for NM hunts based on weapon, bag, and date data."""
    from collections import defaultdict
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT h.hunt_id, h.hunt_code, wt.weapon_code, bl.bag_code,
                   bl.label AS bag_label, hd.start_date, hd.hunt_name,
                   array_agg(DISTINCT g.gmu_code) AS gmu_codes
            FROM hunts h
            JOIN states st ON st.state_id = h.state_id
            LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
            LEFT JOIN bag_limits bl ON bl.bag_limit_id = h.bag_limit_id
            LEFT JOIN (
                SELECT DISTINCT ON (hunt_id) hunt_id, start_date, hunt_name
                FROM hunt_dates ORDER BY hunt_id, season_year DESC
            ) hd ON hd.hunt_id = h.hunt_id
            LEFT JOIN hunt_gmus hg ON hg.hunt_id = h.hunt_id
            LEFT JOIN gmus g ON g.gmu_id = hg.gmu_id
            WHERE st.state_code = 'NM' AND h.is_active = 1
            GROUP BY h.hunt_id, h.hunt_code, wt.weapon_code, bl.bag_code,
                     bl.label, hd.start_date, hd.hunt_name
            ORDER BY h.hunt_code
        """)
        rows = dict_rows(cur)

        def sex_label(bag_code, bag_label):
            bc = (bag_code or "").upper()
            bl_lower = (bag_label or "").lower()
            if bc == "A" or "antlerless" in bl_lower:
                return "Antlerless"
            if "cow" in bl_lower:
                return "Cow"
            if "either sex" in bl_lower or bc == "ES":
                return "Either Sex"
            if "mature bull" in bl_lower or bc == "MB":
                return "Bull"
            if "spike" in bl_lower:
                return "Spike"
            if "fork" in bl_lower:
                return "Fork Antlered"
            if "doe" in bl_lower:
                return "Doe"
            if "buck" in bl_lower:
                return "Buck"
            if "ram" in bl_lower:
                return "Ram"
            if "ewe" in bl_lower:
                return "Ewe"
            return bag_code

        weapon_map = {
            "RIFLE": "Rifle", "ARCHERY": "Archery", "MUZZ": "Muzzleloader",
            "ANY": "Any Weapon", "SRW": "Short-Range", "SHOTGUN": "Shotgun",
        }

        groups = defaultdict(list)
        hunt_info = {}
        for r in rows:
            sex = sex_label(r["bag_code"], r["bag_label"])
            weapon = weapon_map.get((r["weapon_code"] or "").upper(), r["weapon_code"])
            gmus = tuple(sorted(r["gmu_codes"] or []))
            hunt_info[r["hunt_id"]] = {"sex": sex, "weapon": weapon}
            groups[(gmus, r["weapon_code"], sex)].append(r)

        ordinals = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth"]
        for key, group_rows in groups.items():
            group_rows.sort(key=lambda x: (str(x["start_date"] or "9999"), x["hunt_code"]))
            for idx, r in enumerate(group_rows):
                info = hunt_info[r["hunt_id"]]
                parts = []
                if len(group_rows) > 1 and idx < len(ordinals):
                    parts.append(ordinals[idx])
                if info["weapon"]:
                    parts.append(info["weapon"])
                if info["sex"]:
                    parts.append(info["sex"])
                label = " ".join(parts) if parts else None
                cur.execute("UPDATE hunts SET season_label = %s WHERE hunt_id = %s",
                            (label, r["hunt_id"]))

        conn.commit()
        conn.close()
    except Exception:
        import traceback
        traceback.print_exc()


_compute_season_labels_nm()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
