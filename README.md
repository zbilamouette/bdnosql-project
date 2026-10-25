# bdnosql-project

consigne du projet : PROJET NOSQL


Le but de ce projet est de constituer une application web simple, avec au moins une page avec un formulaire qui puisse récupérer des données écrites par un utilisateur et qui les persiste dans au moins deux systemes différents parmi : postgresql - redis - mongodb - neo4j - elasticsearch
Le projet doit avoir au moins un fichier docker compose qui orchestre donc au moins 3 docker (un pour la partie server, et un par techno de stockage)
Le format de restitution est un espace sur github - 
Je dois pourvoir git clone, jouer docker compose up pour interagir avec l'interface web, lancer au moins deux terminaux pour me connecter à chacun des systemes de persistance et constater la persistance.
La date limite de publication du projet sur github est le 13 novembre.
Comme discuté nous passerons l'aprés midi du 19 novembre à présenter les projet à la classe pour échanger sur vos réalisations.
Vous pouvez vous mettre par équipe de 2 ou 3 pour faire ces réalisations, merci de remplir le tableau ci aprés avec vos noms et url de projet.

---

# ⚡ SwiftLink — Raccourcisseur d'URL & Analytics Temps Réel

**SwiftLink** est une application web moderne illustrant une **architecture de stockage hybride** conforme aux standards de l'ingénierie logicielle : elle associe un **SGBD relationnel (PostgreSQL 18)** pour la persistance ACID durable et un **magasin NoSQL en mémoire (Redis 8)** pour le cache sub-milliseconde et les compteurs atomiques temps réel.

---

## 🏗️ Architecture & Rôle des Systèmes

Chaque système remplit un rôle technique précis et non redondant :

| Service | Image / Techno | Rôle Architectural | Justification Technique |
| :--- | :--- | :--- | :--- |
| **`api`** | Python 3.13 + FastAPI | Serveur web asynchrone & API REST | Gestion non-bloquante avec `psycopg_pool` async et `redis.asyncio`. |
| **`postgres`** | `postgres:18-alpine` | Stockage relationnel persistant (table `urls`) | **Source de vérité durable** : contrainte d'unicité sur les slugs, horodatage, transactions ACID. |
| **`redis`** | `redis:8-alpine` | Magasin NoSQL clé-valeur en mémoire | **Performance & Analytics** : cache de redirection (`url:{slug}`), compteurs de clics atomiques (`INCR clicks:{slug}`), classement dynamique en direct via Sorted Set (`popular_urls`). |

---

## 🚀 Lancer le Projet

### Prérequis
- Docker et Docker Compose installés sur votre machine.

### Démarrage en 1 commande

```bash
git clone <url-du-repo>
cd bdnosql-project
docker compose up --build
```

L'application démarre et initialise automatiquement les tables et connexions :
- **Interface Web interactive** : [http://localhost:8000](http://localhost:8000)
- **Documentation OpenAPI (Swagger)** : [http://localhost:8000/docs](http://localhost:8000/docs)
- **Endpoint Healthcheck** : [http://localhost:8000/health](http://localhost:8000/health)

---

## 🔍 Vérifier la Persistance (Démo Soutenance)

Pour valider l'évaluation, ouvrez **deux terminaux distincts** pour vous connecter à chacun des moteurs de stockage.

### Terminal 1 — PostgreSQL (Relationnel ACID)

Connectez-vous au conteneur PostgreSQL :
```bash
docker compose exec postgres psql -U app -d nosql
```

Puis exécutez la requête SQL :
```sql
SELECT id, slug, target_url, created_at FROM urls;
```
> **Constat** : Chaque lien créé via le formulaire y est enregistré avec son identifiant unique auto-incrémenté et son horodatage de création.

---

### Terminal 2 — Redis (NoSQL / En Mémoire)

Connectez-vous au conteneur Redis :
```bash
docker compose exec redis redis-cli
```

Interrogez les clés, compteurs et classements :
```redis
# 1. Lister les clés en cache
KEYS *

# 2. Vérifier la valeur d'une redirection en cache
GET url:<votre_slug>

# 3. Consulter le compteur atomique de clics pour ce lien
GET clicks:<votre_slug>

# 4. Consulter le classement des liens les plus visités (Sorted Set)
ZREVRANGE popular_urls 0 -1 WITHSCORES
```
> **Constat** : Dès qu'un utilisateur clique sur un lien court (`/r/<slug>`), Redis incrémente instantanément le compteur en mémoire via `INCR` sans impacter les performances de la base SQL.

---

### Résistance au Redémarrage

Les deux bases utilisent des volumes Docker nommés (`pg18_data` et `redis_data` avec persistance AOF activée) :
```bash
# Arrêter les conteneurs
docker compose down

# Relancer
docker compose up -d
```
Les données restent intactes. Pour réinitialiser complètement l'environnement, utilisez `docker compose down -v`.

---

## 📡 API REST

| Méthode | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Interface web complète avec formulaire et dashboard interactif |
| `POST` | `/api/links` | Crée un lien court (JSON : `target_url`, `title`, `custom_slug`) |
| `GET` | `/api/links` | Retourne la liste consolidée (PostgreSQL) et les métriques de clics (Redis) |
| `GET` | `/r/{slug}` | Redirection HTTP 307 ultra-rapide vers l'URL d'origine (+ incrément clic) |
| `GET` | `/health` | Diagnostic de connectivité aux deux bases de données |
| `GET` | `/docs` | Documentation interactive Swagger / OpenAPI |

---

## 🌐 Déploiement sur Serveur (VPS)

Pour déployer sur un serveur distant (ex. VPS Debian/Ubuntu) :

1. Cloner le dépôt sur le serveur :
   ```bash
   git clone <url-du-repo> /opt/swiftlink
   cd /opt/swiftlink
   ```
2. Créer le fichier d'environnement :
   ```bash
   cp .env.example .env
   nano .env # Personnalisez vos mots de passe et BASE_URL (ex: https://nosql.votredomaine.fr)
   ```
3. Lancer en tâche de fond :
   ```bash
   docker compose up -d --build
   ```
4. Seul le port HTTP de l'API (8000) est exposé. Configurez un reverse proxy Nginx ou Caddy avec HTTPS (Let's Encrypt) pour pointer sur le port 8000.
