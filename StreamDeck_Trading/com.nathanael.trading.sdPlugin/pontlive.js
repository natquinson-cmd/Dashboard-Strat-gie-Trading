// Position en cours publiee par le PONT du VPS (dashboard/pontLive, toutes les 5 s quand une position est
// ouverte). Sert de source quand le flux IG du Stream Deck est coupe ou desactive : le Stream Deck n'a alors
// plus besoin de se connecter lui-meme a IG (cle API partagee avec le pont, suspendue par IG le 19/10/2026).
// Lecture seule, Firebase uniquement.
'use strict';
const FB = 'https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com/dashboard/pontLive.json';

function createPontLive(log, onChange) {
  let live = null, erreur = null;
  async function lire() {
    try {
      const secret = process.env.FIREBASE_DB_SECRET;
      const r = await fetch(FB + (secret ? '?auth=' + encodeURIComponent(secret) : ''), { signal: AbortSignal.timeout(8000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const j = await r.json();
      const avant = JSON.stringify(live);
      live = j && j.at ? { at: Date.parse(j.at), pnl: Number(j.pnl) || 0, positions: Array.isArray(j.positions) ? j.positions : [] } : null;
      if (erreur) { log('pontLive : lecture retablie'); erreur = null; }
      if (JSON.stringify(live) !== avant) onChange();
    } catch (e) {
      if (!erreur) log('pontLive : ' + e.message);
      erreur = e.message;
    }
  }
  lire();
  setInterval(lire, 5000);

  // Etat au meme format que celui du flux IG (ig.js), pour que les touches n'aient rien a changer.
  // null si la publication du pont a plus de 60 s (le pont envoie toutes les 5 s, ou une fois a la cloture).
  function etat() {
    if (!live || !(Date.now() - live.at < 60000 || !live.positions.length)) return null;
    const list = live.positions.map(p => {
      const kind = String(p.kind || '?');
      // valeur d'1 point : euros securises / points securises (fixe), sinon P&L / points
      const ept = p.secured && p.securedEur ? Math.abs(p.securedEur / p.secured) : (p.points ? Math.abs(p.pnl / p.points) : 0);
      return { dealId: 'pont-' + kind + '-' + p.level, direction: p.direction, size: Number(p.size) || 0, level: Number(p.level),
        stop: p.stop != null ? Number(p.stop) : null, limit: p.limit != null ? Number(p.limit) : null, trailing: p.trailing || null,
        contractSize: p.size ? ept / p.size : null, epic: 'PONT:' + kind, name: kind, exit: Number(p.exit) };
    });
    const quotes = {};
    list.forEach(p => { quotes[p.epic] = { bid: p.exit, offer: p.exit, at: live.at }; });
    return { status: 'ok', source: 'pont', account: { pnl: live.pnl, at: live.at }, positions: { count: list.length, list, at: live.at }, quotes, prices: {} };
  }
  return { etat };
}

module.exports = { createPontLive };
