#!/usr/bin/env python3
# run.py — orchestrateur du screener (Option C : tout sur le VPS, source gratuite Yahoo).
# 1) Yahoo screener : univers US filtre par croissance + capitalisation (cote serveur)
# 2) Yahoo quoteSummary : enrichit chaque ticker (fondamentaux + prix + MM50/200 + 52s-haut)
# 3) scoring PRE-CASSURE (screen.py) -> classement
# 4) IBKR (optionnel, si ENABLE_IBKR=true) : momentum precis sur le top + positions live
# 5) push Firebase (stocks/screener/latest + /positions), lu par le dashboard
#
# Flags : --no-push (calcule + affiche, ne pousse pas) | --limit N (cap enrichissement)
#
# Env : FIREBASE_DB_URL, FIREBASE_DB_SECRET (ou GOOGLE_APPLICATION_CREDENTIALS)
#       SCREEN_MIN_REVGROWTH (0.25) SCREEN_MIN_MCAP (300000000) UNIVERSE_LIMIT (250) MAX_TOTAL (500) TOP_N (50)
#       ENABLE_IBKR (false) IBKR_HOST IBKR_PORT IBKR_CLIENT_ID BLEND_IBKR (0.15)
import os
import re
import sys
import time

from yahoo import Yahoo
from screen import rank_universe, DEFAULT_CONFIG

NO_PUSH = '--no-push' in sys.argv
WATCH = '--watch' in sys.argv   # relance a chaque changement de config depuis le dashboard
LIMIT_OVERRIDE = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--limit=')), None)
# Mode : smallcap (petites caps momentum/pre-cassure) | quality (grandes caps qualite-valorisation) | None = les deux
MODE = next((a.split('=')[1] for a in sys.argv if a.startswith('--mode=')), None)

MIN_REVGROWTH = float(os.environ.get('SCREEN_MIN_REVGROWTH', '0.30'))
# Fourchette de capitalisation : on vise les SMALL/MID caps "pretes a exploser" et on EXCLUT
# les mega caps (qui ne montent que de quelques %). Baisse MAX_MCAP pour cibler plus petit.
MIN_MCAP = float(os.environ.get('SCREEN_MIN_MCAP', '500000000'))
MAX_MCAP = float(os.environ.get('SCREEN_MAX_MCAP', '10000000000'))
# Borne HAUTE de croissance appliquee EN PYTHON (le champ croissance du screener Yahoo devient
# incoherent avec deux bornes) : au-dela = croissance depuis une base quasi nulle = distorsion.
MAX_REVGROWTH = float(os.environ.get('SCREEN_MAX_REVGROWTH', '3.0'))
UNIVERSE_LIMIT = LIMIT_OVERRIDE or int(os.environ.get('UNIVERSE_LIMIT', '300'))
MAX_TOTAL = int(os.environ.get('MAX_TOTAL', '1000'))
TOP_N = int(os.environ.get('TOP_N', '50'))
ENABLE_IBKR = os.environ.get('ENABLE_IBKR', 'false') == 'true'
BLEND = float(os.environ.get('BLEND_IBKR', '0.15'))


# Config mode QUALITE (grandes caps US + Europe, notees par valorisation)
Q_MIN_MCAP = float(os.environ.get('Q_MIN_MCAP', '5000000000'))
Q_REGIONS = os.environ.get('Q_REGIONS', 'us,fr,de,nl,gb,ch,it,es,se,dk,fi').split(',')
Q_UNIVERSE_LIMIT = int(os.environ.get('Q_UNIVERSE_LIMIT', '300'))  # proposition 2 : univers elargi (inclut MSCI, FICO, MELI, S&P Global...)
Q_MAX_TOTAL = int(os.environ.get('Q_MAX_TOTAL', '1500'))

# Places boursieres US majeures (on exclut l'OTC/Pink et les tickers etrangers = ~560 titres de junk)
MAJOR_EXCH = {'NMS', 'NYQ', 'NGM', 'NCM', 'ASE', 'PCX', 'BATS'}
# + places europeennes primaires pour le mode qualite (PAS l'IOB = GDR/ADR etrangers thin)
Q_MAJOR_EXCH = MAJOR_EXCH | {'PAR', 'GER', 'AMS', 'LSE', 'EBS', 'MIL', 'MCE', 'STO', 'CPH', 'HEL', 'VIE', 'BRU', 'LIS'}


