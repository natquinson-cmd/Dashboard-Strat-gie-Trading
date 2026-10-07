// Ecran « Enfants » : un appui sur la touche ENFANTS remplace les touches du plugin par une touche par enfant
// (ligne du haut), le total de la poche au centre et RETOUR en bas a gauche. Retour au bout de 45 s sans appui.
// Pas de deuxieme page Stream Deck : le plugin redessine ses propres touches (toutes les touches sauf « page suivante »).
'use strict';

// ordre fixe (sinon les touches changeraient de place quand les valeurs bougent) et couleurs du dashboard
const ORDRE = ['Anaïa', 'Robin', 'Lily Rose', 'Noah', 'Elie'];
const COULEUR = { 'Anaïa': '#8b5cf6', 'Robin': '#3b82f6', 'Lily Rose': '#ec4899', 'Noah': '#f97316', 'Elie': '#dcee00' };
const POS_RETOUR = '0,2', POS_TOTAL = '2,1';

function createEnfantsView({ C, esc, eur, sEur, sPct, col, getData, getMode }) {
  const F = 'font-family="Segoe UI, Arial" text-anchor="middle" font-weight="800"';
  const wrap = (accent, body) => 'data:image/svg+xml;charset=utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">'
    + '<rect width="144" height="144" fill="' + C.bg + '"/>' + (accent ? '<rect x="0" y="0" width="144" height="10" fill="' + accent + '"/>' : '') + body + '</svg>');

  function enfants() {
    const k = getData() && getData().kids;
    if (!k) return [];
    const by = {}; k.children.forEach(c => { by[c.child] = c; });
    const liste = ORDRE.filter(n => by[n]).map(n => by[n]);
    return liste.concat(k.children.filter(c => !ORDRE.includes(c.child)));
  }

  // Touche d'un enfant : prenom, capital en gros, plus-value (totale ou du jour selon MODE) et %
  function cle(c) {
    const jour = getMode() === 'jour';
    const pv = jour ? c.day : c.value - c.paid;
    const pct = jour ? (c.value - c.day > 0 ? c.day / (c.value - c.day) * 100 : 0) : (c.paid > 0 ? (c.value - c.paid) / c.paid * 100 : 0);
    const nom = c.child.length > 9 ? c.child.split(' ')[0] : c.child;
    const pvTxt = pv == null ? '–' : sEur(pv), pc = pv == null ? C.gray : col(pv);
    // cagnotte (depuis le 05/10/2026) : c.value = part de la cagnotte entiere, plus-value depuis la bascule.
    // Avant : ETF + Lendermarket de Noah et Elie, plus-value et % de l'ETF seul.
    const k = getData() && getData().kids, pot = !!(k && k.pot);
    const capital = pot ? c.value : c.value + (c.lm || 0);
    // meme mise en page pour tous (le detail « ETF + LM » est retire, trop petit, demande du user le 07/10) :
    // prenom, capital, plus-value, %, en grand
    const pvLbl = esc(pvTxt) + (c.lm && !pot ? ' ETF' : '');
    return wrap(COULEUR[c.child] || C.blue,
      '<text x="72" y="32" ' + F + ' font-size="19" fill="' + C.txt + '">' + esc(nom.toUpperCase()) + '</text>'
      + '<text x="72" y="74" ' + F + ' font-size="' + (eur(capital).length > 7 ? 29 : 33) + '" fill="' + C.txt + '">' + esc(eur(capital)) + '</text>'
      + '<text x="72" y="107" ' + F + ' font-size="' + (pvLbl.length > 9 ? 20 : 24) + '" fill="' + (pv == null ? C.gray : pc) + '">' + pvLbl + '</text>'
      + '<text x="72" y="134" ' + F + ' font-size="' + (jour ? 17 : 21) + '" fill="' + (pv == null ? C.gray : pc) + '">' + esc(pv == null ? '' : sPct(pct).replace(' %', '%')) + (jour ? ' · jour' : '') + '</text>');
  }
  function total() {
    const k = getData() && getData().kids;
    if (!k) return wrap(C.gray, '<text x="72" y="80" ' + F + ' font-size="15" fill="' + C.gray + '">chargement</text>');
    const jour = getMode() === 'jour', pv = jour ? k.day : k.pnl, pct = jour ? k.dayPct : k.pct;
    // cagnotte : valeur totale (ETF + Lendermarket), plus-value depuis la bascule. Avant : ETF + LM, plus-value de l'ETF.
    const totalLm = k.pot ? 0 : k.children.reduce((a, c) => a + (c.lm || 0), 0);
    return wrap(C.dim,
      '<text x="72" y="34" ' + F + ' font-size="15" fill="' + C.dim + '">' + (k.pot ? 'CAGNOTTE' : (totalLm ? 'TOTAL ENFANTS' : 'TOTAL POCHE')) + '</text>'
      + '<text x="72" y="74" ' + F + ' font-size="28" fill="' + C.txt + '">' + esc(eur(k.value + totalLm)) + '</text>'
      + '<text x="72" y="104" ' + F + ' font-size="20" fill="' + (pv == null ? C.gray : col(pv)) + '">' + esc(pv == null ? '–' : sEur(pv)) + '</text>'
      + '<text x="72" y="128" ' + F + ' font-size="17" fill="' + (pv == null ? C.gray : col(pv)) + '">' + esc(pct == null ? '' : sPct(pct).replace(' %', '%')) + (jour ? ' · jour' : '') + '</text>');
  }
  const retour = () => wrap(null,
    '<rect x="14" y="40" width="116" height="64" rx="14" fill="none" stroke="' + C.dim + '" stroke-width="3"/>'
    + '<path d="M44 72 l16 -14 v9 h34 v10 h-34 v9 z" fill="' + C.txt + '"/>'
    + '<text x="72" y="128" ' + F + ' font-size="16" fill="' + C.dim + '">RETOUR</text>');
  const vide = () => wrap(null, '');

  // Image d'une touche selon sa position « colonne,ligne » pendant l'ecran Enfants
  function render(pos) {
    if (pos === POS_RETOUR) return retour();
    if (pos === POS_TOTAL) return total();
    const [col_, row] = pos.split(',').map(Number);
    if (row === 0) { const c = enfants()[col_]; return c ? cle(c) : vide(); }
    return vide();
  }
  return { render };
}

module.exports = { createEnfantsView };
