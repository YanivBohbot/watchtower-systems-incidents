# Infrastructure et exploitation

## Services et responsabilités

| Service Compose | Commande / rôle | Persistance |
|---|---|---|
| `frontend` | Nginx non privilégié, React compilé et proxy HTTP | Build immuable |
| `api` | Uvicorn / FastAPI | PostgreSQL et fichiers |
| `worker` | Celery, file `processing`, concurrence 1 | Jobs SQL et fichiers |
| `investigator` | Celery, file `investigation`, concurrence 1 | Checkpoints SQLite, tickets et SQL |
| `scheduler` | Celery Beat, balayage de l'outbox toutes les 30 secondes | Fichier de calendrier |
| `migrate` | Alembic, exécution unique | Schéma PostgreSQL |
| `postgres` | Données métier | Volume `postgres-data` |
| `redis` | Courtier de tâches | Les jobs SQL restent la source durable |
| `qdrant` | Index vectoriel | Volume `qdrant-data` |

Les services backend montent le volume `app-data`. Il contient les médias, les
checkpoints, les tickets et les poids du détecteur. Le serveur MCP est un
sous-processus de l'investigateur, pas un service réseau supplémentaire.

Seul le frontend est exposé, sur `127.0.0.1:5173`. Le proxy relaie `/api`.
Le backend, Redis, PostgreSQL et Qdrant restent sur le réseau Compose interne.
Le rate limiting de connexion est configuré dans Nginx ; un lancement Uvicorn
direct sans proxy n'applique pas cette limitation.

## Contrats HTTP

Les routes protégées attendent `Authorization: Bearer <token>`.

| Méthode / route | Entrée | Effet |
|---|---|---|
| `GET /api/health` | Aucune | Santé du processus, pas un diagnostic complet des dépendances |
| `POST /api/auth/login` | JSON email/password | JWT et utilisateur |
| `GET /api/me` | Jeton | Profil courant |
| `GET /api/videos` | Jeton | Vidéos partagées |
| `POST /api/videos` | Multipart `file`, `zone` JSON | Vidéo et job d'analyse |
| `GET /api/videos/{id}/content` | Jeton | Octets de la vidéo |
| `GET /api/documents` | Jeton | Documents et état d'indexation |
| `POST /api/documents` | Multipart `file` | Document et job d'ingestion, déduplication SHA-256 |
| `GET /api/incidents` | Jeton | Événements détectés |
| `GET /api/incidents/{id}/evidence` | Jeton | Capture JPEG |
| `POST /api/incidents/{id}/investigate` | Jeton opérateur | Dossier et job d'investigation |
| `GET /api/investigations` | Jeton | Rapports et états |
| `POST /api/investigations/{id}/review` | JSON approved/create_ticket | Décision puis job de reprise |
| `GET /api/jobs` | Jeton | Les 100 travaux les plus récents |
| `POST /api/jobs/{id}/retry` | Jeton opérateur | Relance d'un travail en échec |

Exemple de zone :

```json
{"x1":0.25,"y1":0.15,"x2":0.8,"y2":0.9,"dwell_seconds":3}
```

Exemple de validation :

```json
{"approved":true,"create_ticket":true}
```

La documentation OpenAPI est disponible sous `/api/docs`.

## États et cohérence

Un job suit `queued → running → completed` ou `failed`. L'atomic claim empêche
deux livraisons du même job de le lancer simultanément. Le balayage SQL répare
l'absence de publication dans Redis, pas une mort brutale pendant l'exécution.

Une investigation passe de `queued` à `awaiting_review`, puis `review_queued`,
et enfin `approved` ou `rejected`. L'état du job indique un éventuel échec
intermédiaire. Un rapport approuvé sans ticket ne crée aucun objet MCP.

Les checkpoints SQLite sont partagés entre invocations, sous une unique file
d'investigation et un unique worker à concurrence 1. **Ne pas répliquer ce worker**
sans remplacer le saver et prévoir une coordination distribuée.

## Diagnostic et reprise

```bash
docker compose ps
docker compose logs --tail=100 api worker investigator scheduler
```

Pour une erreur de document : vérifier l'accès API, le texte extractible, le modèle
d'embeddings et la disponibilité de Qdrant. Changer de dimension d'embedding exige
une nouvelle collection et une réindexation ; ne pas réutiliser la collection
existante avec des vecteurs incompatibles.

Pour une vidéo : vérifier format, durée, résolution, accès aux poids YOLO et temps
disponible sur CPU. `lap` est installé explicitement pour ByteTrack. Pour un réseau
fermé, préinstaller `/data/models/yolov8n.pt` dans le volume ; le logiciel ne fournit
pas les poids dans l'archive.

Pour une investigation : vérifier le modèle LLM, sa disponibilité pour la clé
utilisée, le quota API et les logs du processus MCP. Une référence inventée entraîne
un échec du rapport au lieu d'une citation silencieusement acceptée.

Un job `failed` se relance depuis l'interface. Un job resté `running` après une
interruption brutale demande une intervention : confirmer que son ancien worker
est arrêté, puis lancer la récupération et laisser le scheduler le republier.

```bash
docker compose exec api python -m app.cli recover-job IDENTIFIANT_DU_JOB
```

Les logs peuvent contenir des réponses ou erreurs de bibliothèques : limiter leur
accès dans un déploiement réel. La V1 ne met pas en place de plateforme de logs,
de métriques distribuées ou d'alertes externes.

## Développement sans Docker

Installer le backend comme expliqué dans README. Créer `backend/.env` avec un
`JWT_SECRET` local aléatoire et sa clé API. Adapter `DATABASE_URL`, `REDIS_URL` et
`QDRANT_URL` aux services accessibles depuis la machine. SQLite convient au premier
démarrage local ; PostgreSQL est la cible Compose.

Depuis `backend` :

```bash
alembic upgrade head
python -m app.cli create-user yaniv@example.com --role admin
uvicorn app.main:app --reload
```

Dans deux autres terminaux ayant le même environnement :

```bash
celery -A app.tasks:celery worker -Q processing --concurrency=1 --loglevel=INFO
celery -A app.tasks:celery worker -Q investigation --concurrency=1 --loglevel=INFO
```

Puis un quatrième pour Beat :

```bash
celery -A app.tasks:celery beat --loglevel=INFO
```

Depuis `frontend`, `npm ci` puis `npm run dev`. Vite relaie `/api` vers
`localhost:8000`. Celery est plus simple sous Linux, macOS ou WSL ; Docker est
le chemin recommandé sous Windows.

## Déploiement ultérieur

Avant une exposition publique : stratégie TLS/session/SSO, périmètre d'accès aux
données, stockage objet, streaming vidéo, limites de ressources et isolation des
parseurs, sauvegardes, politique de rétention et observabilité. Ce sont des travaux
identifiés, pas des services déjà déployés par ce projet.

Les poids et bibliothèques de vision ont leurs propres conditions de licence.
Vérifier notamment la licence Ultralytics avant une distribution commerciale.
