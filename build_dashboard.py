"""
build_dashboard.py
--------------------
Génère automatiquement le fichier dashboard.html avec :
- les vrais matchs à venir (annoncés) de chaque compétition
- les prédictions du modèle de Poisson, calibrées sur les résultats
  déjà joués cette saison

Usage :
    python3 build_dashboard.py TON_TOKEN FL1 PD
    python3 build_dashboard.py TON_TOKEN FL1 PD CL BL1 SA

Codes disponibles (tier gratuit football-data.org) :
    FL1 = Ligue 1, PD = La Liga, CL = Champions League,
    PL = Premier League, BL1 = Bundesliga, SA = Serie A,
    DED = Eredivisie, PPL = Primeira Liga, ELC = Championship,
    BSA = Brasileirão

Résultat : dashboard.html, un fichier autonome à ouvrir dans un
navigateur (double-clic), ou à héberger tel quel comme site.

Relance cette commande chaque jour pour rafraîchir les matchs annoncés
et les pronostics.
"""

import sys
import os
import re
import json
import time
import webbrowser
import requests

from data_loader import Match
from dixon_coles_model import DixonColesModel
import track_record
import odds_client

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
COMPETITIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "competitions.json")


def load_config() -> tuple[str, list[str]]:
    # Compétitions : fichier public (competitions.json) en priorité, sinon config.json local
    competitions = []
    if os.path.exists(COMPETITIONS_PATH):
        with open(COMPETITIONS_PATH, "r", encoding="utf-8") as f:
            competitions = json.load(f).get("competitions", [])
    elif os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            competitions = json.load(f).get("competitions", [])

    # Token football-data.org : variable d'environnement en priorité (GitHub Actions),
    # sinon config.json local -> ne doit JAMAIS se trouver dans un fichier publié sur GitHub.
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "")
    odds_token = os.environ.get("ODDS_API_TOKEN", "")
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not token:
            token = cfg.get("token", "")
        if not odds_token:
            odds_token = cfg.get("odds_api_token", "")

    if not token or token == "TON_TOKEN":
        raise SystemExit(
            "Token manquant. En local : mets-le dans config.json. "
            "Sur GitHub Actions : ajoute le secret FOOTBALL_DATA_TOKEN."
        )
    if not competitions:
        raise SystemExit("Ajoute au moins une compétition dans competitions.json ou config.json.")
    return token, odds_token, competitions

COMPETITION_NAMES = {
    "FL1": "Ligue 1",
    "PD": "La Liga",
    "CL": "Ligue des Champions",
    "PL": "Premier League",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "ELC": "Championship",
    "BSA": "Brasileirão",
}

MAX_UPCOMING_PER_COMPETITION = 6


def api_get(token: str, competition_code: str) -> list[dict]:
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches"
    headers = {"X-Auth-Token": token}
    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 403:
        print(f"   pas d'accès à {competition_code} avec ce token (compétition hors tier gratuit ?), on saute.")
        return []
    if response.status_code == 429:
        print("   limite de requêtes atteinte, pause de 60s...")
        time.sleep(60)
        return api_get(token, competition_code)
    response.raise_for_status()
    return response.json().get("matches", [])


def to_finished_matches(api_matches: list[dict]) -> list[Match]:
    matches = []
    for m in api_matches:
        score = m.get("score", {}).get("fullTime", {})
        hg, ag = score.get("home"), score.get("away")
        if hg is None or ag is None:
            continue
        matches.append(
            Match(
                date=m.get("utcDate", "")[:10],
                home_team=m.get("homeTeam", {}).get("name", ""),
                away_team=m.get("awayTeam", {}).get("name", ""),
                home_goals=hg,
                away_goals=ag,
            )
        )
    return matches


