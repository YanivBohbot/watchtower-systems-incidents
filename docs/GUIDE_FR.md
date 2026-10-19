# Comprendre le code de WatchTower

Ce guide explique chaque fichier de l'application et les fonctions importantes.
Les sources constituent la référence : les extraits ci-dessous décrivent le code
livré, pas un pseudo-projet parallèle.

## 1. Pourquoi cette architecture ?

Trois problèmes différents sont séparés : extraire des observations d'une vidéo,
appliquer une règle métier, puis préparer une investigation à partir de preuves.
L'analyse image par image est prévisible ; l'investigation nécessite parfois de
choisir quels outils consulter. Les autorisations et l'approbation ne dépendent
jamais du bon vouloir du modèle.

Le backend est un **monolithe modulaire** : un code Python organisé en modules,
exécuté par plusieurs processus. FastAPI sert le HTTP, Celery exécute les tâches.
Ces processus partagent PostgreSQL et le volume de fichiers. Ce ne sont pas des
microservices indépendants avec leur propre base.

Le pattern **ports et adaptateurs** est utilisé aux frontières. Les services
acceptent un objet qui possède les méthodes requises ; Python utilise ici des
`Protocol` pour documenter ces capacités. Changer YOLO ou Qdrant n'oblige pas à
réécrire la règle de durée. Il faut néanmoins vérifier les différences de scores,
de coordonnées et de performances du nouvel adaptateur.

## 2. Domaine : les contrats stables

### `backend/app/domain/rules.py`

`Zone` est un modèle Pydantic. Les coordonnées sont normalisées entre 0 et 1 :
une zone reste donc indépendante de la résolution. Les champs imposent les bornes ;
`ordered()` refuse un rectangle inversé ou sans aire. `dwell_seconds` représente
le temps minimal de présence, en secondes de vidéo.

`Observation` est une dataclass immuable contenant un ID de suivi, un point et un
horodatage. Le service vidéo choisit le **bas-centre de la boîte**, une approximation
du point de contact au sol. Ce choix est enregistré dans les détails de l'incident.

`DwellRule.feed()` maintient deux structures : `active` conserve début et dernière
observation pour chaque trajectoire ; `emitted` empêche de créer plusieurs événements
pour la même trajectoire dans cette analyse. Sortir de la zone ou disparaître trop
longtemps réinitialise le compteur. La règle ne connaît ni image, ni SQL, ni agent.

### `backend/app/domain/text.py`

`chunk_text()` découpe une page en fenêtres de caractères avec chevauchement.
`size=1200`, `overlap=180` sont des choix de départ, pas une valeur universelle.
Le chevauchement conserve un peu de contexte entre passages. La validation évite
un pas nul et les pages vides sont ignorées. C'est volontairement un découpage
simple, à comparer ensuite à un découpage structurel ou par tokens.

### `backend/app/domain/ports.py`

`Storage` décrit les opérations fichier. `Embedder` distingue embeddings de documents
et de requêtes. `VectorIndex` expose indexation, recherche et suppression de points.
Les tests injectent des objets déterministes implémentant ces méthodes. Ils ne
changent pas le comportement métier pour réussir.

## 3. Configuration, persistance et sécurité

### `backend/app/config.py`

`Settings` lit les variables d'environnement et éventuellement `.env`. `SecretStr`
évite l'affichage accidentel des secrets dans la représentation du modèle.
Cela ne remplace pas une gestion de secrets en production. `settings()` met en
cache la configuration du processus et prépare le dossier de données.

### `backend/app/db.py`

`Base` est le registre déclaratif SQLAlchemy. `make_sessions()` crée le moteur
et une fabrique de sessions ; une session représente une unité de travail SQL.
SQLite reçoit les réglages de clés étrangères et un délai de verrouillage.
Docker utilise PostgreSQL avec le même schéma métier.

