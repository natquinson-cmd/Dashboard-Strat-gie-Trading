# Sécurisation de la base Firebase `portfolio-dashboard-f0c69`

Avant : base lisible et modifiable par n'importe qui (positions, transactions, patrimoine).
Après : tout est réservé au compte Google du propriétaire, sauf les exceptions ci-dessous.

## Qui accède comment

| Client | Accès après verrouillage |
|---|---|
| Dashboard trading, Partitions (SongBook) | connexion Google du propriétaire (même domaine `natquinson-cmd.github.io`) |
| Scripts du VPS (cours, screener, brief, synchro IG) | clé secrète `FIREBASE_DB_SECRET` (variable d'environnement système) |
| Pont IG (`darwinex-bridge`) | même clé (variable d'environnement, ou `config.json` firebase.secret) |
| Stream Deck (PC) | même clé (variable d'environnement utilisateur) |
| Jeux des enfants (`anacrossing`, `mathfoot`, `f1academy`) | ouverts, sans compte |
| Profils (`profil_psy`, `neuro_profil`) | écriture ouverte, lecture réservée au propriétaire |
| Site Axiom (`signalsLeads`) | création d'inscriptions seulement |
| Anciens : Dashboard Investissement, Mes-projets, `ig-sync.js` | cessent de fonctionner (plus utilisés) |

La clé secrète ne doit JAMAIS apparaître dans un fichier du dépôt (public) ni dans le chat.

## Fichiers

- `regles_firebase.json` : règles à publier (Realtime Database > Règles) (UID du propriétaire : `3TeVRklUsThrykDDWlGKM3S5IPK2`, compte Google natquinson@gmail.com).
- `regles_ouvertes_retour_arriere.json` : retour arrière immédiat en cas de problème.