def screen_smallcap(y):
    # SMALL/MID caps US, tri par cap croissante (les plus petites d'abord), filtrage fin en Python.
    operands = [
        ('gt', 'quarterlyrevenuegrowth.quarterly', MIN_REVGROWTH),
        ('gt', 'intradaymarketcap', MIN_MCAP),
        ('lt', 'intradaymarketcap', MAX_MCAP),
        ('eq', 'region', 'us'),
    ]
    rows = y.screen(operands, size=250, sort_field='intradaymarketcap', sort_type='asc', max_total=MAX_TOTAL)
    rows = [t for t in rows if t.get('exchange') in MAJOR_EXCH]
    print(f'Screener small-cap : {len(rows)} titres US ({MIN_MCAP/1e6:.0f}M-{MAX_MCAP/1e9:.0f}Md$, CA YoY>{MIN_REVGROWTH:.0%})')
    return [t['symbol'] for t in rows]


# priorite de cotation pour le dedoublonnage (US d'abord, puis places EU primaires)
_EXCH_PRIO = {e: i for i, e in enumerate(
    ['NMS', 'NYQ', 'NGM', 'NCM', 'ASE', 'PCX', 'BATS', 'PAR', 'AMS', 'GER', 'EBS', 'MIL', 'MCE', 'LSE', 'STO', 'CPH', 'HEL', 'VIE', 'BRU', 'LIS', 'IOB'])}


def _company_key(name):
    n = (name or '').upper()
    n = re.sub(r'\b(INC|CORP|CORPORATION|PLC|SA|NV|AG|SE|LTD|LIMITED|CO|COMPANY|HOLDINGS?|GROUP|ORD|ADR|ADS|'
              r'CLASS|SHS?|SHARES?|REGISTERED|REG|DEPOSITARY|RECEIPTS?|NEW|THE|DL|EO|NPV|ON|RG|CDI)\b', ' ', n)
    return re.sub(r'[^A-Z]', '', n)[:10]  # lettres seules, 10 premiers -> fusionne les cotations multiples


# Watchlist EUROPE curee (tickers PRIMAIRES) : evite le chaos des cotations croisees des valeurs US
# sur les bourses europeennes. Editable via l'env Q_EU_LIST (tickers separes par des virgules).
Q_EU_DEFAULT = ('MC.PA,OR.PA,RMS.PA,SU.PA,AI.PA,SAF.PA,EL.PA,DG.PA,SAN.PA,BNP.PA,CS.PA,CAP.PA,TTE.PA,STLAP.PA,'
                'ASML.AS,PRX.AS,ADYEN.AS,HEIA.AS,WKL.AS,SAP.DE,SIE.DE,ALV.DE,MBG.DE,DTE.DE,MRK.DE,'
                'NESN.SW,NOVN.SW,ROG.SW,UHR.SW,ZURN.SW,ABBN.SW,NOVO-B.CO,AZN.L,SHEL.L,ULVR.L,RELX.L,HSBA.L,LSEG.L,ITX.MC')
Q_EU_WATCHLIST = [s.strip() for s in os.environ.get('Q_EU_LIST', Q_EU_DEFAULT).split(',') if s.strip()]

# Watchlist US FORCEE : noms US de qualite qui passent SOUS le seuil de cap des ~261 plus grosses (donc absents
# du screener trie par cap) mais qu'on veut quand meme evaluer (ex FICO ~24 Md$). Editable via l'env Q_US_LIST.
Q_US_DEFAULT = 'FICO'
Q_US_WATCHLIST = [s.strip().upper() for s in os.environ.get('Q_US_LIST', Q_US_DEFAULT).split(',') if s.strip()]


