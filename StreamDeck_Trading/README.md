# Stream Deck Trading

Plugin Stream Deck (15 touches) branché sur le Trading Dashboard.

## Touches en direct (rangée du haut)
| Touche | Affiche | Appui |
|---|---|---|
| CAPITAL | Capital total IG + actions + Darwinex, % de P&L cumulé | ouvre le dashboard |
| P&L JOUR | P&L du jour toutes sources | mise à jour immédiate |
| P&L MOIS | P&L du mois en cours, % du capital de début de mois | ouvre le dashboard |
| PONT IG | OK / LENT / MUET / KO selon l'âge du dernier signal du pont | fenêtre de détail (pont + synchro IG) |
| IDÉE | nombre d'idées notées aujourd'hui | fenêtre de saisie, ajout dans `Idees_Trading.md` |

## Fonctionnement
- `engine.js` extrait (acorn) les fonctions de `Trading_Dashboard.html` et les exécute dans un bac à sable
  avec les données Firebase : mêmes chiffres que l'onglet Trading total, sans recopier les formules.
- Lecture seule, rafraîchi toutes les 60 s. En cas d'échec : dernier chiffre gardé, barre orange, « figé HH:MM », raison dans `plugin.log`.
- Pont IG : jamais vert par défaut. Vert si signal < 20 min, orange si < 60 min ou MT5 déconnecté, rouge au-delà (gris le week-end).
- Après verrouillage des règles Firebase : définir la variable d'environnement `FIREBASE_DB_SECRET`.

## Installation
Le dossier `com.nathanael.trading.sdPlugin` est lié (jonction) dans `%APPDATA%\Elgato\StreamDeck\Plugins\`.
Après une modification : `npm install` dans le dossier du plugin si besoin, puis redémarrer le logiciel Stream Deck.
