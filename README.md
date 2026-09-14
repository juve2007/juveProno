# Prédicteur de matchs de football (Ligue 1 / La Liga)

## 📊 Historique de fiabilité

Chaque jour, les 5 pronostics de la "Sélection du jour" sont enregistrés
automatiquement dans `history.json`. Quand le match est joué, le robot
vérifie tout seul si le pronostic avait raison, et le dashboard affiche
un vrai taux de réussite (global + 30 derniers jours) avec l'historique
récent (✓/✗). Rien à configurer — ça fonctionne dès la première
exécution, et devient utile après quelques jours de données.

⚠️ `history.json` doit être commité sur GitHub (contrairement à
`config.json`) pour que l'historique survive d'un jour à l'autre.

## 💰 Value betting

Compare les probabilités du modèle aux vraies cotes du marché (une
fois la marge du bookmaker retirée) pour repérer les matchs où le
modèle voit un vrai écart — pas juste les picks les plus confiants.

1. Crée un compte gratuit sur https://the-odds-api.com (500 crédits/mois)
2. Ajoute ton token dans `config.json` (`"odds_api_token"`) en local,
   ou comme secret GitHub `ODDS_API_TOKEN` pour la version en ligne
3. C'est tout — la section "Value bets du jour" apparaît automatiquement
   dès qu'un écart significatif (5 points ou plus) est détecté

Sans ce token, le reste du dashboard fonctionne normalement, cette
section affiche juste un message "non configuré".

## 🌐 Mise en ligne (GitHub Pages + robot dans le cloud)

Une fois fait, le robot tourne **tout seul chaque jour sur les serveurs
de GitHub** — plus besoin de ton PC allumé ni de double-cliquer sur
rien. Le site est en ligne en permanence, à une vraie adresse.

⚠️ Le dépôt doit être **public** pour l'hébergement gratuit — mais ton
token API ne sera jamais visible : `config.json` est exclu par
`.gitignore`, et sur GitHub le token passe par un secret chiffré.

**Étapes (à faire une seule fois)** — voir le détail plus bas dans la
conversation, en résumé :
1. Crée un compte GitHub (gratuit) et un nouveau dépôt **public**
2. Pousse ce dossier dedans avec git
3. Ajoute ton token comme secret du dépôt : `FOOTBALL_DATA_TOKEN`
4. Active GitHub Pages (Settings → Pages → branche `main`)
5. Le site est en ligne à `https://TON_PSEUDO.github.io/TON_DEPOT/dashboard.html`

Le fichier `.github/workflows/daily.yml` fait tourner le robot chaque
jour à 6h UTC automatiquement (modifiable), et aussi à la demande
depuis l'onglet "Actions" de GitHub (bouton "Run workflow").

---

## 📱 Installer comme une application sur ton téléphone

Le dashboard est maintenant une vraie "web app" installable (PWA) :
icône sur l'écran d'accueil, plein écran, fonctionne hors-ligne.

**Dès maintenant, sans rien héberger :**
1. Transfère tout le dossier `foot_predictor` sur ton téléphone (par mail,
   WhatsApp, câble USB, Google Drive...) — au minimum `dashboard.html`,
   `manifest.json`, `sw.js` et le dossier `icons/` doivent rester ensemble,
   dans le même dossier.
2. Ouvre `dashboard.html` avec **Chrome** sur le téléphone.
3. Menu Chrome (⋮) → **"Ajouter à l'écran d'accueil"**.

Tu auras une icône JuveProno sur ton téléphone. Le plein écran et le
mode hors-ligne complets ne s'activent vraiment qu'une fois le site
hébergé en ligne (voir plus bas) — en local ça reste un très bon raccourci.

