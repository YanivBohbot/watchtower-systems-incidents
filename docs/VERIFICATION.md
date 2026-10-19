# Bilan de vérification — 18 octobre 2026

Ce document distingue les sources implémentées des intégrations effectivement exécutées.
Aucune clé utilisateur n'a été lue ou enregistrée. Aucun appel OpenAI payant n'a été effectué.

| Contrôle | Résultat | Périmètre réel |
|---|---|---|
| Suite Python `pytest -q` | **19 tests réussis** | Règles, auth, rôles, uploads, concurrence, RAG, vidéo, graphe, agent, MCP, migration, jobs |
| Ruff | **Réussi** | Imports, erreurs Python et formatage des fichiers applicatifs/tests/migrations |
| Build React `npm run build` | **Réussi** | Vérification TypeScript et bundle Vite |
| Prettier | **Réussi** | Sources React, CSS et configuration frontend |
| Playwright | **1 scénario réussi** | Chromium, vraie API FastAPI de test : connexion, espace vide, upload TXT, liste et déconnexion |
| YOLO + ByteTrack réels | **Réussi** | Image de référence Ultralytics : trois personnes suivies, coordonnées normalisées |
| Pipeline vidéo avec YOLO réel | **Réussi** | Huit frames d'une image de référence répétée : trois incidents SQL et leurs captures JPEG |
| Migration Alembic | **Réussi sur SQLite** | Schéma neuf comparé aux modèles, aucune différence |
| MCP stdio | **Réussi** | Processus serveur réel, découverte d'outils, création, recherche et déduplication persistante |
| LangChain | **Réussi avec fournisseur scripté** | Boucle réelle d'appel d'outil et rapport structuré ; pas une réponse OpenAI live |
| LangGraph | **Réussi** | Checkpoint, arrêt pour revue, reprise après réouverture, rejet et retry de publication |
| Qdrant SDK | **Réussi en mode embarqué** | Upsert, classement vectoriel et suppression ; pas un serveur distant |
| Fichier Compose | **YAML parsé** | Services et volumes inspectés ; moteur Docker absent |
| Dépendances Python | **Réussi** | Résolution du lock et `pip check` sans incompatibilité |

## Ce qui n'a pas été exécuté

- Build des images et `docker compose up` : Docker n'est pas installé dans l'environnement de travail.
- PostgreSQL, Redis/Celery broker et Qdrant réseau réunis dans le même déploiement.
- Appels OpenAI d'embeddings et de génération avec la clé personnelle du demandeur.
- Un parcours navigateur complet depuis une vraie vidéo jusqu'à un rapport OpenAI puis un ticket.
- Tests de charge, évaluation de précision sur vidéos représentatives, GPU ou caméra live.

Le test YOLO sur huit frames répétées est un test d'intégration technique, **pas une
mesure de qualité sur des incidents réels**. Le test navigateur valide une partie
du parcours ; les tests backend couvrent séparément les étapes restantes.

## Corrections issues de la vérification

- Installation explicite de `lap` pour ByteTrack.
- Uploads documentaires simultanés : un seul document/job, sans réponse 500 ; test de concurrence ajouté.
- Migration alignée sur le type SQL du temps vidéo ; comparaison automatique ajoutée.
- Injection du client Qdrant pour tester son SDK sans ouvrir de connexion réseau non souhaitée.
- Serveur Vite lié à localhost pour démarrer dans un environnement sans accès à l'inventaire réseau système.

Une relecture indépendante des sources a examiné autorisations, états des jobs,
approbation concurrente, idempotence MCP, médias et démarrage. Les deux problèmes
concrets signalés ont été corrigés. Les limites d'exploitation restent décrites
dans README et OPERATIONS_FR.md.

## Reproduire les vérifications

```bash
cd backend
pytest -q
ruff check app tests migrations
ruff format --check app tests migrations
```

```bash
cd frontend
npm ci
npm run build
npx playwright install chromium
# Définir WATCHTOWER_PYTHON si le Python backend n'est pas celui du PATH.
npx playwright test
```

Pour le test de vision réel, avec l'extra vision installé, depuis la racine :

```bash
python scripts/smoke_vision.py --model CHEMIN_VERS/yolov8n.pt
```

Les poids sont téléchargés s'ils sont absents et disponibles pour Ultralytics.
Les vidéos et poids utilisés pour les essais ne sont pas inclus dans l'archive.
