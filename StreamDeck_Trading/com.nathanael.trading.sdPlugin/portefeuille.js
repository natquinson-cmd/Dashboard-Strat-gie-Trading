// Ecran « Positions » : un appui sur P&L JOUR remplace les touches du plugin par les 12 lignes d'actions du
// portefeuille (logo, ticker, plus-value et %), triees par poids comme l'ecran Actions du dashboard.
// (0,2) = RETOUR, (1,2) = bascule plus-value totale / du jour (meme mode que la touche PLUS-VALUE).
// Logos : FinancialModelingPrep comme le dashboard, repli sur l'icone du site ; mis en cache sur disque.
'use strict';
const fs = require('fs');
const path = require('path');

const zlib = require('zlib');

// Part des pixels VISIBLES sur fond blanc (ni transparents, ni quasi blancs) d'un PNG 8 bits RGB/RGBA.
// Un logo blanc (Visa chez FMP) serait invisible sur la tuile blanche : on prend alors l'icone du site,
// comme le dashboard. Renvoie null si le format n'est pas gere (on garde alors le logo).
function partVisible(buf) {
  try {
    if (buf.readUInt32BE(0) !== 0x89504e47) return null;
    let off = 8, w = 0, h = 0, depth = 0, type = 0; const idat = [];
    while (off < buf.length) {
      const len = buf.readUInt32BE(off), tag = buf.toString('ascii', off + 4, off + 8), d = buf.subarray(off + 8, off + 8 + len);
      if (tag === 'IHDR') { w = d.readUInt32BE(0); h = d.readUInt32BE(4); depth = d[8]; type = d[9]; if (d[12]) return null; }
      else if (tag === 'IDAT') idat.push(d);
      else if (tag === 'IEND') break;
      off += 12 + len;
    }
    const bpp = type === 6 ? 4 : type === 2 ? 3 : 0;
    if (depth !== 8 || !bpp) return null;
    const raw = zlib.inflateSync(Buffer.concat(idat)), stride = w * bpp, px = Buffer.alloc(h * stride);
    for (let y = 0; y < h; y++) {
      const f = raw[y * (stride + 1)], src = y * (stride + 1) + 1, dst = y * stride;
      for (let x = 0; x < stride; x++) {
        const a = x >= bpp ? px[dst + x - bpp] : 0, b = y ? px[dst - stride + x] : 0, c = (x >= bpp && y) ? px[dst - stride + x - bpp] : 0;
        let v = raw[src + x];
        if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
        else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += (pa <= pb && pa <= pc) ? a : pb <= pc ? b : c; }
        px[dst + x] = v & 255;
      }
    }
    let vis = 0;
    for (let i = 0; i < px.length; i += bpp) {
      const al = bpp === 4 ? px[i + 3] : 255;
      if (al > 60 && Math.min(px[i], px[i + 1], px[i + 2]) < 225) vis++;
    }
    return vis / (w * h);
  } catch (e) { return null; }
}

const SLOTS = ['0,0', '1,0', '2,0', '3,0', '4,0', '0,1', '1,1', '2,1', '3,1', '4,1', '2,2', '3,2'];
const POS_RETOUR = '0,2', POS_MODE = '1,2';

