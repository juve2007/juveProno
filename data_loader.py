"""
data_loader.py
----------------
Charge des résultats de matchs de football depuis un fichier CSV.

Format attendu (c'est le format standard du site football-data.co.uk,
utilisé pour la Ligue 1, la Liga, la Premier League, etc.) :

    Date,HomeTeam,AwayTeam,FTHG,FTAG
    2025-08-15,Paris SG,Nantes,3,0
    2025-08-16,Marseille,Lyon,1,1
    ...

- FTHG = Full Time Home Goals (buts de l'équipe à domicile)
- FTAG = Full Time Away Goals (buts de l'équipe à l'extérieur)

Le loader ignore les colonnes en trop (cotes de paris, cartons, corners...)
si elles sont présentes : il ne garde que ce dont le modèle a besoin.
"""

from dataclasses import dataclass
import pandas as pd


@dataclass
class Match:
    date: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int


def load_matches_from_csv(path: str) -> list[Match]:
    """Charge une liste de Match à partir d'un CSV façon football-data.co.uk."""
    df = pd.read_csv(path)

    # Tolère quelques variantes de noms de colonnes
    col_map = {c.lower(): c for c in df.columns}
    date_col = col_map.get("date", "Date")
    home_col = col_map.get("hometeam", "HomeTeam")
    away_col = col_map.get("awayteam", "AwayTeam")
    hg_col = col_map.get("fthg", "FTHG")
    ag_col = col_map.get("ftag", "FTAG")

    matches = []
    for _, row in df.iterrows():
        try:
            matches.append(
                Match(
                    date=str(row[date_col]),
                    home_team=str(row[home_col]).strip(),
                    away_team=str(row[away_col]).strip(),
                    home_goals=int(row[hg_col]),
                    away_goals=int(row[ag_col]),
                )
            )
        except (ValueError, KeyError):
            # ligne incomplète (ex: match pas encore joué) -> on saute
            continue
    return matches


def teams_in(matches: list[Match]) -> set[str]:
    """Retourne l'ensemble des équipes présentes dans les données."""
    teams = set()
    for m in matches:
        teams.add(m.home_team)
        teams.add(m.away_team)
    return teams