def screen_quality(y):
    # US : screener grandes caps (region us = propre), dedoublonne par societe (classes d'actions).
    operands = [('gt', 'intradaymarketcap', Q_MIN_MCAP), ('eq', 'region', 'us')]
    rows = y.screen(operands, size=250, sort_field='intradaymarketcap', sort_type='desc', max_total=Q_MAX_TOTAL)
    rows = [t for t in rows if t.get('exchange') in MAJOR_EXCH and t.get('symbol') and not t['symbol'][0].isdigit()]
    best = {}
    for t in rows:
        k = _company_key(t.get('name')) or t['symbol']
        if k not in best or (t.get('marketCap') or 0) > (best[k].get('marketCap') or 0):
            best[k] = t
    us_syms = [t['symbol'] for t in sorted(best.values(), key=lambda t: -(t.get('marketCap') or 0))]
    us_syms = us_syms[:max(0, Q_UNIVERSE_LIMIT - len(Q_EU_WATCHLIST) - len(Q_US_WATCHLIST))]
    # Watchlist US forcee (ex FICO) : ajoutee si le screener ne l'a pas deja captee
    forced = [s for s in Q_US_WATCHLIST if s not in us_syms]
    # Europe : watchlist curee (tickers primaires, zero doublon)
    print(f'Screener qualite : {len(us_syms)} US (screener) + {len(forced)} US (watchlist) + {len(Q_EU_WATCHLIST)} EU (watchlist)')
    return us_syms + forced + Q_EU_WATCHLIST


def ibkr_enrich(top):
    from ibkr_client import IBKRClient
    from momentum import momentum_score
    host = os.environ.get('IBKR_HOST', '127.0.0.1')
    port = int(os.environ.get('IBKR_PORT', '4001'))
    cid = int(os.environ.get('IBKR_CLIENT_ID', '17'))
    positions, account = [], {}
    with IBKRClient(host, port, cid, readonly=True) as ib:
        positions = ib.positions()
        account = ib.account_summary()
        for c in top:
            m = ib.momentum(c['symbol'])
            c['ibkr'] = m
            c['ibkrMomentumScore'] = momentum_score(m)
            c['tradableIBKR'] = ib.is_tradable(c['symbol'])
            c['scoreScreen'] = c['score']
            if c['ibkrMomentumScore'] is not None:
                c['score'] = round((1 - BLEND) * c['score'] + BLEND * c['ibkrMomentumScore'], 1)
    return positions, account


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def attach_sparklines(y, items):
    """Ajoute a chaque item du top : metrics.spark (mini-serie de cours), metrics.changePct
    (variation du jour) et metrics.price si absent. 1 appel Yahoo/titre, seulement sur le top pousse."""
    for c in items or []:
        s = y.spark(c.get('symbol'))
        m = c.setdefault('metrics', {})
        if s:
            m['spark'] = s['closes']
            m['changePct'] = s['changePct']
            if m.get('price') is None:
                m['price'] = s['price']
        time.sleep(y.pause)
    return items


def apply_firebase_config():
    """Override les defauts avec la config posee par le dashboard (sliders) -> stocks/screener/config."""
    global MIN_MCAP, MAX_MCAP, MIN_REVGROWTH, MAX_REVGROWTH, UNIVERSE_LIMIT, TOP_N
    db = os.environ.get('FIREBASE_DB_URL')
    if not db:
        return
    from firebase_push import get
    cfg = get(db, 'stocks/screener/config')
    if not isinstance(cfg, dict):
        return

    def f(k, cur, cast=float):
        try:
            return cast(cfg[k]) if cfg.get(k) is not None else cur
        except Exception:
            return cur

    MIN_MCAP = f('minMcap', MIN_MCAP)
    MAX_MCAP = f('maxMcap', MAX_MCAP)
    MIN_REVGROWTH = f('minRevGrowth', MIN_REVGROWTH)
    MAX_REVGROWTH = f('maxRevGrowth', MAX_REVGROWTH)
    if not LIMIT_OVERRIDE:
        UNIVERSE_LIMIT = f('universeLimit', UNIVERSE_LIMIT, int)
    TOP_N = f('topN', TOP_N, int)
    print(f'Config dashboard : cap {MIN_MCAP/1e6:.0f}M-{MAX_MCAP/1e9:.1f}Md, CA>{MIN_REVGROWTH:.0%}, analyses={UNIVERSE_LIMIT}, top={TOP_N}')


