// Flux temps reel IG (Lightstreamer) : prix des indices et P&L ouvert du compte.
// Identifiants dans ig_config.json (a remplir par le user, ignore par git, jamais journalise).
// Lecture seule : aucune requete d'ordre, seulement /session, /positions et le flux.
'use strict';
const fs = require('fs');
const path = require('path');
const { LightstreamerClient, Subscription } = require('lightstreamer-client-node');

const CONFIG_FILE = path.join(__dirname, 'ig_config.json');
const API = 'https://api.ig.com/gateway/deal';
// CFD « cash » IG : suivent l'indice au comptant en seance et les futures en dehors
const DEFAULT_EPICS = { dax: 'IX.D.DAX.DAILY.IP', ndx: 'IX.D.NASDAQ.IFE.IP', spx: 'IX.D.SPTRD.DAILY.IP' };

function createIgFeed(log, onChange) {
  const state = {
    status: 'off',        // off | connexion | ok | erreur
    error: null,
    prices: {},           // nom -> { mid, pct, marketState, at }
    account: null,        // { pnl, equity, at }
    positions: null,      // { count, at }
  };
  let cfg = null, session = null, client = null, posTimer = null, retryTimer = null, stopped = false;

  function fail(msg) {
    state.status = 'erreur'; state.error = msg;
    log('IG : ' + msg);
    onChange();
    if (!stopped && !retryTimer) retryTimer = setTimeout(() => { retryTimer = null; start(); }, 120000);   // nouvel essai dans 2 min
  }

  async function rest(p, opts) {
    const headers = { 'X-IG-API-KEY': cfg.apiKey, Accept: 'application/json; charset=UTF-8', 'Content-Type': 'application/json; charset=UTF-8', Version: (opts && opts.version) || '2' };
    if (session) { headers.CST = session.cst; headers['X-SECURITY-TOKEN'] = session.xst; }
    const r = await fetch(API + p, { method: (opts && opts.method) || 'GET', headers, body: opts && opts.body ? JSON.stringify(opts.body) : undefined, signal: AbortSignal.timeout(20000) });
    const txt = await r.text();
    if (!r.ok) {
      let code = txt.slice(0, 120);
      try { code = JSON.parse(txt).errorCode || code; } catch (e) { /* texte brut */ }
      const err = new Error('HTTP ' + r.status + ' ' + code);
      err.status = r.status;
      throw err;
    }
    return { headers: r.headers, body: txt ? JSON.parse(txt) : {} };
  }

  async function login() {
    session = null;
    const r = await rest('/session', { method: 'POST', body: { identifier: cfg.username, password: cfg.password } });
    session = {
      cst: r.headers.get('cst'), xst: r.headers.get('x-security-token'),
      accountId: cfg.accountId || r.body.currentAccountId,
      endpoint: r.body.lightstreamerEndpoint,
    };
    if (!session.cst || !session.xst) throw new Error('jetons de session absents');
  }

  // Nombre de positions ouvertes : 1 requete par minute (le pont en fait deja 12, IG en tolere bien plus).
  async function pollPositions() {
    try {
      const b = (await rest('/positions')).body;
      state.positions = { count: (b.positions || []).length, at: Date.now() };
      onChange();
    } catch (e) {
      if (e.status === 401 || e.status === 403) { restart('session expirée'); return; }
      log('IG positions : ' + e.message);
    }
  }

  function subscribe() {
    const me = client = new LightstreamerClient(session.endpoint, 'DEFAULT');
    client.connectionDetails.setUser(session.accountId);
    client.connectionDetails.setPassword('CST-' + session.cst + '|XST-' + session.xst);
    client.addListener({
      onStatusChange(s) {
        if (client !== me) return;   // ancien client en cours de fermeture
        if (s.startsWith('CONNECTED:')) { if (state.status !== 'ok') { state.status = 'ok'; state.error = null; log('IG : flux connecté (' + s + ')'); onChange(); } }
        else if (s === 'DISCONNECTED' && !stopped) fail('flux coupé');
      },
      onServerError(code, msg) { if (client === me) fail('serveur de flux ' + code + ' ' + msg); },
    });

    const epics = Object.assign({}, DEFAULT_EPICS, cfg.epics || {});
    const names = Object.keys(epics);
    const mkt = new Subscription('MERGE', names.map(n => 'MARKET:' + epics[n]), ['BID', 'OFFER', 'CHANGE_PCT', 'MARKET_STATE']);
    mkt.addListener({
      onItemUpdate(u) {
        const n = names[u.getItemPos() - 1];
        const bid = parseFloat(u.getValue('BID')), offer = parseFloat(u.getValue('OFFER'));
        if (!isFinite(bid) || !isFinite(offer)) return;
        state.prices[n] = { mid: (bid + offer) / 2, pct: parseFloat(u.getValue('CHANGE_PCT')) || 0, marketState: u.getValue('MARKET_STATE'), at: Date.now(), epic: epics[n] };
        onChange();
      },
      onSubscriptionError(code, msg) { log('IG abonnement prix : ' + code + ' ' + msg); },
      onItemLostUpdates() {},
    });
    client.subscribe(mkt);

    const acc = new Subscription('MERGE', ['ACCOUNT:' + session.accountId], ['PNL', 'EQUITY']);
    acc.addListener({
      onItemUpdate(u) {
        const pnl = parseFloat(u.getValue('PNL')), equity = parseFloat(u.getValue('EQUITY'));
        state.account = { pnl: isFinite(pnl) ? pnl : 0, equity: isFinite(equity) ? equity : null, at: Date.now() };
        onChange();
      },
      onSubscriptionError(code, msg) { log('IG abonnement compte : ' + code + ' ' + msg); },
    });
    client.subscribe(acc);
    client.connect();
  }

  function stopClient() {
    if (posTimer) { clearInterval(posTimer); posTimer = null; }
    if (client) { try { client.disconnect(); } catch (e) { /* deja coupe */ } client = null; }
  }
  function restart(why) { log('IG : reconnexion (' + why + ')'); stopClient(); start(); }

  async function start() {
    stopClient();
    try { cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')); }
    catch (e) { state.status = 'off'; state.error = 'ig_config.json absent'; onChange(); return; }
    if (!cfg.apiKey || !cfg.username || !cfg.password || /^TA_|^TON_/.test(cfg.apiKey + cfg.username)) {
      state.status = 'off'; state.error = 'ig_config.json à remplir'; onChange(); return;
    }
    state.status = 'connexion'; onChange();
    try { await login(); }
    catch (e) { fail('connexion refusée : ' + e.message); return; }
    subscribe();
    pollPositions();
    posTimer = setInterval(pollPositions, 60000);
  }

  // Les jetons IG expirent apres ~6 h : reconnexion preventive toutes les 5 h.
  setInterval(() => { if (state.status === 'ok') restart('renouvellement de session'); }, 5 * 3600000);

  return { state, start, stop() { stopped = true; stopClient(); } };
}

module.exports = { createIgFeed };
