// Plugin Stream Deck « Trading Nathanaël » : touches en direct branchées sur le dashboard.
// Protocole Stream Deck brut (WebSocket), sans SDK : le logiciel lance ce script avec
// -port, -pluginUUID, -registerEvent, -info.
'use strict';
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const WebSocket = require('ws');
const { compute } = require('./engine');

const CONFIG = {
  dashboardPath: 'C:/Users/quinson/Desktop/Claude/Trading_Dashboard.html',
  dashboardUrl: 'https://natquinson-cmd.github.io/Dashboard-Strat-gie-Trading/',
  refreshMs: 60000,
  indexRefreshMs: 20000,
};
const LOG = path.join(__dirname, 'plugin.log');
function log(msg) {
  try {
    const line = new Date().toISOString() + ' ' + msg + '\n';
    if (fs.existsSync(LOG) && fs.statSync(LOG).size > 500000) fs.writeFileSync(LOG, '');
    fs.appendFileSync(LOG, line);
  } catch (e) { /* rien */ }
}

const args = {};
for (let i = 2; i < process.argv.length - 1; i += 2) args[process.argv[i].replace(/^-/, '')] = process.argv[i + 1];

// ── Rendu des touches (SVG 144 x 144) ─────────────────────────────────────
const C = { bg: '#0f1720', txt: '#e8edf3', dim: '#8a97a8', pos: '#22c38e', neg: '#ff5c66', warn: '#f5a524', gray: '#5b6776', blue: '#4a8cff' };
const esc = s => String(s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
function key({ label, value, sub, color, accent, valueSize }) {
  const vs = valueSize || (String(value).length > 8 ? 26 : String(value).length > 6 ? 31 : 36);
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">'
    + '<rect width="144" height="144" fill="' + C.bg + '"/>'
    + '<rect x="0" y="0" width="144" height="8" fill="' + (accent || color || C.gray) + '"/>'
    + '<text x="72" y="36" text-anchor="middle" font-family="Segoe UI, Arial" font-size="17" font-weight="700" fill="' + C.dim + '">' + esc(label) + '</text>'
    + '<text x="72" y="' + (84 + (36 - vs) / 3) + '" text-anchor="middle" font-family="Segoe UI, Arial" font-size="' + vs + '" font-weight="800" fill="' + (color || C.txt) + '">' + esc(value) + '</text>'
    + (sub ? '<text x="72" y="122" text-anchor="middle" font-family="Segoe UI, Arial" font-size="17" font-weight="600" fill="' + C.dim + '">' + esc(sub) + '</text>' : '')
    + '</svg>';
  return 'data:image/svg+xml;charset=utf8,' + encodeURIComponent(svg);
}

const nf0 = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const eur = v => (Math.abs(v) >= 10000 ? nf1.format(v / 1000) + ' k€' : nf0.format(Math.round(v)) + ' €').replace(/\u202f/g, ' ');
const sEur = v => (v > 0 ? '+' : '') + eur(v);
const sPct = v => (v > 0 ? '+' : '') + nf2.format(v) + ' %';
const col = v => Math.abs(v) < 0.5 ? C.txt : (v > 0 ? C.pos : C.neg);
const hhmm = t => { const d = new Date(t); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); };
const MOIS = ['JANV.', 'FÉVR.', 'MARS', 'AVRIL', 'MAI', 'JUIN', 'JUIL.', 'AOÛT', 'SEPT.', 'OCT.', 'NOV.', 'DÉC.'];
function ago(ms) {
  const m = Math.round(ms / 60000);
  if (m < 1) return "à l'instant";
  if (m < 60) return 'il y a ' + m + ' min';
  const h = Math.round(m / 60);
  return h < 48 ? 'il y a ' + h + ' h' : 'il y a ' + Math.round(h / 24) + ' j';
}

let data = null, lastError = null, busy = false, firstOk = false;

