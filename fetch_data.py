"""
fetch_data.py
---------------
Récupère les vrais résultats de matchs depuis l'API football-data.org
et les enregistre au format attendu par data_loader.py.

Étape 1 : crée un compte gratuit ici -> https://www.football-data.org/client/register
Étape 2 : récupère ton token (une chaîne de caractères) sur ton tableau de bord
Étape 3 : lance :
    python3 fetch_data.py TON_TOKEN FL1 sample_data/ligue1_reel.csv
    python3 fetch_data.py TON_TOKEN PD  sample_data/laliga_reel.csv
    python3 fetch_data.py TON_TOKEN CL  sample_data/champions_league_reel.csv

Codes de compétition (tier gratuit) :
    PL  = Premier League (Angleterre)
    PD  = La Liga (Espagne)
    FL1 = Ligue 1 (France)
    BL1 = Bundesliga (Allemagne)
    SA  = Serie A (Italie)
    CL  = UEFA Champions League

Limite du tier gratuit : 10 appels/minute, saison en cours uniquement.
Largement suffisant pour calibrer le modèle.
"""

import sys
import csv
import requests


def fetch_matches(token: str, competition_code: str) -> list[dict]:
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches"
    headers = {"X-Auth-Token": token}
    params = {"status": "FINISHED"}  # seulement les matchs déjà joués

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code == 403:
        raise SystemExit(
            "Erreur 403 : ton token n'a pas accès à cette compétition, ou "
            "le token est invalide. Vérifie sur ton tableau de bord football-data.org."
        )
    if response.status_code == 429:
        raise SystemExit("Trop de requêtes (limite 10/min). Attends une minute et relance.")
    response.raise_for_status()

    return response.json().get("matches", [])


def save_as_csv(matches: list[dict], out_path: str) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
        count = 0
        for m in matches:
            score = m.get("score", {}).get("fullTime", {})
            hg, ag = score.get("home"), score.get("away")
            if hg is None or ag is None:
                continue  # match sans score final -> on saute
            date = m.get("utcDate", "")[:10]
            home = m.get("homeTeam", {}).get("name", "")
            away = m.get("awayTeam", {}).get("name", "")
            writer.writerow([date, home, away, hg, ag])
            count += 1
    print(f"-> {count} matchs écrits dans {out_path}")


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    token, competition_code, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    matches = fetch_matches(token, competition_code)
    save_as_csv(matches, out_path)


if __name__ == "__main__":
    main()
