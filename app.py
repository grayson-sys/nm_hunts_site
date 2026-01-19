import os
import sqlite3
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "nm_hunts.db")

DRAW_YEAR = 2025
SEASON_YEAR = 2026

app = Flask(__name__, static_folder="static", static_url_path="")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


POOL_CONFIG = {
    "resident": {
        "applications_col": "resident_applications",
        "licenses_col": "resident_licenses",
        "label": "Resident",
    },
    "nonresident": {
        "applications_col": "nonresident_applications",
        "licenses_col": "nonresident_licenses",
        "label": "Nonresident",
    },
    "outfitter": {
        "applications_col": "outfitter_applications",
        "licenses_col": "outfitter_licenses",
        "label": "Outfitter",
    },
}

WEAPON_DIGIT = {
    "rifle": "1",
    "archery": "2",
    "muzzleloader": "3",
}


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def build_gmu_filter_clause(gmu_number: int):
    g = str(gmu_number)
    patterns = [
        f"% {g},%",
        f"% {g}:%",
        f"% {g} %",
        f"% {g} and%",
        f"% {g}%",
    ]
    clauses = []
    params = []
    for p in patterns:
        clauses.append("h.unit_description LIKE ?")
        params.append(p)
    return "(" + " OR ".join(clauses) + ")", params


def harvest_latest_join():
    return """
    LEFT JOIN (
      SELECT hs1.hunt_id,
             MAX(hs1.harvest_year) AS latest_harvest_year
      FROM harvest_stats hs1
      WHERE hs1.access_type = 'Public'
      GROUP BY hs1.hunt_id
    ) latest
      ON latest.hunt_id = h.hunt_id
    LEFT JOIN harvest_stats hs
      ON hs.hunt_id = h.hunt_id
     AND hs.harvest_year = latest.latest_harvest_year
     AND hs.access_type = 'Public'
    """


def classify_notes(pool: str, odds: float, hunt_code: str):
    if odds is None:
        return "No odds data available for this hunt."

    if odds >= 0.25:
        tier = "high"
    elif odds >= 0.10:
        tier = "mid"
    else:
        tier = "low"

    idx = ord(hunt_code[-1]) % 3

    if tier == "high":
        templates = [
            "Textbook third choice safety hunt: very high odds without giving up much in the way of opportunity.",
            "Great safety pick. You are playing in the high odds tier here, which is exactly what you want for a third choice.",
            "This is the kind of hunt you park in the third slot when you actually want to go hunting instead of just buying a lottery ticket.",
        ]
    elif tier == "mid":
        templates = [
            "Nice middle of the road odds. This is a solid second choice if your first pick is a long shot.",
            "Good candidate for a second choice: odds are respectable and the success numbers say it is worth showing up prepared.",
            "Balanced odds for a second tier hunt. Not a gimme, but not a moonshot either.",
        ]
    else:
        templates = [
            "Classic first choice tag: low odds, but the kind of hunt you swing for when you want something special.",
            "Treat this as a swing for the fences first choice. Odds are tight enough that it should not be sitting in your third slot.",
            "This belongs in your dream hunt bucket. Odds are slim, which is exactly what you expect for a true first choice.",
        ]

    return templates[idx]


@app.route("/api/draw_odds")
def api_draw_odds():
    pool = request.args.get("pool", "resident")
    weapon = request.args.get("weapon", "all")
    species_code = request.args.get("species_code")
    gmu = request.args.get("gmu", type=int)

    if pool not in POOL_CONFIG:
        return jsonify({"error": "Invalid pool"}), 400
    if not species_code:
        return jsonify({"error": "species_code is required"}), 400
    if gmu is None:
        return jsonify({"error": "gmu is required"}), 400

    cfg = POOL_CONFIG[pool]
    app_col = cfg["applications_col"]
    lic_col = cfg["licenses_col"]

    conn = get_db_connection()
    cur = conn.cursor()

    sql = f"""
    SELECT
      h.hunt_code,
      s.species_code,
      s.common_name AS species_name,
      h.unit_description,
      hd.hunt_name,
      hd.start_date,
      hd.end_date,
      dr.{app_col} AS applications,
      dr.{lic_col} AS licenses,
      hs.success_rate,
      hs.harvest_year,
      bl.bag_code
    FROM hunts h
    JOIN species s ON h.species_id = s.species_id
    JOIN draw_results dr
      ON dr.hunt_id = h.hunt_id
     AND dr.draw_year = ?
    JOIN hunt_dates hd
      ON hd.hunt_id = h.hunt_id
     AND hd.season_year = ?
    LEFT JOIN bag_limits bl
      ON bl.bag_limit_id = h.bag_limit_id
    {harvest_latest_join()}
    WHERE h.is_active = 1
      AND s.species_code = ?
    """
    params = [DRAW_YEAR, SEASON_YEAR, species_code]

    gclause, gparams = build_gmu_filter_clause(gmu)
    sql += f" AND {gclause}"
    params.extend(gparams)

    if weapon in WEAPON_DIGIT:
        digit = WEAPON_DIGIT[weapon]
        sql += " AND h.hunt_code LIKE ?"
        params.append(f"%-{digit}-%")

    sql += f" ORDER BY dr.{app_col} DESC LIMIT 50"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        apps = r["applications"]
        lic = r["licenses"]
        odds = lic / apps if apps and lic else 0.0

        results.append(
            {
                "hunt_code": r["hunt_code"],
                "species_code": r["species_code"],
                "species_name": r["species_name"],
                "unit_description": r["unit_description"],
                "hunt_name": r["hunt_name"],
                "start_date": r["start_date"],
                "end_date": r["end_date"],
                "draw_odds": odds,
                "success_rate": r["success_rate"],
                "harvest_year": r["harvest_year"],
                "bag_code": r["bag_code"],
            }
        )

    return jsonify(
        {
            "pool": pool,
            "pool_label": cfg["label"],
            "draw_year": DRAW_YEAR,
            "season_year": SEASON_YEAR,
            "results": results,
        }
    )


