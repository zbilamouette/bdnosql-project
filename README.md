# bdnosql-project

Livre d'or : les visiteurs peuvent laisser un message public, avec une note facultative de 1 à 5. Chaque envoi est persisté dans **PostgreSQL** et **MongoDB**.

## Architecture

| Service    | Image / Techno        | Rôle                                   |
|------------|-----------------------|----------------------------------------|
| `api`      | Python 3.12 + FastAPI | Serveur web (formulaire + API JSON)    |
| `postgres` | postgres:16           | Stockage relationnel (table `submissions`) |
| `mongo`    | mongo:7               | Stockage document (collection `submissions`) |

## Lancer le projet

```bash
git clone <url-du-repo>
cd bdnosql-project
docker compose up --build
```

Ouvrir http://localhost:8000, remplir le formulaire et envoyer. Les 50 derniers messages PostgreSQL sont affichés, avec le nombre d'entrées retrouvées dans chaque base (limité à 50 par base).

La colonne `rating` est ajoutée automatiquement à la table existante au démarrage : les anciens messages sont conservés et s'affichent sans note. L'adresse e-mail n'est plus demandée sur le formulaire.

## Tests

Avec les dépendances de `app/requirements.txt` et `httpx` installées :

```bash
cd app
python -m unittest discover -s tests -v
```

## Vérifier la persistance

Terminal 1 — PostgreSQL :

```bash
docker compose exec postgres psql -U app -d nosql
SELECT * FROM submissions;
```

Terminal 2 — MongoDB :

```bash
docker compose exec mongo mongosh -u app -p app --authenticationDatabase admin nosql
db.submissions.find()
```

Les données survivent à un `docker compose down` puis `docker compose up` (volumes nommés). `docker compose down -v` les supprime.

## API

| Méthode | Route               | Description                          |
|---------|---------------------|--------------------------------------|
| GET     | `/`                 | Formulaire + données des deux bases  |
| POST    | `/api/submissions`  | Crée une entrée (JSON `name`, `message`, `rating` et `email` facultatifs) |
| GET     | `/api/submissions`  | Liste les entrées des deux bases     |
| GET     | `/health`           | État des connexions                  |
| GET     | `/docs`             | Documentation Swagger                |

## Déploiement

Sur le serveur : copier `.env.example` en `.env`, changer les mots de passe, puis `docker compose up -d --build`. Les bases ne sont pas exposées sur Internet ; avec `API_BIND=127.0.0.1`, l'API n'est accessible que via le reverse proxy.

### Déploiement automatique (GitHub Actions)

Le workflow [.github/workflows/deploy.yml](.github/workflows/deploy.yml) déploie sur `nosql.ggelpm.fr` (`/var/www/nosql`) à chaque push sur `main` (ou manuellement via *Run workflow*). Il envoie le code via `tar` + SSH (rsync non requis), génère le `.env`, lance `docker compose up -d --build` et vérifie `/health`.

Secrets à définir dans *Settings → Secrets and variables → Actions* (`VPS_HOST`, `VPS_USER`, `VPS_PORT` et `VPS_SSH_KEY` peuvent aussi être des variables) :

| Secret              | Description                                  |
|---------------------|----------------------------------------------|
| `VPS_HOST`          | IP ou hostname du VPS                        |
| `VPS_USER`          | Utilisateur SSH (membre du groupe `docker`)  |
| `VPS_SSH_KEY`       | Clé privée SSH                               |
| `VPS_PORT`          | Port SSH (optionnel, défaut `22`)            |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL                      |
| `MONGO_PASSWORD`    | Mot de passe MongoDB                         |

Variable optionnelle : `API_PORT` (défaut `8000`), port local sur lequel nginx doit pointer.