| Table | Pourquoi elle existe |
|---|---|
| `User` | Compte, hash du mot de passe, rôle |
| `Video` | Nom, clé de stockage et règle configurée |
| `Job` | Travail durable, progression, état et erreur |
| `Incident` | Événement, trajectoire, temps vidéo et preuve |
| `Document` | Document immuable et empreinte SHA-256 |
| `Chunk` | Texte canonique, page et document d'un passage |
| `Investigation` | Rapport, état, auteur et décision humaine |

Les contraintes uniques protègent l'intégrité même lorsque deux processus agissent
simultanément. Elles ne sont pas remplacées par un simple `if` Python.

### `backend/app/auth.py`

`hash_password()` utilise PBKDF2-SHA256, un sel aléatoire et 600 000 itérations.
Le mot de passe original n'est pas stocké. `verify_password()` recalcule le hash
et compare les octets avec `hmac.compare_digest`.

`token_for()` signe un JWT HS256 valable huit heures. L'API extrait son `sub`,
vérifie signature et expiration, puis recharge l'utilisateur et son rôle en SQL.
Une modification du rôle prend ainsi effet sur les requêtes suivantes.

### `backend/app/cli.py`

`create-user` demande le mot de passe avec `getpass` et crée un utilisateur sans
exposer de route d'inscription publique. `recover-job` remet un travail bloqué
à `queued`. Ce dernier doit être utilisé seulement après avoir confirmé l'arrêt
de l'ancien worker ; il n'est pas un mécanisme de lease distribué.

### `backend/migrations/`

`env.py` fournit le moteur et les métadonnées à Alembic. `0001_initial.py` définit
explicitement le schéma initial ; il ne se contente pas d'appeler `create_all()`
sur des modèles qui pourraient évoluer. Toute évolution ultérieure exige une
nouvelle révision Alembic. Les tests isolés utilisent `create_all()` pour la vitesse.

## 4. L'API : du HTTP aux cas d'usage

### `backend/app/api.py`

`create_app()` est une fabrique : les tests lui fournissent une base temporaire et
un dispatcher déterministe ; le lancement normal assemble les dépendances réelles.

`current()` vérifie le JWT. `operator()` autorise uniquement opérateurs et admins
pour les mutations. Les viewers peuvent lire l'espace partagé. `public()` sérialise
les colonnes publiques et retire hashes et clés internes de stockage.

`bounded_upload()` lit le fichier par blocs, refuse les fichiers vides et applique
la limite en octets. L'extension est une première validation ; le contenu vidéo
est réellement décodé dans le worker, et les PDF sont réellement parsés à l'ingestion.

`upload_video()` valide la zone, stocke le fichier sous une clé UUID, puis enregistre
la vidéo et le job. Le job est commité **avant** son envoi à Celery. Si Redis est
indisponible, le travail reste durablement en SQL et le scheduler peut le republier.

`upload_document()` calcule SHA-256 pour éviter une nouvelle indexation du même
contenu. Une seconde vérification par contrainte SQL traite les uploads concurrents :
le perdant revient au document existant et supprime son fichier provisoire.

Les routes de contenu recherchent d'abord un ID de vidéo/incident en SQL, après
authentification. Elles n'acceptent pas une clé de fichier arbitraire. Dans cette
V1, la réponse vidéo est chargée en mémoire ; les objets sont bornés à 100 Mo.
Une version à forte charge utiliserait du streaming et des requêtes Range ou des
URLs de stockage signées, après contrôle des droits.

`investigate()` crée le dossier et son job. `review()` effectue une mise à jour
conditionnelle sur `awaiting_review` : deux clics concurrents ne produisent donc
pas deux décisions acceptées. Il enregistre le décideur, la décision et un job
de reprise. `retry()` ne réactive que les jobs en échec.

`enqueue()` est volontairement best-effort : la publication ne fait pas partie de
la transaction SQL. La table `jobs`, l'atomic claim du worker et le balayage périodique
forment une petite **outbox durable**.

### `backend/app/main.py`

Point d'entrée Uvicorn : charger la configuration puis construire l'application.
Il n'exécute pas de migration ni de traitement lourd à l'import.

## 5. La vidéo, de bout en bout

### `backend/app/adapters/storage.py`