def run_smallcap(y):
    DEFAULT_CONFIG['topN'] = TOP_N
    symbols = screen_smallcap(y)[:UNIVERSE_LIMIT]
    if not symbols:
        print('Small-cap : univers vide'); return None, [], {}
    print(f'Enrichissement de {len(symbols)} titres...')
    records = y.enrich(symbols)
    records = [r for r in records if r.get('revenueGrowthYoY') is None or r['revenueGrowthYoY'] <= MAX_REVGROWTH]
    print(f'{len(records)} enrichis')
    result = rank_universe(records, DEFAULT_CONFIG)
    top = result['top']
    print(f"small-cap : survivants={result['survivors']} top={len(top)}")
    attach_sparklines(y, top)  # prix + variation du jour + mini-graphique (top uniquement)
    positions, account, source = [], {}, 'yahoo_vps'
    if ENABLE_IBKR:
        try:
            positions, account = ibkr_enrich(top)
            top.sort(key=lambda c: c.get('score') or 0, reverse=True)
            source = 'ibkr_vps'
        except Exception as e:
            print(f'IBKR indisponible ({e})')
    payload = {'generatedAt': _now_iso(), 'source': source, 'mode': 'smallcap',
               'summary': {'universe': len(symbols), 'enriched': len(records), 'survivors': result['survivors'],
                           'topEnriched': len(top), 'coverage': round(len(records) / max(1, len(symbols)) * 100),
                           'enrichedByIBKR': ENABLE_IBKR and source == 'ibkr_vps'},
               'top': top}
    return payload, positions, account


def run_quality(y):
    from quality import rate_universe, QUALITY_CONFIG
    symbols = screen_quality(y)
    if not symbols:
        print('Qualite : univers vide'); return None
    print(f'Enrichissement qualite de {len(symbols)} titres (2 appels/titre)...')
    records = []
    for i, sym in enumerate(symbols):
        r = y.quote_quality(sym)
        if r and r.get('price') is not None and r.get('marketCap'):
            pc = y.price_cagr(sym)
            r['priceCAGR'] = pc
            ec = r.get('earningsCAGR')
            eg = r.get('earningsGrowthYoY')
            # Proposition 4 : si le CAGR benefices sur 4 ans est incalculable (ex Amazon, benefices
            # erratiques), on se rabat sur la croissance annuelle des benefices plutot que d'abandonner.
            growth = ec if ec is not None else eg
            r['gap'] = (growth - pc) if (growth is not None and pc is not None) else None
            dg = y.dividend_growth(sym)   # croissance du dividende (signature DK)
            if dg:
                r.update(dg)              # divStreak, divCagr, divGrowing, divYears
            fh = y.fundamentals_history(sym)   # croissance REGULIERE : CAGR CA/FCF + rachats (DK)
            if fh:
                r.update(fh)              # revCagr, revYears, fcfCagr, sharesChange, buyback
            records.append(r)
        if (i + 1) % 25 == 0:
            print(f'  ...enrichi {i + 1}/{len(symbols)}')
        time.sleep(y.pause)
    # dedoublonnage final par societe (ex AZN ADR US vs AZN.L Londres) : garde la plus grosse cap
    seen, uniq = set(), []
    for r in sorted(records, key=lambda x: -(x.get('marketCap') or 0)):
        k = _company_key(r.get('name')) or r.get('symbol')
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    records = uniq
    res = rate_universe(records, QUALITY_CONFIG)
    # Proposition 1 : on pousse TOUT le classement (Achat fort -> Surevaluee), pas seulement le top,
    # pour afficher aussi les verdicts "Surevaluee" (Apple, Tesla, Costco...) comme la tier list.
    pushed = res['all']
    print(f"qualite : survivants={res['survivors']} classes={len(pushed)}")
    attach_sparklines(y, pushed)  # prix + variation du jour + mini-graphique
    return {'generatedAt': _now_iso(), 'source': 'yahoo_vps', 'mode': 'quality',
            'summary': {'universe': len(symbols), 'enriched': len(records), 'survivors': res['survivors'],
                        'topEnriched': len(pushed), 'coverage': round(len(records) / max(1, len(symbols)) * 100)},
            'top': pushed}


