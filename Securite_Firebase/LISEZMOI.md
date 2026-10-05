# Sécurisation de la base Firebase `portfolio-dashboard-f0c69`

Avant : base lisible et modifiable par n'importe qui (positions, transactions, patrimoine).
Après : tout est réservé au compte Google du propriétaire, sauf les exceptions ci-dessous.

## Qui accède comment

| Client | Accès après verrouillage |
|---|---|
| Dashboard trading, Partitions (SongBook) | connexion Google du propriétaire (même domaine `natquinson-cmd.github.io`) |
| Personnes ajoutées par le propriétaire (liste `acces`) | connexion Google : niveau `lecture` (tout voir) ou `complet` (tout voir et modifier), jamais la liste des accès |
| Scripts du VPS (cours, screener, brief, synchro IG) | clé secrète `FIREBASE_DB_SECRET` (variable d'environnement système) |
| Pont IG (`darwinex-bridge`) | même clé (variable d'environnement, ou `config.json` firebase.secret) |
| Stream Deck (PC) | même clé (variable d'environnement utilisateur) |
| Jeux des enfants (`anacrossing`, `mathfoot`, `f1academy`) | ouverts, sans compte |
| Profils (`profil_psy`, `neuro_profil`) | écriture ouverte, lecture réservée au propriétaire |
| Site Axiom (`signalsLeads`) | création d'inscriptions seulement |
| Anciens : Dashboard Investissement, Mes-projets, `ig-sync.js` | cessent de fonctionner (plus utilisés) |

La clé secrète ne doit JAMAIS apparaître dans un fichier du dépôt (public) ni dans le chat.

## Fichiers

- `regles_firebase.json` : règles à publier (Realtime Database > Règles) (UID du propriétaire : `3TeVRklUsThrykDDWlGKM3S5IPK2`).
- `regles_ouvertes_retour_arriere.json` : retour arrière immédiat en cas de problème.

## Poser la clé secrète (avant de publier les règles)

La clé se copie dans la console Firebase : Paramètres du projet, Comptes de service, Codes secrets de la base de données, Afficher.
Elle ne passe jamais par le chat, un fichier du dépôt ou la page.

1. **VPS**, CMD lancé en administrateur : `setx /M FIREBASE_DB_SECRET "la_cle"`, puis `git pull` dans le dossier du screener, `update.bat` du pont (hors position ouverte), redémarrage du VPS.
2. **VPS**, après le redémarrage : double-clic sur `Screener_Engine\ibkr_vps\verifier_cle.bat`, qui doit afficher `OK : cle valide`.
3. **PC** (Stream Deck), CMD normal : `setx FIREBASE_DB_SECRET "la_cle"`, puis quitter complètement Stream Deck (icône près de l'horloge) et le relancer. Test : `python Screener_Engine\ibkr_vps\verifier_cle.py` dans une nouvelle fenêtre.

Le test lit les règles de la base, lecture que seule la clé administrateur autorise : il distingue une clé valide d'une clé fausse même tant que la base est ouverte.

## Donner ou retirer un accès (sans toucher aux règles)

1. La personne ouvre le dashboard et se connecte avec son compte Google : l'écran « n'a pas encore accès » s'affiche et une demande est déposée (`demandesAcces/{uid}`).
2. Un badge apparaît sur ton bouton de compte (initiale en haut à droite) : clic, « Lecture » ou « Complet ». Sa page s'ouvre toute seule.
3. Changer de niveau ou retirer : même menu, « Passer en lecture / en complet » ou « Retirer » en face de la personne.

Lecture : tout voir, rien modifier (les règles refusent l'écriture ; le dashboard affiche « Lecture seule »). Complet : tout voir, tout modifier, Partitions compris. Une entrée sans niveau vaut lecture. Dans les deux cas, la liste des accès reste réservée au propriétaire.
