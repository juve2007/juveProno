"""
odds_client.py
----------------
Récupère les vraies cotes du marché (via The Odds API) et calcule
l'écart ("edge") entre la probabilité du modèle et la probabilité
implicite du marché, une fois la marge du bookmaker retirée.

Inscription gratuite : https://the-odds-api.com (500 crédits/mois).
Un appel avec 1 marché ("h2h" = victoire/nul/défaite) et 1 région
("eu") coûte 1 crédit -> largement suffisant pour un usage quotidien
(10 compétitions/jour = ~300 crédits/mois).

Principe du "edge" :
- Le marché donne des cotes, ex: 1.80 / 3.60 / 4.50
- On les convertit en probabilités implicites (1 / cote), qui somment
  à un peu plus de 100% à cause de la marge du bookmaker (l'"overround")
- On retire cette marge en normalisant (chaque proba / somme des probas)
  -> ça donne la vraie estimation du marché, marge exclue
- edge = probabilité du modèle - probabilité du marché (normalisée)
  Un edge positif veut dire que le modèle pense que c'est plus probable
  que ce que le marché price -> c'est ça, un "value bet" potentiel.
"""

import difflib
import requests

ODDS_API_SPORT_KEYS = {
    "FL1": "soccer_france_ligue_one",
    "PD": "soccer_spain_la_liga",
    "PL": "soccer_epl",
    "BL1": "soccer_germany_bundesliga",
    "SA": "soccer_italy_serie_a",
    "CL": "soccer_uefa_champs_league",
    "DED": "soccer_netherlands_eredivisie",
    "PPL": "soccer_portugal_primeira_liga",
    "ELC": "soccer_efl_champ",
    "BSA": "soccer_brazil_campeonato",
}

EDGE_THRESHOLD = 5.0  # points de pourcentage minimum pour être affiché comme "value"


def fetch_odds(api_key: str, competition_code: str) -> list[dict]:
    sport_key = ODDS_API_SPORT_KEYS.get(competition_code)
    if not sport_key or not api_key:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": api_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            print(f"   cotes indisponibles pour {competition_code} (code {response.status_code}), on continue sans.")
            return []
        return response.json()
    except requests.RequestException:
        print(f"   erreur réseau sur les cotes pour {competition_code}, on continue sans.")
        return []


def _normalize(name: str) -> str:
    n = name
    for junk in (" FC", " CF", " AC", " AS", " SC", " 1901", " 29", " Alsace"):
        n = n.replace(junk, "")
    return n.strip().lower()


def _best_match(target: str, candidates: list[str]) -> str | None:
    target_n = _normalize(target)
    best, best_score = None, 0.0
    for c in candidates:
        score = difflib.SequenceMatcher(None, target_n, _normalize(c)).ratio()
        if score > best_score:
            best, best_score = c, score
    return best if best_score >= 0.55 else None


def attach_value_bets(dashboard_matches: list[dict], odds_events: list[dict]) -> int:
    """Enrichit chaque match avec les cotes du marché et l'edge, quand une
    correspondance fiable est trouvée. Retourne le nombre de matchs enrichis."""
    if not odds_events:
        return 0

    home_names = [ev.get("home_team", "") for ev in odds_events]
    attached = 0

    for m in dashboard_matches:
        matched_name = _best_match(m["home"], home_names)
        if not matched_name:
            continue
        event = next((ev for ev in odds_events if ev.get("home_team") == matched_name), None)
        if not event:
            continue

        prices = {"home": [], "draw": [], "away": []}
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    price, name = outcome.get("price"), outcome.get("name", "")
                    if name == event.get("home_team"):
                        prices["home"].append(price)
                    elif name == event.get("away_team"):
                        prices["away"].append(price)
                    elif name.lower() == "draw":
                        prices["draw"].append(price)

        if not (prices["home"] and prices["draw"] and prices["away"]):
            continue

        avg = {k: sum(v) / len(v) for k, v in prices.items()}
        implied = {k: 1 / v for k, v in avg.items()}
        overround = sum(implied.values())
        normalized = {k: (v / overround) * 100 for k, v in implied.items()}

        m["market_odds"] = {k: round(v, 2) for k, v in avg.items()}
        m["market_prob"] = {k: round(v, 1) for k, v in normalized.items()}
        m["edge"] = {
            "home": round(m["p_home"] - normalized["home"], 1),
            "draw": round(m["p_draw"] - normalized["draw"], 1),
            "away": round(m["p_away"] - normalized["away"], 1),
        }
        attached += 1

    return attached


def best_value_bets(dashboard_matches: list[dict], threshold: float = EDGE_THRESHOLD) -> list[dict]:
    """Liste triée des paris où le modèle voit un vrai écart face au marché."""
    values = []
    labels = {"home": "{home} gagne", "draw": "Match nul", "away": "{away} gagne"}
    for m in dashboard_matches:
        edge = m.get("edge")
        if not edge:
            continue
        outcome, value = max(edge.items(), key=lambda kv: kv[1])
        if value < threshold:
            continue
        values.append({
            "competition": m["competition"], "date": m["date"],
            "home": m["home"], "away": m["away"],
            "home_crest": m.get("home_crest", ""), "away_crest": m.get("away_crest", ""),
            "outcome_label": labels[outcome].format(home=m["home"], away=m["away"]),
            "model_prob": m["p_home"] if outcome == "home" else m["p_draw"] if outcome == "draw" else m["p_away"],
            "market_prob": m["market_prob"][outcome],
            "market_odds": m["market_odds"][outcome],
            "edge": value,
        })
    values.sort(key=lambda v: v["edge"], reverse=True)
    return values