function createPortefeuilleView({ C, esc, sPct, col, getData, getMode, renderMode, log, onLogo }) {
  const F = 'font-family="Segoe UI, Arial" text-anchor="middle" font-weight="800"';
  const wrap = body => 'data:image/svg+xml;charset=utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="144" height="144" viewBox="0 0 144 144">'
    + '<rect width="144" height="144" fill="' + C.bg + '"/>' + body + '</svg>');

  // ── logos (cache memoire + disque) ──
  const DIR = path.join(__dirname, 'logos');
  const logos = {};   // ticker -> data URI | 'absent' | 'en cours'
  function logo(l) {
    if (logos[l.t] && logos[l.t] !== 'en cours') return logos[l.t];
    if (logos[l.t] === 'en cours') return null;
    const file = path.join(DIR, l.t.replace(/[^A-Z0-9.-]/gi, '_') + '.png');
    try { logos[l.t] = 'data:image/png;base64,' + fs.readFileSync(file).toString('base64'); return logos[l.t]; } catch (e) { /* pas en cache */ }
    logos[l.t] = 'en cours';
    (async () => {
      const dom = (l.website || '').replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
      const urls = ['https://financialmodelingprep.com/image-stock/' + encodeURIComponent(l.t.replace(/-(USD|EUR)$/, m => m.slice(1))) + '.png']
        .concat(dom ? ['https://www.google.com/s2/favicons?domain=' + encodeURIComponent(dom) + '&sz=64'] : []);
      for (const u of urls) {
        try {
          const r = await fetch(u, { signal: AbortSignal.timeout(10000) });
          if (!r.ok || !/image/.test(r.headers.get('content-type') || '')) continue;
          const buf = Buffer.from(await r.arrayBuffer());
          if (buf.length < 200) continue;
          const vis = partVisible(buf);
          if (vis != null && vis < 0.03 && u !== urls[urls.length - 1]) { log('logo ' + l.t + ' blanc ou vide, icone du site a la place'); continue; }
          try { fs.mkdirSync(DIR, { recursive: true }); fs.writeFileSync(file, buf); } catch (e) { /* cache facultatif */ }
          logos[l.t] = 'data:image/png;base64,' + buf.toString('base64');
          onLogo();
          return;
        } catch (e) { /* essai suivant */ }
      }
      logos[l.t] = 'absent';
      log('logo introuvable : ' + l.t);
    })();
    return null;
  }

  const actions = () => ((getData() && getData().lignes) || []).filter(l => l.cat === 'actions');

  function cle(l) {
    const jour = getMode() === 'jour';
    // montants en DOLLARS sur cet ecran (devise du portefeuille), format du dashboard : +$318 / -$215
    const pv = jour ? l.dayUsd : l.pnlUsd, pct = jour ? l.dayPct : l.pnlPct;
    const sUsd = v => (v > 0 ? '+' : v < 0 ? '-' : '') + '$' + Math.round(Math.abs(v)).toLocaleString('fr-FR').replace(/\s/g, ' ');
    const c = pv == null ? C.gray : col(pv);
    const tk = l.t.replace(/(\.[A-Z]{1,3}|-USD)$/, '');
    const lg = logo(l);
    // pas de ticker (le logo suffit, demande du user) : logo centre en haut, chiffres en grand dessous.
    // Sans logo, le ticker s'ecrit dans la tuile.
    const img = lg && lg !== 'absent'
      ? '<rect x="35" y="3" width="74" height="74" rx="14" fill="#ffffff"/><image x="40" y="8" width="64" height="64" href="' + lg + '" xlink:href="' + lg + '" preserveAspectRatio="xMidYMid meet"/>'
      : '<rect x="35" y="3" width="74" height="74" rx="14" fill="#24303d"/><text x="72" y="46" ' + F + ' font-size="16" fill="' + C.txt + '">' + esc(tk.slice(0, 5)) + '</text>';
    const montant = pv == null ? '–' : sUsd(pv), pctTxt = pct == null ? '' : sPct(pct).replace(' %', '%');
    return wrap(img
      + (jour ? '<text x="6" y="18" font-family="Segoe UI, Arial" font-weight="800" font-size="13" fill="' + C.blue + '">J</text>' : '')
      + '<text x="72" y="107" ' + F + ' font-size="' + (montant.length > 7 ? 25 : montant.length > 5 ? 28 : 30) + '" fill="' + c + '">' + esc(montant) + '</text>'
      + '<text x="72" y="136" ' + F + ' font-size="' + (pctTxt.length > 7 ? 21 : 23) + '" fill="' + c + '">' + esc(pctTxt) + '</text>');
  }
  const retour = () => wrap('<rect x="14" y="40" width="116" height="64" rx="14" fill="none" stroke="' + C.dim + '" stroke-width="3"/>'
    + '<path d="M44 72 l16 -14 v9 h34 v10 h-34 v9 z" fill="' + C.txt + '"/>'
    + '<text x="72" y="128" ' + F + ' font-size="16" fill="' + C.dim + '">RETOUR</text>');

  function render(pos) {
    if (pos === POS_RETOUR) return retour();
    if (pos === POS_MODE) return renderMode();
    const i = SLOTS.indexOf(pos);
    const l = i >= 0 ? actions()[i] : null;
    return l ? cle(l) : wrap('');
  }
  // ticker de la touche (pour l'appui), null hors positions
  const tickerAt = pos => { const i = SLOTS.indexOf(pos); const l = i >= 0 ? actions()[i] : null; return l ? l.t : null; };
  return { render, tickerAt, POS_RETOUR, POS_MODE };
}

module.exports = { createPortefeuilleView };
