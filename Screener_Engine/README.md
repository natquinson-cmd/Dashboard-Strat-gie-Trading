# Screener Growth agressif (filtre Revolut)

Moteur qui balaye un univers d'actions US, applique des criteres de **croissance agressive + momentum**, ne garde que les titres **achetables sur Revolut**, et publie un **classement** que lit une page web legere.

Objectif : du **reperage** de candidates, pas du reporting de portefeuille (Revolut fait deja le reporting), pas du conseil d'investissement.

## Architecture

```
FMP (screener + quotes + fondamentaux, gratuit)          Cron 1x/jour
        │                                                     │
        ▼                                                     ▼
  Worker Cloudflare  ──►  filtre garde-fous + gate growth ──► score (percentiles) ──► KV "latest"
        │                         ▲                                                        │
   whitelist Revolut (KV)  ───────┘                                              Screener.html (GET /latest)
```

- **`worker/src/screen.js`** : coeur pur (garde-fous, gate, scoring par percentiles sectoriels). Testable sans cle.
- **`worker/src/providers.js`** : acces donnees (FMP principal, Yahoo en secours).
- **`worker/src/index.js`** : Worker (endpoints + cron + KV, rolling des fondamentaux).
- **`Screener.html`** : page resultats (lit le Worker, theme clair flat).
- **`data/revolut_whitelist.example.csv`** : format de la whitelist Revolut.

## Mise en place (gratuit)

Prerequis : Node.js, `npm i -g wrangler`, un compte Cloudflare, une **cle API gratuite FMP** (financialmodelingprep.com, plan Free 250 appels/jour).

```bash
cd Screener_Engine/worker
wrangler login

# 1) Cree le namespace KV et colle l'id renvoye dans wrangler.toml (champ id)
wrangler kv namespace create SCREENER

# 2) Secrets
wrangler secret put FMP_KEY      # ta cle gratuite FMP
wrangler secret put ADMIN_KEY    # un mot de passe que TU choisis (protege /run et /whitelist)

# 3) Deploie
wrangler deploy
```

### Charger la whitelist Revolut (optionnel mais recommande)

```bash
curl -X POST "https://stock-screener.TON-SOUS-DOMAINE.workers.dev/whitelist?key=TON_ADMIN_KEY" \
  --data-binary @../data/revolut_whitelist.example.csv
```

Sans whitelist, le moteur screene tout l'**US liquide** (bon proxy de Revolut) et tu confirmes la dispo dans l'app. Avec la whitelist, l'intersection est exacte. Voir "Obtenir la liste Revolut" plus bas.

### Premier classement (sans attendre le cron)

```bash
# dry-run (ne persiste pas) pour verifier que les donnees remontent :
open "https://stock-screener.xxx.workers.dev/run?key=TON_ADMIN_KEY&n=40&dry=1"
# vrai run qui persiste un premier classement :
open "https://stock-screener.xxx.workers.dev/run?key=TON_ADMIN_KEY&n=60"
```

### Page resultats

Ouvre `Screener.html`, clique **URL du moteur**, colle l'URL de ton Worker, **Rafraichir**.

## Fonctionnement au quotidien

Le cron (`0 6 * * 1-5`) tourne chaque jour ouvre :
- **momentum + liquidite** rafraichis pour tout l'univers (quotes en lot, peu d'appels) ;
- **fondamentaux** rafraichis en *rolling* (`FUND_CHUNK` tickers/jour, defaut 60), car ils ne bougent qu'au trimestre.

La **couverture** monte donc progressivement : avec 60 tickers/jour sur ~2000 titres, la couverture complete prend ~30 jours de bourse, puis tourne en boucle. Pour aller plus vite : passe un tier FMP superieur et monte `FUND_CHUNK`, ou lance `/run?n=...` plusieurs fois.

## Reglage des criteres

Tout est dans `worker/src/screen.js` -> `DEFAULT_CONFIG` : garde-fous (cap, prix, volume, dilution, dette, exception BPA<0), plancher growth, seuils de flags, **poids du score** (momentum 32 %, croissance CA 25 %, BPA 20 %, qualite 15 %, volume 8 %). Modifie, `wrangler deploy`, relance `/run`.

Variables non secretes (dans `wrangler.toml`) : `MIN_MARKET_CAP`, `MIN_VOLUME`, `MAX_UNIVERSE`, `FUND_CHUNK`, `QUOTE_CHUNK`, `ENABLE_YAHOO_FALLBACK`, `ENABLE_PRICE_CHANGE`.

## Test local (sans cle)

```bash
node worker/test/local_test.mjs
```

Valide la logique de filtrage + scoring sur un univers fictif (garde-fous, exception BPA negatif, penalite momentum, tri).

## Obtenir la liste Revolut

Revolut n'a **ni API ni liste officielle** telechargeable. Le catalogue = ~2000-3000 valeurs liquides curees (surtout US), beaucoup de small caps **absentes** (c'est attendu, ton screener en perdra a l'intersection). Options, du plus fidele au plus simple :
1. **Capture reseau de l'app** sur ton propre compte (proxy type mitmproxy) -> la source de verite, mais non officielle.
2. **Liste tierce** consolidee (a defaut, vite perimee, souvent US-only).
3. **Sans whitelist** : proxy "US liquide" + verif finale dans l'app (le top est court, ~40 noms).

Traite la whitelist comme un **CSV que tu rafraichis tous les 1-3 mois**. Format : une colonne `ticker` (ou une simple liste), un ticker par ligne.

## Limites honnetes (tier gratuit)

- FMP Free = 250 appels/jour : d'ou le rolling des fondamentaux (couverture progressive).
- Les **noms de champs FMP** ou le **gating** de certains endpoints (financial-growth, ratios-ttm) peuvent varier selon le plan. Si `/run` renvoie des `null` sur la croissance/les marges : active `ENABLE_YAHOO_FALLBACK=true` (fallback Yahoo, non officiel, fragile) ou passe un petit tier FMP payant (~25 $/mois) avec endpoints bulk.
- Le quote en lot suppose que FMP accepte plusieurs symboles par appel ; sinon reduire `QUOTE_CHUNK`.
- Yahoo (fallback) est un endpoint **non officiel**, cassable, et peut etre limite depuis les IP Cloudflare.

## Avertissement

Outil de reperage quantitatif. **Pas** un conseil d'investissement, **pas** une incitation a acheter. Verifie chaque titre dans Revolut et fais ta propre analyse. Le growth agressif implique des valorisations elevees et un risque de perte accru.