// Une touche de chiffres : si la derniere mise a jour a echoue, on garde le dernier chiffre connu
// mais la barre passe a l'orange et le bas dit depuis quand ; sans chiffre du tout, on affiche la raison.
function staleOr(render) {
  if (!data) return key({ label: 'ERREUR', value: lastError ? 'échec' : '…', sub: lastError ? lastError.slice(0, 16) : 'chargement', color: lastError ? C.neg : C.dim });
  const img = render();
  return img;
}
const RENDER = {
  capital() {
    return staleOr(() => key({
      label: 'CAPITAL', value: eur(data.capTotal),
      sub: lastError ? 'figé ' + hhmm(data.computedAt) : sPct(data.pnlPct),
      color: C.txt, accent: lastError ? C.warn : col(data.pnlTotal),
    }));
  },
  pnljour() {
    return staleOr(() => {
      const t = data.today.total, base = data.capTotal - t;
      return key({ label: 'P&L JOUR', value: Math.abs(t) < 0.5 ? '0 €' : sEur(t),
        sub: lastError ? 'figé ' + hhmm(data.computedAt) : (base > 0 ? sPct(t / base * 100) : ''),
        color: col(t), accent: lastError ? C.warn : col(t) });
    });
  },
  pnlmois() {
    return staleOr(() => {
      const t = data.month.total;
      return key({ label: 'P&L ' + MOIS[new Date().getMonth()], value: sEur(t),
        sub: lastError ? 'figé ' + hhmm(data.computedAt) : (data.monthBase > 0 ? sPct(t / data.monthBase * 100) : ''),
        color: col(t), accent: lastError ? C.warn : col(t) });
    });
  },
  // Pont IG : jamais vert par defaut, la couleur se juge sur l'age du dernier signal.
  pont() {
    if (!data || !data.pont) return key({ label: 'PONT IG', value: '?', sub: lastError ? lastError.slice(0, 16) : 'chargement', color: C.gray });
    const p = data.pont, age = Date.now() - new Date(p.at).getTime();
    const dow = new Date().getDay(), weekend = dow === 0 || dow === 6;
    let color, value;
    if (!p.ok) { color = C.neg; value = 'KO'; }
    else if (!isFinite(age)) { color = C.neg; value = '?'; }
    else if (age > 60 * 60000) { color = weekend ? C.gray : C.neg; value = weekend ? 'PAUSE' : 'MUET'; }
    else if (age > 20 * 60000 || !p.mt5Connected) { color = C.warn; value = p.mt5Connected ? 'LENT' : 'MT5 OFF'; }
    else { color = C.pos; value = 'OK'; }
    if (p.dryRun && color === C.pos) value = 'TEST';
    return key({ label: 'PONT IG', value, sub: isFinite(age) ? ago(age) : '', color, accent: color });
  },
  // Poche enfants (VWCE en parts), separee du capital personnel.
  enfants() {
    if (!data || !data.kids) return key({ label: 'ENFANTS', value: '?', sub: lastError ? lastError.slice(0, 16) : 'chargement', color: C.gray });
    const k = data.kids;
    return key({ label: 'ENFANTS', value: eur(k.value), sub: lastError ? 'figé ' + hhmm(data.computedAt) : sPct(k.pct),
      color: C.txt, accent: lastError ? C.warn : col(k.pnl) });
  },
  dax: () => renderIndex('dax'),
  ndx: () => renderIndex('ndx'),
  spx: () => renderIndex('spx'),
};