**Pour un vrai fichier .apk installable**, une fois le site hébergé
en ligne (étape "mise en ligne réelle" qu'on peut faire ensemble) :
1. Va sur https://www.pwabuilder.com
2. Colle l'URL de ton site
3. Clique "Package for stores" → Android → télécharge le `.apk`

Aucun outil Android à installer de ton côté, tout se fait sur leur site.

## Modèle de prédiction : Dixon-Coles

Le moteur de pronostic utilise le modèle de **Dixon-Coles** (référence
académique de 1997, toujours utilisée aujourd'hui) plutôt qu'un simple
Poisson indépendant :

- corrige un biais connu sur les scores serrés (0-0, 1-0, 0-1, 1-1)
- pondère les matchs récents plus fort que les matchs du début de saison
- évite les prédictions extrêmes (ex: "0 but attendu") quand une équipe
  a très peu de matchs joués, en la ramenant vers la moyenne de la
  ligue tant que les données ne prouvent pas le contraire

Tout est ré-appris automatiquement à chaque exécution à partir des
résultats récupérés — rien à calibrer à la main. Le code est dans
`dixon_coles_model.py`.

## 🤖 Utilisation quotidienne (une fois configuré)

Double-clique sur **`lancer_robot.bat`**. C'est tout.

Ça récupère les matchs à venir, calcule les pronostics, régénère le
dashboard, et l'ouvre automatiquement dans ton navigateur. Une fenêtre
noire s'affiche pendant quelques secondes (le "robot" qui travaille),
puis se ferme quand tu appuies sur une touche.

Ton token est déjà enregistré dans `config.json` — pas besoin de le
retaper à chaque fois. Le robot couvre déjà toutes les ligues
disponibles gratuitement (Ligue 1, La Liga, Premier League, Bundesliga,
Serie A, Champions League, Eredivisie, Primeira Liga, Championship,
Brasileirão) — comme ça il y a toujours des matchs à afficher, même
les jours creux dans un seul championnat.

Pour activer/désactiver une ligue, modifie la liste `competitions`
dans `config.json` (codes disponibles listés en haut de
`build_dashboard.py`).

---

Outil qui calcule des **probabilités** de résultat pour un match de foot,
à partir des vrais résultats déjà joués dans la saison, avec un modèle
statistique de Poisson (même principe que les outils sérieux type
FiveThirtyEight/Opta).

⚠️ Important à comprendre avant de vendre ça à qui que ce soit : ce n'est
**pas une martingale ni une certitude**. Le modèle donne des probabilités
sérieuses (ex : "62% de victoire à domicile"), pas des résultats garantis.
Sois honnête là-dessus avec tes futurs clients/abonnés — c'est ce qui fait
la différence entre un vrai outil d'analyse et une arnaque.

## Structure du projet

```
foot_predictor/
├── data_loader.py      # charge les résultats depuis un CSV
├── poisson_model.py     # le modèle statistique
├── predict.py            # script pour lancer une prédiction
├── fetch_data.py          # récupère les vrais résultats via l'API football-data.org
├── build_dashboard.py      # génère le tableau de bord visuel (voir plus bas)
├── dashboard_template.html # le template du tableau de bord
├── dashboard_demo.html      # démo à ouvrir directement pour voir le rendu
├── config.json               # ton token + les compétitions (à ne modifier qu'une fois)
├── lancer_robot.bat            # double-clic Windows = tout se met à jour
├── lancer_robot.sh              # équivalent Mac/Linux

## Tableau de bord visuel (le "espace" avec les matchs du jour)

`dashboard_demo.html` est prêt à ouvrir tout de suite (double-clic, ou
glisse-le dans Chrome) — il contient des données de démonstration pour
que tu voies immédiatement le rendu : match phare animé, cartes façon
"ticket de stade" par match, barres de probabilité, badges de club.

Pour générer le vrai tableau de bord avec les vrais matchs annoncés et
leurs pronostics (à relancer chaque jour) :

```bash
python3 build_dashboard.py TON_TOKEN FL1 PD
```

Ça va chercher automatiquement :
- les matchs déjà joués cette saison (pour calibrer le modèle)
- les prochains matchs annoncés de chaque compétition
- calculer une prédiction pour chacun

... et produire `dashboard.html`, un fichier autonome (pas besoin de
serveur) que tu peux ouvrir dans un navigateur ou héberger tel quel
comme page de ton site.

├── sample_data/
│   └── demo_matches.csv  # ⚠️ DONNÉES FICTIVES, juste pour tester le code
└── README.md
```

## Tester tout de suite (avec les fausses données de démo)

```bash
python3 predict.py sample_data/demo_matches.csv "Paris SG" "Lyon"
```

## Brancher les vraies données (Ligue 1, La Liga, Champions League)

On utilise l'API **football-data.org** : gratuite, stable, et son tier
gratuit couvre exactement Ligue 1, La Liga et la Champions League (pas
besoin de changer de source plus tard).

1. Crée un compte gratuit : https://www.football-data.org/client/register
2. Récupère ton token sur ton tableau de bord après inscription
3. Lance (une commande par compétition) :
   ```bash
   python3 fetch_data.py TON_TOKEN FL1 sample_data/ligue1_reel.csv
   python3 fetch_data.py TON_TOKEN PD  sample_data/laliga_reel.csv
   python3 fetch_data.py TON_TOKEN CL  sample_data/champions_league_reel.csv
   ```
4. Utilise le fichier généré avec predict.py :
   ```bash
   python3 predict.py sample_data/ligue1_reel.csv "Paris SG" "Marseille"
   ```

Limite du tier gratuit : 10 requêtes/minute, données de la saison en
cours uniquement — largement suffisant ici.

## Prochaines étapes (dans l'ordre où on peut les faire)

1. ✅ Moteur de prédiction Ligue 1 + La Liga (fait)
2. Champions League : format de données un peu différent (le calendrier
   change de format en phase de groupes/ligue) — on l'ajoutera à part
3. Interface web pour publier les pronostics automatiquement chaque
   semaine (site simple, ou intégré à Chariow comme ton ebook)
4. Système d'abonnement pour vendre l'accès aux pronostics
5. Amélioration du modèle : pondérer les matchs récents plus fort que
   les vieux matchs, ajouter la variante Dixon-Coles (corrige les scores
   très bas type 0-0, 1-0, 1-1)

## Dépendances

```bash
pip install numpy scipy pandas requests --break-system-packages
```
(sur Windows, sans `--break-system-packages` : juste `pip install numpy scipy pandas requests`)
