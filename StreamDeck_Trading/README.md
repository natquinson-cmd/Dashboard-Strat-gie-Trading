# Stream Deck Trading

Plugin Stream Deck (15 touches) branché sur le Trading Dashboard.

## Touches en direct (rangée du haut)
| Touche | Affiche | Appui |
|---|---|---|
| CAPITAL | Capital total IG + actions + Darwinex, % de P&L cumulé | ouvre le dashboard |
| P&L JOUR | P&L du jour toutes sources | mise à jour immédiate |
| P&L MOIS | P&L du mois en cours, % du capital de début de mois | ouvre le dashboard |
| PONT IG | OK / LENT / MUET / KO selon l'âge du dernier signal du pont | fenêtre de détail (pont + synchro IG) |
| ENFANTS | valeur de la poche VWCE des enfants (parts x cours), % sur versé | fenêtre de détail par enfant |

## Indices en direct (2e rangée, Yahoo, toutes les 20 s)
DAX, Nasdaq 100, S&P 500 : variation du jour en gros et en couleur, courbe de la séance (même couleur, pointillé = clôture de la veille,
l axe couvre toute la séance donc la courbe avance dans la journée), cours en petit en bas. Couleur de la barre du haut
gris et « clôt. » en dehors. Appui : graphique TradingView dans Chrome.

## Fonctionnement
- Les liens s'ouvrent dans Chrome (repli sur le navigateur par défaut si Chrome est absent).
- `engine.js` extrait (acorn) les fonctions de `Trading_Dashboard.html` et les exécute dans un bac à sable
  avec les données Firebase : mêmes chiffres que l'onglet Trading total, sans recopier les formules.
- Lecture seule, rafraîchi toutes les 60 s. En cas d'échec : dernier chiffre gardé, barre orange, « figé HH:MM », raison dans `plugin.log`.
- Pont IG : jamais vert par défaut. Vert si signal < 20 min, orange si < 60 min ou MT5 déconnecté, rouge au-delà (gris le week-end).
- Après verrouillage des règles Firebase : définir la variable d'environnement `FIREBASE_DB_SECRET`.

## Installation
Le dossier `com.nathanael.trading.sdPlugin` est lié (jonction) dans `%APPDATA%\Elgato\StreamDeck\Plugins\`.
Après une modification : `npm install` dans le dossier du plugin si besoin, puis redémarrer le logiciel Stream Deck.

## Flux IG temps réel (`ig.js`)
- Copier `ig_config.example.json` en `ig_config.json` et y mettre ses identifiants IG (ceux du pont). Fichier ignoré par git, jamais journalisé.
- Connexion `/session`, puis flux Lightstreamer : `MARKET:<epic>` (BID, OFFER, CHANGE_PCT) pour DAX / Nasdaq 100 / S&P 500, `ACCOUNT:<id>` (PNL) pour le P&L latent. `/positions` lu à la connexion, puis seulement quand le flux `TRADE:<id>` (OPU) annonce une ouverture/fermeture, et toutes les 5 min par sécurité. Aucune requête d'ordre.
- Affichage redessiné au plus 1 fois par seconde. Point bleu sur une touche d'indice = prix IG en direct (sinon repli Yahoo).
- Touche ALGOS LIVE : P&L latent des positions ouvertes (en direct), flèche de sens (verte achat, rouge vente) et instrument, réalisé du jour (trades synchronisés dans le dashboard). Appui : onglet Trading Auto.
- Session renouvelée toutes les 5 h ; en cas d'échec, nouvel essai toutes les 2 min, raison affichée sur la touche et dans `plugin.log`.

## Lancement au branchement (pas au démarrage de Windows)
- L'entrée « Stream Deck » de `HKCU\...\CurrentVersion\Run` a été retirée (valeur d'origine dans `run_entry_origine.txt`).
- Tâche planifiée « Stream Deck - lancement au branchement » (`tache_lancement_au_branchement.xml`) : déclenchée par l'événement
  Kernel-PnP 410 (un périphérique démarre) et à l'ouverture de session. Elle lance `lancer_si_branche.vbs` → `.ps1`, qui ne démarre
  le logiciel que si un périphérique Elgato (`USB\VID_0FD9`) est présent et que le logiciel ne tourne pas déjà.
- Retour arrière : `schtasks /Delete /TN "Stream Deck - lancement au branchement" /F`, puis réactiver « Lancer au démarrage » dans les préférences Stream Deck.