@app.route("/api/hunts")
def api_hunts():
    species_code = request.args.get("species_code")
    if not species_code:
        return jsonify({"error": "species_code is required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT h.hunt_code, h.unit_description
        FROM hunts h
        JOIN species s ON h.species_id = s.species_id
        WHERE s.species_code = ?
          AND h.is_active = 1
        ORDER BY h.hunt_code
        """,
        (species_code,),
    )
    rows = cur.fetchall()
    conn.close()

    hunts = []
    for r in rows:
        label = r["hunt_code"]
        if r["unit_description"]:
            label = f"{label} - {r['unit_description']}"
        hunts.append({"hunt_code": r["hunt_code"], "label": label})

    return jsonify({"hunts": hunts})


@app.route("/api/best_hunts")
def api_best_hunts():
    pool = request.args.get("pool", "resident")
    species_code = request.args.get("species_code")
    weapon = request.args.get("weapon", "all")

    if pool not in POOL_CONFIG:
        return jsonify({"error": "Invalid pool"}), 400
    if not species_code:
        return jsonify({"error": "species_code is required"}), 400

    cfg = POOL_CONFIG[pool]
    app_col = cfg["applications_col"]
    lic_col = cfg["licenses_col"]

    conn = get_db_connection()
    cur = conn.cursor()

    sql = f"""
    SELECT
      h.hunt_code,
      h.unit_description,
      s.common_name AS species_name,
      hd.hunt_name,
      dr.{app_col} AS applications,
      dr.{lic_col} AS licenses,
      hs.success_rate,
      hs.harvest_year,
      bl.bag_code
    FROM hunts h
    JOIN species s ON h.species_id = s.species_id
    JOIN draw_results dr
      ON dr.hunt_id = h.hunt_id
     AND dr.draw_year = ?
    {harvest_latest_join()}
    LEFT JOIN hunt_dates hd
      ON hd.hunt_id = h.hunt_id
     AND hd.season_year = ?
    LEFT JOIN bag_limits bl
      ON bl.bag_limit_id = h.bag_limit_id
    WHERE h.is_active = 1
      AND s.species_code = ?
    """
    params = [DRAW_YEAR, SEASON_YEAR, species_code]

    if weapon in WEAPON_DIGIT:
        digit = WEAPON_DIGIT[weapon]
        sql += " AND h.hunt_code LIKE ?"
        params.append(f"%-{digit}-%")

    # Exclude youth and mobility impaired hunts from cheat codes
    sql += """
      AND (
        h.unit_description IS NULL
        OR (LOWER(h.unit_description) NOT LIKE '%youth%' AND LOWER(h.unit_description) NOT LIKE '%mobility%')
      )
      AND (
        hd.hunt_name IS NULL
        OR (LOWER(hd.hunt_name) NOT LIKE '%youth%' AND LOWER(hd.hunt_name) NOT LIKE '%mobility%')
      )
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    scored = []
    for r in rows:
        apps = r["applications"]
        lic = r["licenses"]
        sr = r["success_rate"]
        if not apps or not lic or sr is None:
            continue
        odds = lic / apps
        if odds <= 0:
            continue

        score = sr * odds
        note = classify_notes(pool, odds, r["hunt_code"])

        scored.append(
            {
                "hunt_code": r["hunt_code"],
                "unit_description": r["unit_description"],
                "hunt_name": r["hunt_name"],
                "species_name": r["species_name"],
                "draw_odds": odds,
                "success_rate": sr,
                "harvest_year": r["harvest_year"],
                "bag_code": r["bag_code"],
                "score": score,
                "note": note,
            }
        )

    scored.sort(key=lambda x: (x["score"], x["draw_odds"]), reverse=True)
    top = scored[:10]

    return jsonify(
        {
            "pool": pool,
            "pool_label": cfg["label"],
            "draw_year": DRAW_YEAR,
            "results": top,
        }
    )


@app.route("/api/application_plan", methods=["POST"])
def api_application_plan():
    data = request.get_json(silent=True) or {}
    pool = data.get("pool", "resident")
    species_code = data.get("species_code")
    choices = data.get("choices") or []

    if pool not in POOL_CONFIG:
        return jsonify({"error": "Invalid pool"}), 400
    if not species_code:
        return jsonify({"error": "species_code is required"}), 400
    if len(choices) != 3:
        return jsonify({"error": "Exactly three choices are required"}), 400

    cfg = POOL_CONFIG[pool]
    app_col = cfg["applications_col"]
    lic_col = cfg["licenses_col"]

    conn = get_db_connection()
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in choices)
    sql = f"""
    SELECT
      h.hunt_code,
      s.common_name AS species_name,
      dr.{app_col} AS applications,
      dr.{lic_col} AS licenses
    FROM hunts h
    JOIN species s ON h.species_id = s.species_id
    JOIN draw_results dr
      ON dr.hunt_id = h.hunt_id
     AND dr.draw_year = ?
    WHERE s.species_code = ?
      AND h.hunt_code IN ({placeholders})
    """
    cur.execute(sql, [DRAW_YEAR, species_code, *choices])
    rows = cur.fetchall()
    conn.close()

    odds_map = {}
    species_name = None
    for r in rows:
        apps = r["applications"]
        lic = r["licenses"]
        if apps and lic:
            p = lic / apps
        else:
            p = None
        odds_map[r["hunt_code"]] = {
            "applications": apps,
            "licenses": lic,
            "p": p,
        }
        species_name = r["species_name"]

    choice_details = []
    probs = []
    for idx, code in enumerate(choices, start=1):
        rec = odds_map.get(code)
        if not rec:
            choice_details.append(
                {
                    "choice_number": idx,
                    "hunt_code": code,
                    "applications": None,
                    "licenses": None,
                    "p": None,
                }
            )
            probs.append(None)
        else:
            choice_details.append(
                {
                    "choice_number": idx,
                    "hunt_code": rec and code,
                    "applications": rec["applications"],
                    "licenses": rec["licenses"],
                    "p": rec["p"],
                }
            )
            probs.append(rec["p"])

    p1, p2, p3 = probs
    eps = 0.005
    logical = (
        p1 is not None
        and p2 is not None
        and p3 is not None
        and p1 <= p2 + eps
        and p2 <= p3 + eps
    )

    valid_probs = [p for p in probs if p is not None and p > 0]
    application_odds = max(valid_probs) if valid_probs else None
    one_in_n = None
    if application_odds and application_odds > 0:
        one_in_n = round(1.0 / application_odds)

    advice_parts = []
    if not logical:
        advice_parts.append(
            "Your three hunts are not ordered from hardest to easiest to draw in your pool."
        )
        if p1 is not None and p2 is not None and p1 > p2 + eps:
            advice_parts.append(
                "Your first choice has better odds than your second choice, so in practical terms you will almost never see that second choice tag."
            )
        if p2 is not None and p3 is not None and p2 > p3 + eps:
            advice_parts.append(
                "Your second choice has better odds than your third choice, so the third choice is not acting as a true safety hunt."
            )
        if species_code == "ELK":
            advice_parts.append(
                "For elk, it is totally reasonable to run a dream first choice in the Gila, Valle Vidal, or Valles Caldera and then stack easier hunts behind it. As long as one of your later choices is a true high odds tag, you are not hurting your overall chance of going hunting."
            )
        if species_code == "DER":
            advice_parts.append(
                "For deer, units like 2B and 23 Burro Mountains are classic dream draws. You can put one of those first and still use a high odds tag later in the list to protect your overall chances."
            )
    else:
        advice_parts.append(
            "Your application is logically ordered: toughest hunt first, easiest last. In the real New Mexico system that is exactly what you want."
        )
        advice_parts.append(
            "Because the computer walks your choices in order for one random number, the hunt with the highest odds on your list is what really sets your overall chance of drawing something."
        )

    advice = " ".join(advice_parts) if advice_parts else None

    return jsonify(
        {
            "pool": pool,
            "pool_label": cfg["label"],
            "species_code": species_code,
            "species_name": species_name,
            "choices": choice_details,
            "logical_order": logical,
            "application_odds": application_odds,
            "one_in_n": one_in_n,
            "advice": advice,
        }
    )


@app.route("/api/bag_limits")
def api_bag_limits():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT bag_code, label, plain_definition
        FROM bag_limits
        ORDER BY bag_code
        """
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify(
        {
            "bag_limits": [
                {
                    "bag_code": r["bag_code"],
                    "label": r["label"],
                    "plain_definition": r["plain_definition"],
                }
                for r in rows
            ]
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