`LocalStorage.path()` résout le chemin et impose qu'il reste sous la racine du
stockage. `put()` écrit dans un fichier temporaire puis le remplace. `read()` lit
les octets, `delete()` permet le nettoyage, `local_copy()` retourne ici directement
le chemin local. Un futur adaptateur distant pourrait télécharger dans le chemin
temporaire fourni à cette dernière méthode.

### `backend/app/adapters/vision.py`

`TrackedObject` contient une boîte normalisée, le score du détecteur et un ID.
`YoloDetector` importe Ultralytics uniquement à son instanciation : le backend et
les tests métier fonctionnent donc sans installer les poids ou PyTorch.

Une instance est créée **par vidéo**, pour isoler l'état de ByteTrack.
`track()` appelle YOLO avec `persist=True`, le tracker ByteTrack et la catégorie
COCO `0` — personne. Les tenseurs du SDK sont convertis en objets Python stables.
`lap` est déclaré explicitement pour éviter une installation surprise au premier suivi.

### `backend/app/services/video.py`

`VideoService.analyze()` ouvre le fichier avec OpenCV, vérifie ses propriétés,
instancie le détecteur et traite les images progressivement. L'horodatage est
`numéro_image / fps`, pas l'heure à laquelle le CPU finit l'inférence.

Pour chaque objet, le service calcule le bas-centre puis appelle `DwellRule.feed()`.
Lors d'un événement, il dessine zone et boîte sur une copie de l'image, crée un JPEG,
stocke la capture et enregistre l'incident. La contrainte `(video_id, track_id)` et
la lecture des événements existants évitent les doublons lors d'une reprise.

`progress()` met à jour le job tous les 30 frames. Un fichier invalide, trop grand,
trop long ou tronqué échoue explicitement. Une analyse partiellement effectuée
peut avoir déjà créé des événements : vérifier l'état du job avant de considérer
sa liste comme complète. Ce n'est pas une transaction unique couvrant toute la vidéo.

## 6. Le RAG, de bout en bout

### `backend/app/adapters/vectors.py`

`QdrantIndex.upsert()` crée la collection si nécessaire, avec la dimension du
premier vecteur et la distance cosinus. Les IDs sont ceux des chunks SQL.
`search()` renvoie IDs et scores. **Le texte du rapport n'est pas obtenu directement
depuis un payload Qdrant non contrôlé.** `delete()` expose le nettoyage de points,
sans route de suppression documentaire dans cette V1.

### `backend/app/services/knowledge.py`

`ingest()` fait passer le document à `indexing`, extrait les pages, découpe le texte,
calcule des IDs déterministes UUID5 et demande les embeddings. L'indexation Qdrant
est terminée avant que SQL marque le document `indexed`. Les mêmes IDs permettent
de réessayer sans ajouter des copies du même passage. En cas d'erreur, le document
passe à `error` et les passages de cet état ne sont pas servis à la recherche.

`search()` calcule l'embedding de la question, interroge Qdrant, puis résout chaque
ID dans SQL en exigeant un document `indexed`. Il retourne le texte canonique,
le nom du document et la page. Les IDs inconnus ou non actifs sont ignorés.

Il n'existe pas de transaction distribuée entre SQL et Qdrant : l'ordre des écritures,
les IDs déterministes et le filtre SQL rendent les reprises cohérentes pour ce cas.
Les nouveaux fichiers sont des documents distincts ; il n'y a pas encore de gestion
automatique de supersession entre versions d'une procédure.

## 7. L'agent et son workflow

### `backend/app/agent/schemas.py`

`Report` impose une sortie structurée : résumé, constats, recommandation, citations,
limites. `validate_report()` refuse un ID de citation absent du jeu effectivement
récupéré pour l'investigation. Les sources détaillées sont réattachées par le code.
Sans citation, une limite explicite est ajoutée.

Cela empêche une référence inventée à un passage inexistant ; **cela ne démontre
pas que chaque phrase est sémantiquement justifiée**. L'évaluation et la validation
humaine restent nécessaires.

### `backend/app/agent/investigator.py`

