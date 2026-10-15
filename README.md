# bdnosql-project

Application web simple : un formulaire dont chaque envoi est persisté dans **PostgreSQL** et **MongoDB**.

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

Ouvrir http://localhost:8000, remplir le formulaire et envoyer.

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
| POST    | `/api/submissions`  | Crée une entrée (JSON `name`, `email`, `message`) |
| GET     | `/api/submissions`  | Liste les entrées des deux bases     |
| GET     | `/health`           | État des connexions                  |
| GET     | `/docs`             | Documentation Swagger                |

## Déploiement

Sur le serveur : copier `.env.example` en `.env`, changer les mots de passe, puis `docker compose up -d --build`. Les bases ne sont pas exposées sur Internet, seul le port de l'API l'est.