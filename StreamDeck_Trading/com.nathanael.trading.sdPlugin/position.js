// Touches JAUGE et SECURITE de la position ouverte (meme lecture que la carte « Position en cours » du dashboard).
// Donnees : positions IG (niveau, stop, objectif, stop suiveur) + cours du flux. Aucune requete IG en plus.
'use strict';

function createPositionKeys({ C, esc, nf1, nf0, igFeed, log }) {
  const F = 'font-family="Segoe UI, Arial" text-anchor="middle" font-weight="800"';
  const svgWrap = (accent, body) => 'data:image/svg+xml;charset=utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">'
    + '<rect width="144" height="144" fill="' + C.bg + '"/>'
    + '<rect x="0" y="0" width="144" height="6" fill="' + accent + '"/>' + body + '</svg>');
  const title = t => '<text x="72" y="22" ' + F + ' font-size="14" fill="' + C.dim + '">' + esc(t) + '</text>';
  // points : sans « ,0 » inutile (42 et non 42,0), une decimale sinon
  const pts = v => { const a = Math.abs(v); return (Math.abs(a - Math.round(a)) < 0.05 ? nf0.format(Math.round(a)) : nf1.format(a)).replace(/\s/g, ' '); };
  const eurTxt = v => (v > 0 ? '+' : v < 0 ? '−' : '') + nf0.format(Math.abs(Math.round(v))).replace(/\s/g, ' ') + ' €';

  // €/point deduit du P&L latent / points (comme le dashboard), memorise par position une fois l'ecart net
  const eurPerPt = {}, verifie = {};

  // Position suivie : la premiere ouverte, avec son cours de sortie (bid si achat, offer si vente)
  function current() {
    const s = igFeed.state;
    if (s.status !== 'ok' || !s.positions || !s.positions.list || !s.positions.list.length) return null;
    const p = s.positions.list[0], q = s.quotes[p.epic];
    if (!q || Date.now() - q.at > 120000) return { p, n: s.positions.list.length, stale: true };
    const buy = p.direction === 'BUY', exit = buy ? q.bid : q.offer;
    const points = buy ? exit - p.level : p.level - exit;
    // Valeur d'1 point : FIXE pour une position. D'abord taille x valeur du contrat donnees par IG ; sinon,
    // estimation P&L latent / points figee la premiere fois (la recalculer a chaque tick faisait bouger le
    // montant du risque, P&L et cours n'arrivant pas au meme instant).
    if (!eurPerPt[p.dealId]) {
      if (p.size > 0 && p.contractSize > 0) eurPerPt[p.dealId] = p.size * p.contractSize;
      else if (s.positions.list.length === 1 && s.account && Math.abs(points) >= 5) eurPerPt[p.dealId] = Math.abs(s.account.pnl / points);
    }
    // controle unique par position : valeur IG vs estimation P&L / points (doivent concorder)
    if (log && eurPerPt[p.dealId] && !verifie[p.dealId] && s.positions.list.length === 1 && s.account && Math.abs(points) >= 5) {
      verifie[p.dealId] = true;
      log('position ' + p.dealId + ' : valeur du point ' + eurPerPt[p.dealId].toFixed(2) + ' (IG taille x contrat), estimation P&L/points ' + Math.abs(s.account.pnl / points).toFixed(2));
    }
    return { p, n: s.positions.list.length, buy, exit, points, ept: eurPerPt[p.dealId] || null };
  }
  const nameOf = p => {
    const h = (p.epic + ' ' + p.name).toUpperCase();
    return /NASDAQ|US TECH/.test(h) ? 'NDX' : /DAX|ALLEMAGNE|GERMANY/.test(h) ? 'DAX' : /SPTRD|US 500/.test(h) ? 'SPX' : (p.name.split(' ')[0] || '?').slice(0, 6).toUpperCase();
  };
  const empty = t => svgWrap(C.gray, title(t) + '<text x="72" y="84" ' + F + ' font-size="15" fill="' + C.gray + '">aucune position</text>');
  const waiting = (t, r) => svgWrap(C.gray, title(t + ' · ' + nameOf(r.p)) + '<text x="72" y="84" ' + F + ' font-size="15" fill="' + C.dim + '">cours en attente</text>');

  // JAUGE : stop a gauche, objectif a droite, toujours oriente sens favorable vers la droite.
  function gauge() {
    const r = current();
    if (!r) return empty('JAUGE');
    if (r.stale) return waiting('JAUGE', r);
    const { p, buy, exit } = r;
    const f = v => buy ? v : -v;   // espace « favorable » : plus grand = mieux
    const vals = [p.level, exit].concat(p.stop != null ? [p.stop] : []).concat(p.limit != null ? [p.limit] : []).map(f);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
    // grand format (demande du user) : barre epaisse en haut, distances SL / TP en gros dessous
    const X0 = 9, X1 = 135, Y = 36, H = 22;
    const x = v => X0 + (X1 - X0) * (f(v) - lo) / (hi - lo);
    let body = '';
    body += '<rect x="' + X0 + '" y="' + Y + '" width="' + (X1 - X0) + '" height="' + H + '" rx="7" fill="#24303d"/>';
    const seg = (a, b, c) => { const xa = Math.min(x(a), x(b)), xb = Math.max(x(a), x(b)); if (xb - xa > 0.5) body += '<rect x="' + xa.toFixed(1) + '" y="' + Y + '" width="' + (xb - xa).toFixed(1) + '" height="' + H + '" fill="' + c + '" opacity="0.85"/>'; };
    if (p.stop != null) seg(p.stop, p.level, f(p.stop) < f(p.level) ? C.neg : C.pos);   // rouge = risque, vert = securise
    seg(p.level, exit, f(exit) >= f(p.level) ? C.pos : C.neg);                            // gain ou perte en cours
    const tick = (v, c, h) => { body += '<rect x="' + (x(v) - 1.5).toFixed(1) + '" y="' + (Y - h) + '" width="3" height="' + (H + 2 * h) + '" fill="' + c + '"/>'; };
    const securise = p.stop != null && f(p.stop) >= f(p.level);
    if (p.stop != null) tick(p.stop, securise ? C.pos : C.neg, 5);
    if (p.limit != null) tick(p.limit, C.pos, 5);
    tick(p.level, C.txt, 7);
    body += '<circle cx="' + x(exit).toFixed(1) + '" cy="' + (Y + H / 2) + '" r="11" fill="' + C.txt + '" stroke="' + C.bg + '" stroke-width="3"/>';
    // distances depuis le cours, arrondies au point : jusqu'au stop (colonne gauche), jusqu'a l'objectif (droite)
    const col2 = (cx, etiq, nb, c) => '<text x="' + cx + '" y="86" ' + F + ' font-size="16" fill="' + c + '">' + esc(etiq) + '</text>'
      + '<text x="' + cx + '" y="120" ' + F + ' font-size="' + (String(nb).length > 4 ? 25 : 31) + '" fill="' + c + '">' + esc(nb) + '</text>';
    body += p.stop != null ? col2(38, 'SL', Math.round(Math.abs(f(exit) - f(p.stop))), securise ? C.pos : C.neg) : col2(38, 'SL', '–', C.warn);
    body += p.limit != null ? col2(106, 'TP', Math.round(Math.abs(f(p.limit) - f(exit))), C.pos) : col2(106, 'TP', '–', C.dim);
    body += '<text x="72" y="139" ' + F + ' font-size="12" fill="' + C.dim + '">pts depuis le cours</text>';
    const arrow = buy ? '▲' : '▼';
    const titre = '<text x="72" y="24" ' + F + ' font-size="17" fill="' + (buy ? C.pos : C.neg) + '">' + esc(arrow + ' ' + nameOf(p) + (r.n > 1 ? ' (+' + (r.n - 1) + ')' : '')) + '</text>';
    return svgWrap(r.points >= 0 ? C.pos : C.neg, titre + body);
  }

  // SECURITE : ce qui est garanti si le stop est touche (achat : stop - entree ; vente : entree - stop)
  function secure() {
    const r = current();
    if (!r) return empty('SÉCURITÉ');
    const { p } = r;
    const buy = p.direction === 'BUY';
    // grands caracteres (demande du user) : points en tres gros, euros en gros, mention en bas
    const bas = txt => '<text x="72" y="136" ' + F + ' font-size="15" fill="' + C.dim + '">' + esc(txt) + '</text>';
    const trail = p.trailing ? bas('suiveur ' + pts(p.trailing) + ' pts') : '';
    if (p.stop == null) return svgWrap(C.warn, title('SÉCURITÉ') + '<text x="72" y="84" ' + F + ' font-size="23" fill="' + C.warn + '">SANS STOP</text>' + trail);
    const sec = buy ? p.stop - p.level : p.level - p.stop;
    const ept = r.ept;
    const eurLine = ept ? '<text x="72" y="110" ' + F + ' font-size="28" fill="__C__">' + esc(eurTxt(sec * ept)) + '</text>' : '';
    if (Math.abs(sec) <= 0.05) return svgWrap(C.txt, title('SÉCURITÉ') + '<text x="72" y="84" ' + F + ' font-size="21" fill="' + C.txt + '">POINT MORT</text>' + trail);
    const nb = pts(Math.abs(sec)), taille = nb.length > 4 ? 38 : 46;
    if (sec > 0) {
      // cadenas ferme dessine (les emojis ne s'affichent pas sur la touche)
      const lock = '<rect x="10" y="50" width="26" height="21" rx="4" fill="' + C.pos + '"/><path d="M15 50 v-7 a8 8 0 0 1 16 0 v7" fill="none" stroke="' + C.pos + '" stroke-width="4"/>';
      return svgWrap(C.pos, title('SÉCURISÉE') + lock + '<text x="86" y="72" ' + F + ' font-size="' + taille + '" fill="' + C.pos + '">+' + esc(nb) + '</text>'
        + eurLine.replace('__C__', C.pos) + (trail || bas('pts garantis')));
    }
    return svgWrap(C.neg, title('RISQUE') + '<text x="72" y="72" ' + F + ' font-size="' + taille + '" fill="' + C.neg + '">−' + esc(nb) + '</text>'
      + eurLine.replace('__C__', C.neg) + (trail || bas('pts si stop touché')));
  }

  return { gauge, secure };
}

module.exports = { createPositionKeys };
