# WatchTower — spécification de la version livrée

Application éducative Full Stack pour vidéos importées : détection de personnes,
suivi, règle de présence dans une zone rectangulaire normalisée, incidents avec
capture, documents PDF/TXT, recherche vectorielle, investigation agentique et
validation humaine avant création d'un ticket via un véritable serveur MCP.

## Contrats
- Identifiants UUID. Une seule organisation, plusieurs utilisateurs, rôles viewer/operator/admin.
- Authentification JWT signée, mots de passe PBKDF2. Aucun compte prédéfini public.
- API synchrone courte, Celery pour traitements. PostgreSQL en Docker, SQLite en tests.
- Port de stockage avec adaptateur local livré ; S3 réservé à une extension ; port de détection YOLO ; embeddings OpenAI ; Qdrant.
- Une analyse vidéo est idempotente : un événement au maximum par trajectoire et zone.
- Les détections utilisent les secondes de la vidéo, jamais le temps de calcul.
- Agent LangChain à outils en lecture seule dans un workflow LangGraph persistant.
- Citation valide = identifiant de passage réellement récupéré pendant ce run.
- Reprise HITL : approbation/rejet déterministe, ticket idempotent par investigation.
- Aucune clé dans les sources. Aucun appel payant requis pour les tests.

## Limites explicites
V1 : fichier vidéo, zone rectangulaire, personnes, documents textuels, mono-organisation.
Pas de live RTSP, OCR, garantie de suivi entre occultations, ni déploiement Kubernetes.
La vérification des références ne prouve pas à elle seule la vérité du texte généré.
YOLO est optionnel à l'installation locale ; poids à fournir/télécharger au premier usage.
Tests avec ports déterministes ; intégrations live évaluées séparément selon disponibilité.

## Critères
Tests de règles (sortie de zone, trou de suivi, seuil et doublons), autorisations API,
uploads, RAG avec filtrage des documents indexés, références inventées rejetées, pause/reprise
du graphe et ticket MCP idempotent. Build TypeScript. Configuration Docker et guide FR.
