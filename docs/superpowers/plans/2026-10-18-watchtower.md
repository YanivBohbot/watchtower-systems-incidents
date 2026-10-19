# Plan d'implémentation

1. Domaine et contrats : écrire tests de règles et chunking, constater RED, implémenter les ports et règles.
2. Persistance et API : écrire tests auth/upload/validation, puis modèles SQLAlchemy, migrations et endpoints.
3. Pipelines : stockage, YOLO, traitement vidéo, ingestion, Qdrant, gestion des statuts ; tests par injection de ports.
4. Agent : outils bornés, rapport structuré, contrôle des citations, SQLite checkpoints, interrupt/resume ; tests sans fournisseur payant.
5. MCP : serveur stdio authentifié par frontière processus local, tickets SQLite, déduplication ; test client protocole réel.
6. React : connexion, upload et sélection zone, documents, états/jobs, preuves, rapport et décision ; build TypeScript.
7. Infra et documentation : Compose PostgreSQL/Redis/Qdrant/API/workers/frontend, CI, guide fichier par fichier et bilan vérifié.

## Review focus
Concurrent resume, atomicité DB/queue, déduplication ticket après échec réseau,
accès aux médias, fichiers invalides, secrets et références documentaires non récupérées.