// ── Indices en direct (Yahoo Finance, cours du marché au comptant) ─────────
const INDICES = {
  dax: { symbol: '^GDAXI', label: 'DAX', tv: 'XETR:DAX' },
  ndx: { symbol: '^NDX', label: 'NASDAQ 100', tv: 'NASDAQ:NDX' },
  spx: { symbol: '^GSPC', label: 'S&P 500', tv: 'SP:SPX' },
};
const quotes = {};   // nom -> { price, pct, at } ou { error }
const nfIdx = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
async function fetchIndex(name) {
  const r = await fetch('https://query1.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(INDICES[name].symbol) + '?interval=1m&range=1d',
    { headers: { 'User-Agent': 'Mozilla/5.0' }, signal: AbortSignal.timeout(10000) });
  if (!r.ok) throw new Error('Yahoo HTTP ' + r.status);
  const m = (((await r.json()).chart || {}).result || [])[0];
  if (!m || !m.meta || m.meta.regularMarketPrice == null) throw new Error('cours absent');
  const prev = m.meta.chartPreviousClose || m.meta.previousClose;
  const pct = m.meta.regularMarketChangePercent != null ? m.meta.regularMarketChangePercent : (prev ? (m.meta.regularMarketPrice / prev - 1) * 100 : 0);
  const reg = (m.meta.currentTradingPeriod || {}).regular || {};
  // courbe de la seance : points minute (sans les trous), ramenes a 72 points max
  const ts = m.timestamp || [], cl = ((m.indicators || {}).quote || [{}])[0].close || [];
  let pts = [];
  for (let i = 0; i < ts.length; i++) if (cl[i] != null && isFinite(cl[i])) pts.push([ts[i] * 1000, cl[i]]);
  if (pts.length > 72) { const step = pts.length / 72; pts = Array.from({ length: 72 }, (_, i) => pts[Math.min(pts.length - 1, Math.round((i + 1) * step) - 1)]); }
  return { price: m.meta.regularMarketPrice, pct, prev, pts, at: m.meta.regularMarketTime * 1000, open: reg.start ? reg.start * 1000 : null, close: reg.end ? reg.end * 1000 : null };
}
async function refreshIndices() {
  await Promise.all(Object.keys(INDICES).map(async n => {
    try { quotes[n] = await fetchIndex(n); }
    catch (e) {
      if (!quotes[n] || !quotes[n].price) quotes[n] = { error: String(e.message || e) };
      else quotes[n].failed = true;
      log('indice ' + n + ' : ' + (e.message || e));
    }
  }));
  for (const [c, n] of contexts) if (INDICES[n]) paint(c);
}
// Ouvert = dans les horaires de seance de la place (Yahoo diffuse le DAX avec ~15 min de retard, l'age du cours ne suffit pas).
// Mise en page : la variation du jour en gros et en couleur, la courbe de la seance (meme couleur, ligne
// pointillee = cloture de la veille), le cours en petit en bas.
function renderIndex(name) {
  const q = quotes[name], lab = INDICES[name].label;
  if (!q) return key({ label: lab, value: '…', sub: 'chargement', color: C.dim });
  if (q.error) return key({ label: lab, value: '?', sub: q.error.slice(0, 16), color: C.neg, accent: C.neg });
  const now = Date.now();
  const live = !q.failed && (q.open && q.close ? now >= q.open && now <= q.close : now - q.at < 20 * 60000);
  const color = Math.abs(q.pct) < 0.005 ? C.txt : (q.pct > 0 ? C.pos : C.neg);
  const F = 'font-family="Segoe UI, Arial"';
  let chart = '';
  const pts = q.pts || [];
  if (pts.length > 1) {
    const X0 = 6, X1 = 138, Y0 = 66, Y1 = 116;
    // en seance : l'axe couvre toute la seance, la courbe avance au fil de la journee
    const last = pts[pts.length - 1][0];
    const inSession = q.open && q.close && last >= q.open && last <= q.close;
    const t0 = inSession ? q.open : pts[0][0], t1 = inSession ? q.close : last;
    const vals = pts.map(p => p[1]).concat(q.prev ? [q.prev] : []);
    const lo = Math.min(...vals), hi = Math.max(...vals), span = (hi - lo) || 1;
    const x = t => X0 + (X1 - X0) * Math.max(0, Math.min(1, (t - t0) / ((t1 - t0) || 1)));
    const y = v => Y1 - (Y1 - Y0) * (v - lo) / span;
    const line = pts.map(p => x(p[0]).toFixed(1) + ',' + y(p[1]).toFixed(1)).join(' ');
    const base = y(q.prev || pts[0][1]).toFixed(1);
    chart = '<polygon points="' + x(pts[0][0]).toFixed(1) + ',' + base + ' ' + line + ' ' + x(last).toFixed(1) + ',' + base + '" fill="' + color + '" fill-opacity="0.18"/>'
      + '<line x1="' + X0 + '" y1="' + base + '" x2="' + X1 + '" y2="' + base + '" stroke="' + C.dim + '" stroke-width="1.5" stroke-dasharray="3 3" opacity="0.7"/>'
      + '<polyline points="' + line + '" fill="none" stroke="' + color + '" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>';
  }
  const pctTxt = sPct(q.pct).replace(' %', '%');
  const bottom = nfIdx.format(q.price).replace(/\s/g, ' ') + (live ? '' : q.failed ? ' · figé' : ' · clôt.');
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">'
    + '<rect width="144" height="144" fill="' + C.bg + '"/>'
    + '<rect x="0" y="0" width="144" height="6" fill="' + (live ? color : C.gray) + '"/>'
    + '<text x="72" y="25" text-anchor="middle" ' + F + ' font-size="15" font-weight="700" fill="' + C.dim + '">' + esc(lab) + '</text>'
    + '<text x="72" y="58" text-anchor="middle" ' + F + ' font-size="' + (pctTxt.length > 7 ? 28 : 32) + '" font-weight="800" fill="' + color + '">' + esc(pctTxt) + '</text>'
    + chart
    + '<text x="72" y="137" text-anchor="middle" ' + F + ' font-size="15" font-weight="600" fill="' + C.dim + '">' + esc(bottom) + '</text>'
    + '</svg>';
  return 'data:image/svg+xml;charset=utf8,' + encodeURIComponent(svg);
}

