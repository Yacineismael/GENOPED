# GP AI — Aide à l'orientation diagnostique des troubles génétiques chez l'enfant

Application web qui propose, à partir des données cliniques d'un enfant, les **3 troubles génétiques
les plus probables** (parmi 9), à l'aide d'un modèle d'apprentissage supervisé (Forêt aléatoire).

> ⚠️ Outil d'aide à l'orientation uniquement. Il ne pose pas de diagnostic et ne remplace pas un
> professionnel de santé ni un test génétique.

## Prérequis
- Python 3.10 ou plus
- Les dépendances listées dans `requirements.txt`

## Installation
```bash
# 1. (recommandé) créer un environnement virtuel
python -m venv venv
# Windows :
venv\Scripts\activate
# macOS / Linux :
source venv/bin/activate

# 2. installer les dépendances
pip install -r requirements.txt
```

## Lancement
```bash
python app.py
```
Puis ouvrir dans un navigateur : **http://127.0.0.1:5000**

## Utilisation
1. Renseigner les informations de l'enfant (âges, analyses, symptômes, antécédents).
2. Les champs non connus peuvent rester sur « Inconnu ».
3. Cliquer sur **Analyser** : l'application affiche les 3 diagnostics les plus probables avec leur
   probabilité.

## Base de données

L'application enregistre chaque analyse dans la table `consultations`, à des fins de **traçabilité
médicale** et de statistiques d'usage. **Aucune donnée identifiante n'est stockée** (ni nom, ni date de
naissance, ni identifiant patient) : seuls les signes cliniques saisis et la suggestion du modèle sont
conservés — pseudonymisation par conception.

**Par défaut : SQLite** (aucune installation nécessaire)
```
sql/genoped.db        base de données (tables : patients, consultations)
sql/genoped_dump.sql  dump SQL compatible PostgreSQL
sql/creation_base.py  script de création + comparatif de performance des requêtes
```

**Bascule vers PostgreSQL** — une seule variable d'environnement à définir, aucun code à modifier :
```bash
# Windows
set DATABASE_URL=postgresql+psycopg2://genoped_app:motdepasse@localhost:5432/genoped
# macOS / Linux
export DATABASE_URL=postgresql+psycopg2://genoped_app:motdepasse@localhost:5432/genoped
```
Import du dump dans PostgreSQL :
```bash
createdb genoped
psql -U postgres -d genoped -f sql/genoped_dump.sql
```

## Identifiants

**Connexion praticien** — l'accès à l'outil (`/analyse`) est réservé aux praticiens identifiés. Sur la
page de connexion, le praticien saisit son **nom**, son **prénom**, son **établissement** et un **code
d'accès** partagé :

| Champ | Valeur de démonstration |
|---|---|
| Code d'accès | `94450` |

L'établissement se choisit dans un menu déroulant (liste des CHU / CHR de France).

Modifiable par la variable d'environnement `CODE_ACCES_PRATICIEN`. L'identité du praticien est
enregistrée avec chaque analyse (traçabilité médicale).

**Back-office administrateur** — accessible sur `http://127.0.0.1:5000/admin`

| Identifiant | Mot de passe |
|---|---|
| `admin` | `genoped2026` |

Modifiables par les variables d'environnement `ADMIN_UTILISATEUR` et `ADMIN_MOTDEPASSE`.
Le back-office affiche le nombre de consultations, la répartition des diagnostics proposés, la
confiance moyenne et les 50 dernières consultations.

> ⚠️ Ces identifiants sont ceux de l'environnement de démonstration. En production, ils doivent être
> remplacés et l'accès restreint (HTTPS, réseau interne, hébergement HDS).

L'application elle-même (accueil et analyse) est **publique et sans authentification** : elle est
destinée aux praticiens des établissements partenaires.

## Structure du projet
```
Disorders/
├── app.py                    # application Flask (back-end)
├── database.py               # accès base de données (SQLite ou PostgreSQL)
├── templates/
│   ├── accueil.html          # page d'accueil GénoPed
│   ├── index.html            # formulaire d'analyse + résultats
│   └── admin.html            # back-office administrateur
├── static/
│   ├── style.css             # styles
│   └── script.js             # formulaire en étapes + validation
├── model/
│   ├── modele_gpai.pkl       # modèle entraîné (pipeline + métadonnées)
│   └── contexte_maladies.json# descriptions, signatures cliniques, examens
├── sql/                      # base de données et dump
├── requirements.txt          # dépendances
└── README.md
```

## Le modèle
- **Algorithme** : Forêt aléatoire (RandomForestClassifier)
- **Hyperparamètres** : n_estimators=400, min_samples_leaf=10, max_features='sqrt',
  class_weight='balanced'
- **Variables exclues** (fuite d'information) : noms de gènes, statut du panel génétique
- **Performance (jeu de test)** : accuracy 57 %, F1 macro 0,42, **Top-3 accuracy 87 %**
- Détails et démarche complète dans les notebooks (`Disorders.ipynb`,
  `disorders_analyse_exploratoire.ipynb`, `Disorders_modelisation.ipynb`).

## Accessibilité
Interface conçue pour être accessible : structure sémantique, libellés associés à chaque champ,
navigation au clavier avec focus visible, contrastes suffisants, lien d'évitement, et zone de
résultats annoncée aux lecteurs d'écran (`aria-live`).