`Investigator.run()` charge l'incident et construit des outils limités au contexte :

| Outil | Accès autorisé |
|---|---|
| `get_evidence` | Observations et lien de preuve de l'incident courant |
| `search_procedures` | Recherche documentaire et enregistrement des sources récupérées |
| `search_related_events` | Dix événements au maximum dans la même vidéo, autour de ±60 s |
| Outils MCP en lecture | Recherche et lecture de tickets |

Une recherche documentaire initiale est imposée par le code. L'agent peut affiner
ensuite. Les outils sont des fermetures : leurs données de contexte ne sont pas
des paramètres librement fournis par le modèle.

`create_agent()` construit une boucle d'appels d'outils. `ToolStrategy(Report)`
demande la sortie structurée. La profondeur est limitée à 16 étapes de graphe,
chaque requête modèle a un timeout et un nombre de retries limité. Ce n'est pas
encore un compteur monétaire global. Le fournisseur est assemblé par `make_model()` ;
une autre fabrique peut fournir un modèle compatible sans modifier les outils.

`tool_trace` conserve les noms des outils locaux, pas un raisonnement interne du LLM.
Les appels MCP ne sont pas détaillés dans cette trace minimale.

### `skills/investigate/SKILL.md`

Il s'agit d'une **procédure applicative chargée dans le prompt système**, versionnée
avec le projet. Ce n'est pas un moteur de découverte dynamique de skills et ce fichier
ne s'installe pas automatiquement comme skill ChatGPT. Les étapes rappellent le
contrôle des preuves, la séparation faits/hypothèses et la validation humaine.

### `backend/app/agent/workflow.py`

`build_workflow()` produit un LangGraph avec trois nœuds :

1. `investigate` prépare et persiste le brouillon.
2. `human_review` appelle `interrupt()` et suspend l'exécution.
3. `finalize` applique la décision et publie éventuellement un ticket.

Le point clé : le nœud de validation ne crée pas de ticket avant `interrupt()`.
LangGraph peut réexécuter ce nœud lors d'une reprise. L'effet externe est dans une
étape ultérieure, avec une clé d'idempotence.

Le pattern est donc **workflow déterministe contenant un agent à outils**, et non
plusieurs agents jouant artificiellement des rôles. La détection vidéo ne traverse
pas cette boucle.

### `backend/app/runtime.py`

C'est la **composition root**. `knowledge_service()` choisit embeddings et Qdrant.
`execute()` route un type de job vers le service approprié.

Pour une investigation, il assemble l'agent, le serveur MCP, le saver SQLite et
le graphe. `thread_id` vaut l'ID de l'investigation. Une nouvelle invocation démarre
le graphe ; une reprise utilise `Command(resume=...)`. Un graphe terminé n'est pas
redémarré lors d'une livraison répétée du job. Si `finalize` avait échoué, il est
repris à partir de son checkpoint sans redemander le rapport au LLM.

## 8. MCP : une intégration réelle et limitée

### `mcp_server/server.py`

Serveur MCP **stdio**, lancé comme sous-processus local. `FastMCP` expose
`search_tickets`, `get_ticket` et `create_ticket`. Les données sont dans un SQLite
persistant. Le transport n'ouvre pas un port réseau et ne nécessite pas ici de
serveur OAuth ; son périmètre de confiance est le processus autorisé à le lancer.

`create_ticket()` emploie une clé d'idempotence unique et `INSERT OR IGNORE` :
si le ticket a été créé mais que la réponse s'est perdue, une nouvelle demande
avec la même investigation renvoie le même ticket.

### `backend/app/adapters/tickets.py`

`McpTickets` configure `MultiServerMCPClient` avec le chemin du serveur et celui de
sa base. `read_tools()` ne transmet à l'agent que les deux outils en lecture.
`publish()` appelle explicitement `create_ticket` depuis le workflow approuvé et
vérifie les erreurs du protocole. C'est notre propre système de tickets ; il ne
prétend pas écrire dans Jira, Linear ou un autre service non connecté.

## 9. Traitements et reprise