// ── Connexion au logiciel Stream Deck ─────────────────────────────────────
const contexts = new Map();   // context -> nom de l'action
const ws = new WebSocket('ws://127.0.0.1:' + args.port);
const send = o => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(o)); };
const actionName = uuid => uuid.split('.').pop();

function paint(ctx) {
  const name = contexts.get(ctx);
  if (!RENDER[name]) return;
  try { send({ event: 'setImage', context: ctx, payload: { image: RENDER[name](), target: 0 } }); }
  catch (e) { log('rendu ' + name + ' : ' + e.message); }
}
const paintAll = () => { for (const c of contexts.keys()) paint(c); };

async function refresh() {
  if (busy) return;
  busy = true;
  try {
    data = await compute(CONFIG);
    if (lastError || !firstOk) log('mise a jour ok : capital ' + Math.round(data.capTotal) + ' EUR, jour ' + Math.round(data.today.total) + ' EUR, ' + contexts.size + ' touche(s)');
    firstOk = true;
    lastError = null;
  } catch (e) {
    lastError = String(e && e.message || e);
    log('echec mise a jour : ' + (e && e.stack || e));
  } finally {
    busy = false;
    paintAll();
  }
}

// Petites fenetres Windows. Le texte passe par une variable d'environnement, jamais dans la commande.
function psRun(script, env) {
  return new Promise(resolve => {
    const p = spawn('powershell.exe', ['-NoProfile', '-STA', '-WindowStyle', 'Hidden', '-Command', script],
      { env: Object.assign({}, process.env, env || {}), windowsHide: true });
    let out = '';
    p.stdout.on('data', d => { out += d; });
    p.on('close', () => resolve(out));
    p.on('error', e => { log('powershell : ' + e.message); resolve(''); });
  });
}
const popup = (title, msg) => psRun('Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show($env:SD_MSG, $env:SD_TITLE)', { SD_MSG: msg, SD_TITLE: title });

function kidsDetails() {
  const k = data && data.kids;
  if (!k) return popup('Poche enfants', lastError ? 'Échec de lecture : ' + lastError : 'Chargement en cours.');
  const e = v => eur(v), sgn = v => (v > 0 ? '+' : '') + eur(v);
  const lines = ['Poche enfants : ' + k.ticker + ' à ' + nf2.format(k.price) + ' € (cours de ' + hhmm(k.priceAt) + ')', ''];
  k.children.forEach(c => lines.push(c.child + ' : ' + e(c.value) + '   (versé ' + e(c.paid) + ', ' + sgn(c.value - c.paid) + ', ' + nf2.format(c.units) + ' parts)'));
  lines.push('', 'Total : ' + e(k.value) + ', versé ' + e(k.paid) + ', ' + sgn(k.pnl) + ' (' + sPct(k.pct) + ')');
  return popup('Poche enfants', lines.join('\n'));
}

