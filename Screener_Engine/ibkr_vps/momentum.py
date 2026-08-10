# momentum.py — calcul de momentum / force relative depuis des barres journalieres IBKR.
# Pur (aucun I/O, aucune dependance IBKR), donc testable en local.

from statistics import mean


def _sma(values, n):
    if len(values) < n:
        return None
    return mean(values[-n:])


def compute_momentum(bars):
    """
    bars : liste de dicts ordonnes du PLUS ANCIEN au PLUS RECENT, chacun avec
           {'close': float, 'high': float, 'low': float, 'volume': float}.
    Renvoie un dict de metriques de momentum, ou None si pas assez d'historique.
    """
    if not bars or len(bars) < 30:
        return None
    closes = [b['close'] for b in bars if b.get('close') is not None]
    highs = [b.get('high', b['close']) for b in bars]
    vols = [b.get('volume') or 0 for b in bars]
    if len(closes) < 30:
        return None

    price = closes[-1]
    ma50 = _sma(closes, 50)
    ma200 = _sma(closes, 200)

    def perf(n):
        return (price / closes[-1 - n] - 1) if len(closes) > n and closes[-1 - n] else None

    perf_1m = perf(21)
    perf_3m = perf(63)
    perf_6m = perf(126)
    perf_12m = perf(252)

    window52 = highs[-252:] if len(highs) >= 252 else highs
    high_52w = max(window52) if window52 else None
    dist_to_high = (price / high_52w - 1) if high_52w else None

    # ATR14 (volatilite) a partir de high/low/close
    atr = None
    if len(bars) >= 15:
        trs = []
        for i in range(1, len(bars)):
            h = bars[i].get('high', bars[i]['close'])
            l = bars[i].get('low', bars[i]['close'])
            pc = bars[i - 1]['close']
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if len(trs) >= 14:
            atr = mean(trs[-14:])

    avg_vol50 = _sma(vols, 50) or (mean(vols) if vols else 0)
    dollar_vol = price * avg_vol50 if avg_vol50 else None

    uptrend = (ma200 is not None and price > ma200 and (ma50 is None or ma50 > ma200))

    return {
        'price': round(price, 4),
        'ma50': round(ma50, 4) if ma50 else None,
        'ma200': round(ma200, 4) if ma200 else None,
        'vsMa200': round(price / ma200 - 1, 4) if ma200 else None,
        'perf1m': _r(perf_1m), 'perf3m': _r(perf_3m), 'perf6m': _r(perf_6m), 'perf12m': _r(perf_12m),
        'high52w': round(high_52w, 4) if high_52w else None,
        'distToHigh': _r(dist_to_high),
        'atr14': round(atr, 4) if atr else None,
        'atrPct': round(atr / price, 4) if atr and price else None,
        'avgVolume50': round(avg_vol50) if avg_vol50 else None,
        'dollarVolume': round(dollar_vol) if dollar_vol else None,
        'uptrend': uptrend,
        'bars': len(bars),
    }


def _r(x):
    return round(x, 4) if isinstance(x, (int, float)) else None


def momentum_score(m):
    """
    Score de momentum 0-100 (heuristique, sert a BLENDER avec le score fondamental FMP).
    Combine tendance (vs MM200), proximite du plus-haut 52s, et perf 6/12 mois.
    Volontairement borne pour ne pas laisser une perf extreme tout ecraser.
    """
    if not m:
        return None
    parts = []
    if m.get('vsMa200') is not None:
        parts.append(_clamp01((m['vsMa200'] + 0.10) / 0.60))          # -10%..+50% -> 0..1
    if m.get('distToHigh') is not None:
        parts.append(_clamp01((m['distToHigh'] + 0.30) / 0.30))        # -30%..0% -> 0..1
    if m.get('perf6m') is not None:
        parts.append(_clamp01((m['perf6m'] + 0.10) / 0.70))            # -10%..+60% -> 0..1
    if m.get('perf12m') is not None:
        parts.append(_clamp01((m['perf12m'] + 0.10) / 1.10))           # -10%..+100% -> 0..1
    if not parts:
        return None
    base = 100 * (sum(parts) / len(parts))
    if not m.get('uptrend'):
        base *= 0.7   # meme malus que le screener : le growth agressif exige la confirmation prix
    return round(base, 1)


def _clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)
