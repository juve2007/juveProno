"""
track_record.py
------------------
Garde une trace de chaque pronostic "Top 5" publié chaque jour, puis
vérifie automatiquement s'il avait raison une fois le match joué.
Sert à afficher un vrai taux de réussite sur le dashboard — la preuve
chiffrée que le modèle tient la route (ou pas).

history.json accumule ces enregistrements d'une exécution à l'autre.
Contrairement à config.json, ce fichier DOIT être commité sur GitHub
pour que l'historique survive d'un jour à l'autre (rien de sensible
dedans, juste des matchs et des résultats).
"""

import json
import os
from datetime import date, timedelta

MARKET_LABELS = {
    "home": "{home} gagne",
    "draw": "Match nul",
    "away": "{away} gagne",
    "over25": "Plus de 2,5 buts",
    "under25": "Moins de 2,5 buts",
    "btts_yes": "Les 2 équipes marquent",
    "btts_no": "Au moins une équipe ne marque pas",
}


def compute_top_picks(matches: list[dict], n: int = 5) -> list[dict]:
    """Reproduit exactement la logique de classement du dashboard (JS) côté Python,
    pour pouvoir enregistrer officiellement les picks du jour."""
    scored = []
    for m in matches:
        candidates = [
            ("home", m["p_home"]),
            ("draw", m["p_draw"]),
            ("away", m["p_away"]),
            ("over25", m["over25"]),
            ("under25", 100 - m["over25"]),
            ("btts_yes", m["btts"]),
            ("btts_no", 100 - m["btts"]),
        ]
        pick_type, prob = max(candidates, key=lambda c: c[1])
        scored.append({
            "match_id": m.get("match_id"),
            "competition": m["competition"],
            "date": m["date"],
            "home": m["home"],
            "away": m["away"],
            "pick_type": pick_type,
            "pick_label": MARKET_LABELS[pick_type].format(home=m["home"], away=m["away"]),
            "probability": prob,
        })
    scored.sort(key=lambda s: s["probability"], reverse=True)
    return scored[:n]


def outcome_correct(pick_type: str, home_goals: int, away_goals: int) -> bool:
    total = home_goals + away_goals
    return {
        "home": home_goals > away_goals,
        "draw": home_goals == away_goals,
        "away": away_goals > home_goals,
        "over25": total > 2,
        "under25": total <= 2,
        "btts_yes": home_goals > 0 and away_goals > 0,
        "btts_no": home_goals == 0 or away_goals == 0,
    }[pick_type]


def load_history(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(path: str, history: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def settle_pending(history: list[dict], finished_lookup: dict) -> int:
    """finished_lookup : {match_id: (home_goals, away_goals)}. Retourne le nombre réglé."""
    settled = 0
    for rec in history:
        if rec.get("result") != "pending":
            continue
        if rec.get("match_id") in finished_lookup:
            hg, ag = finished_lookup[rec["match_id"]]
            rec["result"] = "win" if outcome_correct(rec["pick_type"], hg, ag) else "loss"
            rec["final_score"] = f"{hg}-{ag}"
            settled += 1
    return settled


def add_todays_picks(history: list[dict], picks: list[dict]) -> int:
    existing_ids = {r.get("match_id") for r in history if r.get("match_id")}
    added = 0
    for p in picks:
        if not p.get("match_id") or p["match_id"] in existing_ids:
            continue  # déjà enregistré (le robot a tourné plusieurs fois le même jour)
        history.append({**p, "result": "pending", "final_score": None})
        added += 1
    return added


def summarize(history: list[dict]) -> dict:
    settled = [r for r in history if r.get("result") in ("win", "loss")]
    wins = sum(1 for r in settled if r["result"] == "win")
    accuracy = round(wins / len(settled) * 100, 1) if settled else None

    cutoff = (date.today() - timedelta(days=30)).isoformat()
    recent_settled = [r for r in settled if r["date"] >= cutoff]
    recent_wins = sum(1 for r in recent_settled if r["result"] == "win")
    accuracy_30d = round(recent_wins / len(recent_settled) * 100, 1) if recent_settled else None

    recent_list = sorted(settled, key=lambda r: r["date"], reverse=True)[:12]

    return {
        "accuracy_all_time": accuracy,
        "settled_count": len(settled),
        "accuracy_30d": accuracy_30d,
        "settled_30d_count": len(recent_settled),
        "pending_count": sum(1 for r in history if r.get("result") == "pending"),
        "recent": [
            {
                "date": r["date"], "competition": r["competition"],
                "home": r["home"], "away": r["away"],
                "pick_label": r["pick_label"], "result": r["result"],
                "final_score": r.get("final_score"),
            }
            for r in recent_list
        ],
    }
