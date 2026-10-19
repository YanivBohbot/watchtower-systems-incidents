# WatchTower

Plateforme Full Stack d'analyse de vidéos importées et d'investigation assistée.
Interface française, FastAPI, React/TypeScript, YOLO, RAG, LangChain/LangGraph et MCP.

**Version de portfolio fonctionnelle, pas une plateforme de surveillance certifiée.**
Les sources implémentent les intégrations réelles ; les tests automatisés remplacent
les appels payants et le détecteur par des ports déterministes. Lire
[le bilan de vérification](docs/VERIFICATION.md) avant de confondre code fourni et intégrations exécutées.

## Lire et comprendre le projet

- [Guide du code et de l'architecture, fichier par fichier](docs/GUIDE_FR.md)
- [Infrastructure, contrats HTTP et exploitation](docs/OPERATIONS_FR.md)
- [Spécification de la V1](docs/superpowers/specs/2026-10-18-watchtower.md)
- [Vérifications réellement effectuées et limites](docs/VERIFICATION.md)

## Démarrage avec Docker Compose

Prérequis : Docker avec Compose v2, Python 3 pour générer le fichier d'environnement,
quelques Go disponibles pour l'image Python/PyTorch, accès Internet pour les images,
les dépendances et les poids YOLO au premier lancement.

Depuis le dossier extrait `watchtower` :

```bash
python scripts/init_env.py
```

Ouvrir `.env` dans son éditeur et renseigner `OPENAI_API_KEY` avec sa clé existante.
Ne pas publier ce fichier. L'abonnement ChatGPT ne couvre pas les appels API.
Le modèle et le modèle d'embeddings sont configurables ; choisir des modèles
auxquels le projet OpenAI a effectivement accès.

```bash
docker compose up --build -d
docker compose exec api python -m app.cli create-user yaniv@example.com --role admin
```

Le mot de passe est demandé dans le terminal, sans affichage. Minimum 12 caractères.
Ouvrir **http://localhost:5173**, puis se connecter. Documentation HTTP :
**http://localhost:5173/api/docs**.

Le build par défaut utilise PyTorch CPU. Aucun GPU n'est obligatoire ; la vitesse
dépend du matériel. Les vidéos sont limitées à 100 Mo, 180 secondes et 3840×2160.
La durée maximale d'une tâche est également bornée.

## Première démonstration

1. Ajouter `examples/procedure-zone-a.txt` dans l'onglet **Procédures**.
2. Attendre son état **Indexé**. L'indexation appelle l'API d'embeddings.
3. Filmer une personne consentante, caméra fixe, 30–60 secondes : entrer, rester
   dans une zone plusieurs secondes, puis ressortir.
4. Importer la vidéo. Dessiner la zone et choisir un seuil de 2 ou 3 secondes.
5. Cliquer **Lancer l'analyse**. Le premier traitement peut télécharger les poids YOLO.
6. Depuis un événement, ouvrir une investigation. Le LLM consulte les observations,
   les procédures et éventuellement les outils MCP de tickets.
7. Lire le rapport, ses références et ses limites. Approuver avec ou sans ticket,
   ou rejeter. Le ticket est créé par le workflow après approbation, jamais directement
   par l'agent.

Une vidéo ne satisfaisant pas la règle peut légitimement produire zéro événement.
Le système ne reconnaît pas l'identité ni l'intention d'une personne.

## Organisation

```text
watchtower/
  backend/
    app/
      domain/       contrats, géométrie et règle de durée
      adapters/     stockage, YOLO, Qdrant et MCP
      services/     pipelines vidéo et documentaire
      agent/        agent, schéma du rapport et workflow HITL
      api.py        interface HTTP et autorisations
      auth.py       mots de passe et jetons
      db.py         modèles et sessions SQL
      runtime.py    assemblage des adaptateurs
      tasks.py      tâches Celery et outbox SQL
      cli.py        administration locale
    migrations/     historique Alembic
    tests/          tests métier, API, vidéo, RAG, agent et MCP
  frontend/
    src/            composants React, client HTTP et styles
    tests/          scénario navigateur Playwright
  mcp_server/       serveur de tickets MCP sur stdio
  skills/           instructions versionnées de l'agent
  examples/         procédure fictive de démonstration
  scripts/          génération locale du fichier d'environnement
  docs/             explication détaillée et bilan
  compose.yaml      services, réseaux et volumes
```

## Tests sans clé API

```bash
cd backend
python -m venv .venv
# Linux/macOS : source .venv/bin/activate
# PowerShell : .venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install -e '.[dev]'
pytest
ruff check app tests migrations
```

L'extra `vision` est nécessaire pour lancer YOLO hors Docker :
`pip install -e '.[vision]'`. Installer PyTorch CPU explicitement avant cet extra
si l'on souhaite éviter les dépendances CUDA.

```bash
cd frontend
npm ci
npm run build
npx playwright install chromium
```

Le scénario navigateur lance sa propre API de test : pas d'OpenAI, pas de Celery,
pas de résultats de vision prétendument réels. Pour le lancer, définir
`WATCHTOWER_PYTHON` vers le Python de l'environnement backend si `python` n'est pas
déjà cet interpréteur, puis `npx playwright test`.

## Limites assumées

- Un seul espace partagé : les rôles s'appliquent à l'organisation entière.
- Vidéos importées et une zone rectangulaire par vidéo ; pas de caméra live.
- Détection de personnes avec YOLO COCO et ByteTrack ; perte d'ID possible en cas
  d'occultation. Une nouvelle trajectoire peut générer un nouvel événement.
- Documents PDF textuels/TXT ; pas d'OCR. Les documents sont immuables et dédupliqués
  par contenu. Remplacement/suppression de versions : non implémentés.
- Stockage local partagé par volumes. Le port `Storage` prépare un remplacement S3,
  mais l'adaptateur S3 n'est pas inclus dans cette V1.
- Le LLM reçoit des observations structurées et des liens vers les preuves,
  pas les pixels de la capture. L'analyse multimodale par VLM est une extension distincte.
- Un seul worker d'investigation ; checkpoints SQLite. Pour le distribuer,
  remplacer le saver par PostgreSQL et revoir le verrouillage.
- Actualisation de l'interface par polling, pas SSE/WebSocket.
- Pas de SSO, multi-tenant, TLS public, autoscaling, ni supervision externe configurés.

La documentation explique les extensions possibles ; elle ne les présente pas
comme déjà développées.
