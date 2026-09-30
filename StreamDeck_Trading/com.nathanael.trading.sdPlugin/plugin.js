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
  ideasFile: 'C:/Users/quinson/Desktop/Claude/Idees_Trading.md',
  refreshMs: 60000,
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
  idee() {
    let n = 0;
    try {
      const today = new Date().toISOString().slice(0, 10);
      n = fs.readFileSync(CONFIG.ideasFile, 'utf8').split('\n').filter(l => l.startsWith('- ' + today)).length;
    } catch (e) { /* fichier pas encore cree */ }
    return key({ label: 'IDÉE', value: '+', valueSize: 54, sub: n ? n + " aujourd'hui" : 'noter', color: C.blue, accent: C.blue });
  },
};

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

async function noteIdea(ctx) {
  const out = await psRun("[Console]::OutputEncoding = [Text.Encoding]::UTF8; Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.Interaction]::InputBox('Ton idée (ticker, thèse, à vérifier...) :', 'Noter une idée de trading', '')");
  const txt = out.replace(/\s+/g, ' ').trim();
  if (!txt) return;
  const d = new Date();
  const stamp = d.toISOString().slice(0, 10) + ' ' + hhmm(d);
  try {
    if (!fs.existsSync(CONFIG.ideasFile)) fs.writeFileSync(CONFIG.ideasFile, '# Idées de trading\n\nNotées depuis le Stream Deck. Repérage, pas une décision.\n\n');
    fs.appendFileSync(CONFIG.ideasFile, '- ' + stamp + ' : ' + txt + '\n');
    send({ event: 'showOk', context: ctx });
  } catch (e) {
    log('idee : ' + e.message);
    send({ event: 'showAlert', context: ctx });
  }
  paint(ctx);
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

const PRESS = {
  capital: () => send({ event: 'openUrl', payload: { url: CONFIG.dashboardUrl } }),
  pnlmois: () => send({ event: 'openUrl', payload: { url: CONFIG.dashboardUrl } }),
  pnljour: ctx => { send({ event: 'setImage', context: ctx, payload: { image: key({ label: 'P&L JOUR', value: '…', sub: 'mise à jour', color: C.dim }), target: 0 } }); refresh(); },
  pont: () => pontDetails(),
  idee: ctx => noteIdea(ctx),
};

ws.on('open', () => {
  send({ event: args.registerEvent, uuid: args.pluginUUID });
  log('plugin connecte (port ' + args.port + ')');
  refresh();
  setInterval(refresh, CONFIG.refreshMs);
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
