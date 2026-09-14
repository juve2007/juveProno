"""
predict.py
-----------
Usage :
    python3 predict.py <fichier_csv> "<Equipe domicile>" "<Equipe exterieur>"

Exemple :
    python3 predict.py sample_data/demo_matches.csv "Paris SG" "Lyon"
"""

import sys
from data_loader import load_matches_from_csv, teams_in
from dixon_coles_model import DixonColesModel


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    csv_path, home_team, away_team = sys.argv[1], sys.argv[2], sys.argv[3]

    matches = load_matches_from_csv(csv_path)
    print(f"-> {len(matches)} matchs chargés depuis {csv_path}")

    model = DixonColesModel()
    model.fit(matches)

    available = teams_in(matches)
    for t in (home_team, away_team):
        if t not in available:
            print(f"\n⚠️  '{t}' n'est pas dans les données. Équipes disponibles :")
            print(", ".join(sorted(available)))
            sys.exit(1)

    result = model.predict(home_team, away_team)

    print(f"\n=== {result['home_team']} vs {result['away_team']} ===")
    print(f"Buts attendus : {result['home_team']} {result['expected_goals']['home']} "
          f"- {result['expected_goals']['away']} {result['away_team']}")
    print(f"\nProbabilités 1X2 :")
    print(f"  Victoire {result['home_team']:<15} {result['1x2']['home_win']}%")
    print(f"  Match nul{'':<16} {result['1x2']['draw']}%")
    print(f"  Victoire {result['away_team']:<15} {result['1x2']['away_win']}%")
    print(f"\n+2.5 buts       : {result['over_2_5_goals']}%")
    print(f"Les 2 marquent  : {result['both_teams_to_score']}%")
    print(f"\nScores les plus probables :")
    for score, prob in result["top_scores"]:
        print(f"  {score:<6} {prob}%")


if __name__ == "__main__":
    main()
