# Déploiement de l'application GP AI sur Render

L'application est déployée sur un hébergeur distant (Render) afin de fournir l'**URL publique en
HTTPS** exigée. Le même code tourne aussi en local (`python app.py`) pour les tests et la démonstration.

## Prérequis
- Le code est sur GitHub : https://github.com/Yacineismael/GENOPED
- Un compte Render (gratuit) : https://render.com

## Déploiement automatique (grâce à `render.yaml`)

1. Se connecter sur **render.com** avec le compte **GitHub**.
2. Cliquer sur **New +** → **Blueprint**.
3. Sélectionner le dépôt **GENOPED**. Render détecte le fichier `render.yaml` et pré-remplit tout.
4. Cliquer sur **Apply**. Render installe les dépendances, puis lance l'application.
5. Au bout de quelques minutes, une **URL publique** apparaît :
   `https://genoped-gp-ai.onrender.com` (ou un nom proche).

## Déploiement manuel (si le Blueprint n'est pas utilisé)

1. **New +** → **Web Service** → sélectionner le dépôt **GENOPED**.
2. Renseigner :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app --workers 1 --timeout 120 --bind 0.0.0.0:$PORT`
   - **Instance Type** : Free
3. Dans **Environment**, ajouter :
   - `PYTHON_VERSION` = `3.13.5`
   - `FLASK_DEBUG` = `0`
   - `SECRET_KEY` = (une longue chaîne aléatoire)
4. **Create Web Service**.

## Identifiants de démonstration
- **Praticien** — code d'accès : `94450`
- **Back-office** (`/admin`) — utilisateur : `admin` / mot de passe : `genoped2026`

## Notes importantes
- **Mise en veille** : l'offre gratuite de Render met le service en veille après 15 minutes
  d'inactivité ; le premier accès suivant prend 30 à 50 secondes (réveil du serveur).
- **Base de données** : en ligne, l'application utilise une base SQLite recréée à chaque
  redémarrage (les consultations de démonstration ne sont pas conservées durablement). En production
  chez GénoPed, la base serait un PostgreSQL sur infrastructure **certifiée HDS** (variable
  d'environnement `DATABASE_URL`).
- **HTTPS** : fourni automatiquement par Render.
