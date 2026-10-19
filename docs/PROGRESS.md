# Exécution — 2026-10-18-watchtower

Le demandeur a explicitement demandé l'implémentation de bout en bout et confirmé sa clé existante.
Exécution locale, aucune clé lue ou créée, aucun appel OpenAI live.
Ruling: checkpoint LangGraph SQLite partagé uniquement par le worker d'investigation singleton ; PostgreSQL conserve les données métier. Évite d'ajouter un second service pour les checkpoints dans cette V1 ; pour plusieurs workers passer au saver PostgreSQL.
Ruling: stockage local par défaut pour démarrage simple ; adaptateur S3 fourni.
Ruling: vidéos importées et rectangles uniquement pour un premier parcours concret et testable.

Task 1: complete — contrats et tests de règles.
Task 2: complete — API, rôles, persistance et uploads.
Task 3: complete — pipelines vidéo/documentaire, agents et workflow checkpointé.
Task 4: complete — MCP réel, React, Compose, migration et CI.
Task 5: complete — guide fichier par fichier, exploitation et bilan des validations.
Final review: relecture indépendante ; dépendance lap et conflit d'upload corrigés.
Final fixed: conflit concurrent d'upload — test reproduit 500 puis passé après correctif.
Final fixed: différence Float/Double de migration — comparaison RED puis GREEN.
Final verification: 19 tests backend ; un scénario Playwright ; build React ; YOLO/ByteTrack réel et pipeline vidéo avec captures.
Operational limits: pas de Docker ni d'OpenAI live exécutés ; singleton checkpoints ; reprise manuelle après mort brutale d'un worker.