function pontDetails() {
  if (!data) return popup('Pont IG', lastError ? 'Échec de lecture : ' + lastError : 'Chargement en cours.');
  const p = data.pont || {}, s = data.igSync || {};
  const lines = [
    'Pont IG / MT5',
    '  Dernier signal : ' + (p.at ? new Date(p.at).toLocaleString('fr-FR') : '?'),
    '  État : ' + (p.ok ? 'ok' : 'ERREUR') + ', MT5 ' + (p.mt5Connected ? 'connecté' : 'DÉCONNECTÉ') + (p.dryRun ? ', mode test' : ''),
    '  Dernier événement : ' + (p.lastEvent || '-'),
    '',
    'Synchro des trades IG',
    '  ' + (s.at ? new Date(s.at).toLocaleString('fr-FR') : '?') + ' : ' + (s.ok ? '' : 'ÉCHEC, ') + (s.message || '-'),
    '',
    'Données du Stream Deck : ' + (lastError ? 'ÉCHEC (' + lastError + '), chiffres de ' + hhmm(data.computedAt) : 'à jour (' + hhmm(data.computedAt) + ')'),
  ];
  return popup('État des ponts', lines.join('\n'));
}

// Ouvre un onglet Chrome (et non le navigateur par defaut) ; repli sur le navigateur par defaut si Chrome manque.
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
function openChrome(url) {
  if (!fs.existsSync(CHROME)) return send({ event: 'openUrl', payload: { url } });
  const p = spawn(CHROME, [url], { detached: true, stdio: 'ignore' });
  p.on('error', e => { log('chrome : ' + e.message); send({ event: 'openUrl', payload: { url } }); });
  p.unref();
}

const PRESS = {
  capital: () => openChrome(CONFIG.dashboardUrl),
  pnlmois: () => openChrome(CONFIG.dashboardUrl),
  pnljour: ctx => { send({ event: 'setImage', context: ctx, payload: { image: key({ label: 'P&L JOUR', value: '…', sub: 'mise à jour', color: C.dim }), target: 0 } }); refresh(); },
  pont: () => pontDetails(),
  enfants: () => kidsDetails(),
  dax: () => openChrome('https://www.tradingview.com/chart/?symbol=' + INDICES.dax.tv),
  ndx: () => openChrome('https://www.tradingview.com/chart/?symbol=' + INDICES.ndx.tv),
  spx: () => openChrome('https://www.tradingview.com/chart/?symbol=' + INDICES.spx.tv),
};

ws.on('open', () => {
  send({ event: args.registerEvent, uuid: args.pluginUUID });
  log('plugin connecte (port ' + args.port + ')');
  refresh();
  setInterval(refresh, CONFIG.refreshMs);
  refreshIndices();
  setInterval(refreshIndices, CONFIG.indexRefreshMs);
  setInterval(() => { for (const [c, n] of contexts) if (n === 'pont') paint(c); }, 30000);   // l'age du pont avance meme sans nouvelles donnees
});
ws.on('message', raw => {
  let m; try { m = JSON.parse(raw); } catch (e) { return; }
  if (m.event === 'willAppear') { contexts.set(m.context, actionName(m.action)); log('touche affichee : ' + actionName(m.action)); paint(m.context); }
  else if (m.event === 'willDisappear') contexts.delete(m.context);
  else if (m.event === 'keyDown') {
    const f = PRESS[actionName(m.action)];
    if (f) Promise.resolve(f(m.context)).catch(e => log('touche : ' + e.message));
  }
});
ws.on('close', () => { log('deconnecte du logiciel Stream Deck'); process.exit(0); });
ws.on('error', e => log('websocket : ' + e.message));
