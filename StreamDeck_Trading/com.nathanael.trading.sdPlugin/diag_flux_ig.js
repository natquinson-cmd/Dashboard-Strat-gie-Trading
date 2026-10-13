// Diagnostic ponctuel du flux de prix IG (lecture seule, une connexion, 25 s) : quels formats d'abonnement
// IG accepte-t-il pour un indice ? Lance a la main : node diag_flux_ig.js. N'affiche jamais les identifiants.
'use strict';
const fs = require('fs');
const path = require('path');
const { LightstreamerClient, Subscription } = require('lightstreamer-client-node');
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'ig_config.json'), 'utf8'));
const EPIC = 'IX.D.DAX.IFMM.IP';

(async () => {
  const r = await fetch('https://api.ig.com/gateway/deal/session', {
    method: 'POST', body: JSON.stringify({ identifier: cfg.username, password: cfg.password }),
    headers: { 'X-IG-API-KEY': cfg.apiKey, Version: '2', 'Content-Type': 'application/json; charset=UTF-8', Accept: 'application/json; charset=UTF-8' },
  });
  const b = await r.json();
  if (!r.ok) { console.log('login refuse', r.status, b.errorCode); return; }
  const acc = b.currentAccountId, cst = r.headers.get('cst'), xst = r.headers.get('x-security-token');
  console.log('login ok, endpoint', b.lightstreamerEndpoint);
  const client = new LightstreamerClient(b.lightstreamerEndpoint, 'DEFAULT');
  client.connectionDetails.setUser(acc);
  client.connectionDetails.setPassword('CST-' + cst + '|XST-' + xst);
  const essai = (nom, mode, items, fields, adapter) => {
    const s = new Subscription(mode, items, fields);
    if (adapter) s.setDataAdapter(adapter);
    let n = 0;
    s.addListener({
      onSubscription() { console.log(nom, ': abonnement accepte'); },
      onSubscriptionError(c, m) { console.log(nom, ': REFUSE', c, m); },
      onItemUpdate(u) { if (n++ < 2) console.log(nom, ': prix recu', fields.map(f => f + '=' + u.getValue(f)).join(' ')); },
    });
    client.subscribe(s);
  };
  client.addListener({ onStatusChange(s) { console.log('statut', s); } });
  client.connect();
  essai('MARKET (actuel)', 'MERGE', ['MARKET:' + EPIC], ['BID', 'OFFER', 'CHANGE_PCT', 'MARKET_STATE']);
  essai('MARKET 2 champs', 'MERGE', ['MARKET:' + EPIC], ['BID', 'OFFER']);
  essai('PRICE (Pricing)', 'MERGE', ['PRICE:' + acc + ':' + EPIC], ['BIDPRICE1', 'ASKPRICE1', 'TIMESTAMP'], 'Pricing');
  essai('CHART tick', 'DISTINCT', ['CHART:' + EPIC + ':TICK'], ['BID', 'OFR', 'UTM']);
  setTimeout(() => { client.disconnect(); console.log('fin'); process.exit(0); }, 25000);
})().catch(e => console.log('erreur', e.message));
