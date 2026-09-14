"""
poisson_model.py
------------------
Modèle de prédiction de matchs de football basé sur la loi de Poisson.

Principe (méthode standard en analytique sportive, utilisée par des
plateformes comme FiveThirtyEight ou Opta) :

1. On calcule, à partir des résultats déjà joués, la force d'attaque et
   de défense de chaque équipe, à domicile et à l'extérieur, par rapport
   à la moyenne de la ligue.
2. Pour un match A (dom.) vs B (ext.), on estime le nombre de buts
   "attendus" (lambda) pour chaque équipe :
       lambda_A = attaque_dom(A) x défense_ext(B) x moyenne_buts_dom_ligue
       lambda_B = attaque_ext(B) x défense_dom(A) x moyenne_buts_ext_ligue
3. On modélise le nombre de buts de chaque équipe comme une variable de
   Poisson(lambda), on construit la matrice de probabilité de tous les
   scores possibles, puis on en déduit :
   - probabilité victoire / nul / défaite
   - scores exacts les plus probables
   - probabilité +2.5 buts, probabilité "les deux équipes marquent"

Limites à connaître (à dire honnêtement aux utilisateurs de l'outil) :
- Ce modèle ignore les blessures, suspensions, enjeu du match, forme
  récente pondérée dans le temps, etc. C'est un modèle de base solide,
  pas une boule de cristal. Il donne des PROBABILITÉS, jamais une
  certitude.
- Il lui faut un minimum de matchs par équipe (10+) pour être fiable.
"""

from collections import defaultdict
from dataclasses import dataclass
from scipy.stats import poisson

from data_loader import Match


@dataclass
class TeamStrength:
    home_attack: float
    home_defense: float
    away_attack: float
    away_defense: float


class PoissonModel:
    def __init__(self, max_goals: int = 8):
        self.max_goals = max_goals
        self.strengths: dict[str, TeamStrength] = {}
        self.avg_home_goals = 1.4
        self.avg_away_goals = 1.1

    def fit(self, matches: list[Match]) -> None:
        if not matches:
            raise ValueError("Aucun match fourni pour entraîner le modèle.")

        n = len(matches)
        self.avg_home_goals = sum(m.home_goals for m in matches) / n
        self.avg_away_goals = sum(m.away_goals for m in matches) / n

        goals_for_home = defaultdict(list)
        goals_against_home = defaultdict(list)
        goals_for_away = defaultdict(list)
        goals_against_away = defaultdict(list)

        for m in matches:
            goals_for_home[m.home_team].append(m.home_goals)
            goals_against_home[m.home_team].append(m.away_goals)
            goals_for_away[m.away_team].append(m.away_goals)
            goals_against_away[m.away_team].append(m.home_goals)

        teams = set(goals_for_home) | set(goals_for_away)

        # Lissage : une équipe avec très peu de matchs joués (ou 0 but marqué
        # sur un petit échantillon) est ramenée vers la moyenne de la ligue au
        # lieu de produire des valeurs extrêmes (ex: 0 but attendu -> 100% nul).
        # K = poids de cette moyenne, exprimé en "matchs virtuels".
        K_SMOOTHING = 3

        for team in teams:
            hf = goals_for_home.get(team, [])
            ha = goals_against_home.get(team, [])
            af = goals_for_away.get(team, [])
            aa = goals_against_away.get(team, [])

            def smoothed_ratio(values, league_avg):
                rate = (sum(values) + K_SMOOTHING * league_avg) / (len(values) + K_SMOOTHING)
                return rate / league_avg

            home_attack = smoothed_ratio(hf, self.avg_home_goals)
            home_defense = smoothed_ratio(ha, self.avg_away_goals)
            away_attack = smoothed_ratio(af, self.avg_away_goals)
            away_defense = smoothed_ratio(aa, self.avg_home_goals)

            self.strengths[team] = TeamStrength(
                home_attack=home_attack,
                home_defense=home_defense,
                away_attack=away_attack,
                away_defense=away_defense,
            )

    def _lambdas(self, home_team: str, away_team: str) -> tuple[float, float]:
        if home_team not in self.strengths or away_team not in self.strengths:
            missing = [t for t in (home_team, away_team) if t not in self.strengths]
            raise ValueError(f"Équipe(s) inconnue(s) dans les données : {missing}")

        h = self.strengths[home_team]
        a = self.strengths[away_team]

        lambda_home = h.home_attack * a.away_defense * self.avg_home_goals
        lambda_away = a.away_attack * h.home_defense * self.avg_away_goals
        return lambda_home, lambda_away

    def predict(self, home_team: str, away_team: str) -> dict:
        lambda_home, lambda_away = self._lambdas(home_team, away_team)

        n = self.max_goals + 1
        home_probs = [poisson.pmf(i, lambda_home) for i in range(n)]
        away_probs = [poisson.pmf(j, lambda_away) for j in range(n)]

        score_matrix = [[home_probs[i] * away_probs[j] for j in range(n)] for i in range(n)]

        p_home_win = sum(
            score_matrix[i][j] for i in range(n) for j in range(n) if i > j
        )
        p_draw = sum(score_matrix[i][i] for i in range(n))
        p_away_win = sum(
            score_matrix[i][j] for i in range(n) for j in range(n) if i < j
        )

        p_over_2_5 = sum(
            score_matrix[i][j] for i in range(n) for j in range(n) if i + j > 2
        )
        p_btts = sum(
            score_matrix[i][j] for i in range(n) for j in range(n) if i > 0 and j > 0
        )

        top_scores = sorted(
            (
                (f"{i}-{j}", score_matrix[i][j])
                for i in range(n)
                for j in range(n)
            ),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "home_team": home_team,
            "away_team": away_team,
            "expected_goals": {"home": round(lambda_home, 2), "away": round(lambda_away, 2)},
            "1x2": {
                "home_win": round(p_home_win * 100, 1),
                "draw": round(p_draw * 100, 1),
                "away_win": round(p_away_win * 100, 1),
            },
            "over_2_5_goals": round(p_over_2_5 * 100, 1),
            "both_teams_to_score": round(p_btts * 100, 1),
            "top_scores": [(score, round(p * 100, 1)) for score, p in top_scores],
        }
