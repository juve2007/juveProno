"""
dixon_coles_model.py
----------------------
Modèle de Dixon-Coles — une version plus fine du modèle de Poisson simple.

Référence : Dixon, M.J. and Coles, S.G. (1997), "Modelling Association
Football Scores and Inefficiencies in the Football Betting Market".

Trois améliorations par rapport au Poisson simple (poisson_model.py) :

1. Correction de corrélation sur les scores faibles (0-0, 1-0, 0-1, 1-1) :
   un Poisson indépendant naïf se trompe légèrement sur ces scores
   précis. Le paramètre "rho" (appris automatiquement sur tes données)
   corrige ce biais.

2. Pondération temporelle : un match d'il y a 3 mois compte moins
   qu'un match de la semaine dernière, pour refléter la forme actuelle
   des équipes plutôt que la moyenne de route la saison.

3. Régularisation : évite les valeurs extrêmes (ex : "0 but attendu"
   -> "100% match nul") quand une équipe a très peu de matchs joués,
   en la ramenant vers la moyenne de la ligue tant que les données ne
   prouvent pas le contraire.

Les paramètres (force offensive/défensive de chaque équipe, avantage du
terrain, corrélation) sont estimés par maximum de vraisemblance avec
scipy.optimize — ce n'est pas une formule à calibrer à la main, tout
est ré-appris à chaque exécution à partir des résultats fournis.
"""

import math
from datetime import date, datetime

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from data_loader import Match

HALF_LIFE_DAYS = 200   # un match d'il y a 200 jours pèse deux fois moins qu'un match d'aujourd'hui
REG_LAMBDA = 0.03      # force de régularisation (plus haut = plus prudent avec peu de données)


def _parse_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str[:10])
    except (ValueError, TypeError):
        pass
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    return date(2000, 1, 1)  # date inconnue -> traitée comme très ancienne (poids ~0)


class DixonColesModel:
    def __init__(self, max_goals: int = 8):
        self.max_goals = max_goals
        self.attack: dict[str, float] = {}
        self.defense: dict[str, float] = {}
        self.home_adv: float = 0.0
        self.rho: float = 0.0

    def fit(self, matches: list[Match]) -> None:
        if not matches:
            raise ValueError("Aucun match fourni pour entraîner le modèle.")

        teams = sorted({m.home_team for m in matches} | {m.away_team for m in matches})
        team_idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)

        dates = [_parse_date(m.date) for m in matches]
        most_recent = max(dates)
        xi = math.log(2) / HALF_LIFE_DAYS
        weights = np.array([math.exp(-xi * (most_recent - d).days) for d in dates])

        home_i = np.array([team_idx[m.home_team] for m in matches])
        away_i = np.array([team_idx[m.away_team] for m in matches])
        home_g = np.array([m.home_goals for m in matches])
        away_g = np.array([m.away_goals for m in matches])

        def unpack(params):
            attack = np.zeros(n)
            attack[1:] = params[: n - 1]  # attack[0] fixé à 0 (équipe de référence)
            defense = params[n - 1: 2 * n - 1]
            home_adv = params[2 * n - 1]
            rho = params[2 * n]
            return attack, defense, home_adv, rho

        def neg_log_likelihood(params):
            attack, defense, home_adv, rho = unpack(params)
            lam = np.exp(attack[home_i] + defense[away_i] + home_adv)
            mu = np.exp(attack[away_i] + defense[home_i])

            ll = poisson.logpmf(home_g, lam) + poisson.logpmf(away_g, mu)

            tau = np.ones_like(lam)
            m00 = (home_g == 0) & (away_g == 0)
            m01 = (home_g == 0) & (away_g == 1)
            m10 = (home_g == 1) & (away_g == 0)
            m11 = (home_g == 1) & (away_g == 1)
            tau[m00] = 1 - lam[m00] * mu[m00] * rho
            tau[m01] = 1 + lam[m01] * rho
            tau[m10] = 1 + mu[m10] * rho
            tau[m11] = 1 - rho
            tau = np.clip(tau, 1e-6, None)

            reg = REG_LAMBDA * (np.sum(attack ** 2) + np.sum(defense ** 2))
            return -np.sum(weights * (ll + np.log(tau))) + reg

        x0 = np.zeros(2 * n + 1)
        x0[2 * n - 1] = 0.2  # home_adv, valeur de départ raisonnable
        bounds = [(-3, 3)] * (2 * n - 1) + [(-1, 2), (-0.3, 0.3)]

        result = minimize(neg_log_likelihood, x0, method="L-BFGS-B", bounds=bounds)
        attack, defense, home_adv, rho = unpack(result.x)

        self.attack = {t: float(attack[i]) for t, i in team_idx.items()}
        self.defense = {t: float(defense[i]) for t, i in team_idx.items()}
        self.home_adv = float(home_adv)
        self.rho = float(rho)

    def _lambdas(self, home_team: str, away_team: str) -> tuple[float, float]:
        if home_team not in self.attack or away_team not in self.attack:
            missing = [t for t in (home_team, away_team) if t not in self.attack]
            raise ValueError(f"Équipe(s) inconnue(s) dans les données : {missing}")
        lam = math.exp(self.attack[home_team] + self.defense[away_team] + self.home_adv)
        mu = math.exp(self.attack[away_team] + self.defense[home_team])
        return lam, mu

    def _tau(self, x: int, y: int, lam: float, mu: float) -> float:
        if x == 0 and y == 0:
            return 1 - lam * mu * self.rho
        if x == 0 and y == 1:
            return 1 + lam * self.rho
        if x == 1 and y == 0:
            return 1 + mu * self.rho
        if x == 1 and y == 1:
            return 1 - self.rho
        return 1.0

    def predict(self, home_team: str, away_team: str) -> dict:
        lam, mu = self._lambdas(home_team, away_team)
        n = self.max_goals + 1

        matrix = [
            [poisson.pmf(i, lam) * poisson.pmf(j, mu) * self._tau(i, j, lam, mu) for j in range(n)]
            for i in range(n)
        ]
        total = sum(sum(row) for row in matrix)
        matrix = [[v / total for v in row] for row in matrix]

        p_home_win = sum(matrix[i][j] for i in range(n) for j in range(n) if i > j)
        p_draw = sum(matrix[i][i] for i in range(n))
        p_away_win = sum(matrix[i][j] for i in range(n) for j in range(n) if i < j)
        p_over_2_5 = sum(matrix[i][j] for i in range(n) for j in range(n) if i + j > 2)
        p_btts = sum(matrix[i][j] for i in range(n) for j in range(n) if i > 0 and j > 0)

        top_scores = sorted(
            ((f"{i}-{j}", matrix[i][j]) for i in range(n) for j in range(n)),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "home_team": home_team,
            "away_team": away_team,
            "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
            "1x2": {
                "home_win": round(p_home_win * 100, 1),
                "draw": round(p_draw * 100, 1),
                "away_win": round(p_away_win * 100, 1),
            },
            "over_2_5_goals": round(p_over_2_5 * 100, 1),
            "both_teams_to_score": round(p_btts * 100, 1),
            "top_scores": [(s, round(p * 100, 1)) for s, p in top_scores],
        }