### `backend/app/tasks.py`

`run_job()` réclame le travail par `UPDATE ... WHERE status='queued'`. Seul le
processus qui modifie la ligne l'exécute. Les autres livraisons quittent la fonction.
Le traitement passe ensuite à `completed` ou `failed`, avec logs corrélés à l'ID.
Le message public d'erreur reste succinct ; les détails sont dans les logs.

`sweep()` republie périodiquement les jobs encore `queued`. La file `processing`
sert la vidéo et les documents ; `investigation` sert l'agent et la reprise humaine.
Une interruption brutale du processus peut laisser `running` : la commande de
récupération est alors nécessaire. Pas de promesse d'exécution exactly-once.

## 10. Le frontend, fichier par fichier

| Fichier | Explication |
|---|---|
| `src/main.tsx` | Monte React et le `QueryClientProvider` qui partage cache et mutations |
| `src/types.ts` | Contrats TypeScript des réponses utilisées par l'interface |
| `src/api.ts` | `request()` ajoute le Bearer token, gère JSON/FormData et erreurs ; `mediaUrl()` récupère un blob authentifié |
| `src/ZoneEditor.tsx` | Dessin du rectangle par Pointer Events ; transforme les pixels de l'écran en coordonnées normalisées |
| `src/App.tsx` | Connexion, navigation et vues vidéo/procédures/investigations ; mutations et rafraîchissement des listes |
| `src/style.css` | Mise en page responsive, états, formulaires et affichage des preuves |
| `vite.config.ts` | Build React et proxy `/api` en développement |
| `nginx.conf` | Sert le build et transmet `/api` à FastAPI |
| `nginx-limits.conf` | Limite le rythme des demandes de connexion au niveau du proxy |

`useMedia()` annule les téléchargements obsolètes et révoque les URLs de blobs pour
éviter des fuites mémoire. Le token n'est pas inséré dans une URL vidéo.

`ZoneEditor` conserve le ratio intrinsèque de la vidéo. Le mode de dessin recouvre
l'image ; on termine la sélection pour accéder aux commandes vidéo. La zone
envoyée au backend correspond au repère de l'image, pas à un rectangle déformé.

Dans `App`, TanStack Query rafraîchit les listes toutes les 2,5 secondes. Après une
mutation, le cache est invalidé. Les chargements, erreurs, vues vides et traitements
en échec sont affichés. Le rôle viewer masque les commandes de mutation, mais
**l'autorisation décisive reste dans FastAPI**.

Le JWT est conservé en `sessionStorage` pour cette application locale ; un déploiement
public demanderait une stratégie de session, CSP et protection XSS adaptées.

## 11. Les fichiers d'infrastructure et de tests

`compose.yaml` assemble les services et volumes. Les Dockerfiles construisent le
backend CPU et le frontend statique. `.env.example` documente la configuration ;
`scripts/init_env.py` génère uniquement des secrets locaux et ne connaît pas la clé
OpenAI. `.gitignore` et `.dockerignore` excluent données et secrets.

`requirements.lock` fixe l'environnement backend vérifié ; l'extra vision et PyTorch
CPU sont installés séparément par le Dockerfile. `package-lock.json` fixe les
dépendances frontend. `.github/workflows/ci.yml` exécute tests, lint et build.

Les fichiers `tests/test_*.py` vérifient les règles, droits, concurrence des uploads,
pipeline documentaire, lecture d'une vraie vidéo générée, workflow persistant,
boucle LangChain avec fournisseur scripté et protocole MCP réel. Les adaptateurs
déterministes de test sont situés dans les tests, pas activés comme un mode de
production silencieux. `tests/ui_server.py` sert uniquement au scénario Playwright.

## Ordre de lecture conseillé

Commencer par `domain/rules.py`, puis `services/video.py`, `api.py` et `tasks.py`.
Lire ensuite `services/knowledge.py`, `agent/investigator.py`, `agent/workflow.py`
et `runtime.py`. Terminer par MCP, React et Compose : chaque composant aura alors
un rôle clair dans le parcours complet.