def predict_dashboard_matches(token: str, competition_codes: list[str], finished_lookup: dict) -> list[dict]:
    dashboard_matches = []
    today_iso = __import__("datetime").date.today().isoformat()

    for i, code in enumerate(competition_codes):
        label = COMPETITION_NAMES.get(code, code)
        print(f"-> {label} : récupération des matchs...")

        if i > 0:
            time.sleep(1.2)  # rester bien sous la limite de requêtes/minute

        all_raw = api_get(token, code)
        if not all_raw:
            continue

        # alimente le carnet de résultats finaux (sert à régler l'historique de fiabilité)
        for m in all_raw:
            score = m.get("score", {}).get("fullTime", {})
            hg, ag = score.get("home"), score.get("away")
            if hg is not None and ag is not None and m.get("id") is not None:
                finished_lookup[m["id"]] = (hg, ag)

        finished = to_finished_matches(all_raw)
        upcoming_raw = [
            m for m in all_raw
            if m.get("score", {}).get("fullTime", {}).get("home") is None
            and m.get("utcDate", "")[:10] >= today_iso
        ]
        upcoming_raw.sort(key=lambda m: m.get("utcDate", ""))
        print(f"   {len(all_raw)} matchs au total : {len(finished)} joués, {len(upcoming_raw)} à venir.")

        if len(finished) < 10:
            print(f"   attention : peu de matchs joués, le modèle sera peu fiable pour {label}.")
        if not finished or not upcoming_raw:
            continue

        model = DixonColesModel()
        model.fit(finished)
        print(f"   modèle entraîné (avantage terrain: {model.home_adv:+.2f}, corrélation: {model.rho:+.2f})")

        added = 0
        for m in upcoming_raw:
            if added >= MAX_UPCOMING_PER_COMPETITION:
                break
            home = m.get("homeTeam", {}).get("name", "")
            away = m.get("awayTeam", {}).get("name", "")
            try:
                pred = model.predict(home, away)
            except ValueError:
                continue  # équipe inconnue (pas assez de matchs joués) -> on saute

            dashboard_matches.append({
                "match_id": m.get("id"),
                "competition": label,
                "competition_code": code,
                "date": m.get("utcDate", "")[:10],
                "home": home,
                "away": away,
                "home_crest": m.get("homeTeam", {}).get("crest", ""),
                "away_crest": m.get("awayTeam", {}).get("crest", ""),
                "xg_home": pred["expected_goals"]["home"],
                "xg_away": pred["expected_goals"]["away"],
                "p_home": pred["1x2"]["home_win"],
                "p_draw": pred["1x2"]["draw"],
                "p_away": pred["1x2"]["away_win"],
                "over25": pred["over_2_5_goals"],
                "btts": pred["both_teams_to_score"],
                "top_score": pred["top_scores"][0][0],
                "top_score_prob": pred["top_scores"][0][1],
            })
            added += 1

        print(f"   {added} match(s) avec pronostic ajouté(s) pour {label}.")

    dashboard_matches.sort(key=lambda m: m["date"])
    return dashboard_matches


def inject_into_template(payload: dict, template_path: str, out_path: str) -> None:
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    payload_json = json.dumps(payload, ensure_ascii=False)

    new_html, count = re.subn(
        r"const DATA = /\*__PREDICTIONS_JSON__\*/.*?;\n",
        f"const DATA = {payload_json};\n",
        html,
        count=1,
        flags=re.DOTALL,
    )
    if count == 0:
        raise SystemExit("Marqueur __PREDICTIONS_JSON__ introuvable dans le template.")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new_html)


def main():
    if len(sys.argv) >= 3:
        token = sys.argv[1]
        odds_token = ""
        codes = sys.argv[2:]
    else:
        token, odds_token, codes = load_config()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    history_path = os.path.join(base_dir, "history.json")

    finished_lookup = {}
    matches = predict_dashboard_matches(token, codes, finished_lookup)
    if not matches:
        raise SystemExit("Aucun match à venir trouvé (saison peut-être entre deux journées).")

    # --- Historique de fiabilité ---
    history = track_record.load_history(history_path)
    n_settled = track_record.settle_pending(history, finished_lookup)
    if n_settled:
        print(f"\n📊 {n_settled} ancien(s) pronostic(s) réglé(s) avec les vrais résultats.")
    todays_picks = track_record.compute_top_picks(matches, n=5)
    n_added = track_record.add_todays_picks(history, todays_picks)
    track_record.save_history(history_path, history)
    tr_summary = track_record.summarize(history)
    if tr_summary["accuracy_all_time"] is not None:
        print(f"   fiabilité globale : {tr_summary['accuracy_all_time']}% sur {tr_summary['settled_count']} pronostics réglés")

    # --- Value betting (optionnel, seulement si un token de cotes est configuré) ---
    value_bets = []
    if odds_token and odds_token != "TON_TOKEN_ODDS_API":
        print("\n💰 Récupération des cotes du marché...")
        by_code = {}
        for m in matches:
            by_code.setdefault(m["competition_code"], []).append(m)
        for i, (code, ms) in enumerate(by_code.items()):
            if i > 0:
                time.sleep(1.2)
            events = odds_client.fetch_odds(odds_token, code)
            n = odds_client.attach_value_bets(ms, events)
            print(f"   {COMPETITION_NAMES.get(code, code)} : cotes trouvées pour {n}/{len(ms)} match(s)")
        value_bets = odds_client.best_value_bets(matches)
        print(f"   {len(value_bets)} value bet(s) détecté(s) (écart >= {odds_client.EDGE_THRESHOLD} points)")
    else:
        print("\n💰 Value betting désactivé (pas de odds_api_token configuré).")

    template_path = os.path.join(base_dir, "dashboard_template.html")
    out_path = os.path.join(base_dir, "dashboard.html")

    payload = {
        "generated_at": __import__("datetime").date.today().isoformat(),
        "matches": matches,
        "track_record": tr_summary,
        "value_bets": value_bets,
    }
    inject_into_template(payload, template_path, out_path)
    print(f"\n✅ dashboard.html généré avec {len(matches)} matchs.")

    if not os.environ.get("CI"):
        webbrowser.open("file://" + out_path)
        print("-> Ouverture du dashboard dans ton navigateur...")


if __name__ == "__main__":
    main()