def push_position_meta(y, db):
    """Enrichit les fondamentaux des tickers DETENUS (myPositions), meme hors univers screener,
    pour qu'ils s'affichent dans 'Mes positions' (SNDK, GS... rejetes par le gate). -> positionMeta."""
    from firebase_push import get, push
    pos = get(db, 'stocks/screener/myPositions')
    raw = pos if isinstance(pos, list) else (list(pos.values()) if isinstance(pos, dict) else [])
    syms = sorted({str(p.get('ticker', '')).upper().strip() for p in raw if isinstance(p, dict) and p.get('ticker')})
    syms = [s for s in syms if s]
    if not syms:
        print('positionMeta : aucune position'); return
    out = []
    for sym in syms:
        r = y.quote_quality(sym)
        if not r or r.get('price') is None:
            continue
        pc = y.price_cagr(sym)
        r['priceCAGR'] = pc
        growth = r.get('earningsCAGR') if r.get('earningsCAGR') is not None else r.get('earningsGrowthYoY')
        r['gap'] = (growth - pc) if (growth is not None and pc is not None) else None
        dg = y.dividend_growth(sym)
        if dg:
            r.update(dg)
        fh = y.fundamentals_history(sym)
        if fh:
            r.update(fh)
        r['symbol'] = sym
        out.append({k: v for k, v in r.items() if v is not None})   # pas de null
        time.sleep(y.pause)
    push(db, 'stocks/screener/positionMeta', out)
    print(f'positionMeta pousse : {len(out)} tickers detenus ({", ".join(p["symbol"] for p in out)})')


def main():
    apply_firebase_config()
    y = Yahoo()
    db = os.environ.get('FIREBASE_DB_URL')
    do_push = (not NO_PUSH) and bool(db)
    from firebase_push import push

    if MODE in (None, 'smallcap'):
        out = run_smallcap(y)
        if out and out[0]:
            payload, positions, account = out
            if do_push:
                push(db, 'stocks/screener/smallcap', payload)
                push(db, 'stocks/screener/latest', payload)  # compat
                push(db, 'stocks/screener/positions', {'generatedAt': payload['generatedAt'], 'account': account, 'positions': positions})
                print(f"Pousse smallcap ({len(payload['top'])}) + positions ({len(positions)}).")
            else:
                print('\n(pas de push) Small-cap top 10 :')
                for c in payload['top'][:10]:
                    m = c['metrics']
                    print(f"  {c['symbol']:<6} {c['score']:<5} CA={_p(m.get('revenueGrowthYoY'))} 52s={_p(m.get('distToHigh'))} {' '.join(c['flags'][:2])}")

    if MODE in (None, 'quality'):
        payload = run_quality(y)
        if payload:
            if do_push:
                push(db, 'stocks/screener/quality', payload)
                print(f"Pousse qualite ({len(payload['top'])}).")
                push_position_meta(y, db)   # fondamentaux des titres detenus hors univers (Mes positions)
            else:
                print('\n(pas de push) Qualite top 12 :')
                for c in payload['top'][:12]:
                    m = c['metrics']
                    print(f"  {c['symbol']:<6} {c['rating']:<12} PEG={_num2(m.get('peg'))} ecart-benef/cours={_p(m.get('gap'))} PEfwd={_num2(m.get('forwardPE'))}")


def _p(x):
    return '-' if x is None else ('%+.0f%%' % (x * 100))


def _num2(x):
    return '-' if isinstance(x, str) or x is None else ('%.1f' % x)


if __name__ == '__main__':
    if WATCH:
        import time
        _db = os.environ.get('FIREBASE_DB_URL')
        from firebase_push import get as _get

        def _token():
            c = _get(_db, 'stocks/screener/config') if _db else None
            return c.get('runRequested') if isinstance(c, dict) else None

        print('Mode --watch actif : relance a chaque "Appliquer" depuis le dashboard (Ctrl+C pour arreter).')
        _last = _token()
        main()
        while True:
            time.sleep(20)
            _t = _token()
            if _t is not None and _t != _last:
                _last = _t
                print(f'--- config modifiee (runRequested={_t}) -> relance ---')
                try:
                    main()
                except Exception as _e:
                    print('run echoue:', _e)
    else:
        main()
