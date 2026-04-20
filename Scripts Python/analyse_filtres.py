"""
Analyse des trades gagnants vs perdants pour identifier des filtres.
Facteurs testes:
  1. Volatilite (ATR)
  2. Tendance (SMA)
  3. Heure de la journee
  4. Jour de la semaine
  5. Vitesse du franchissement (momentum)
  6. Distance au chiffre rond a l'entree
  7. Nombre de franchissements recents du meme niveau
  8. Range de la session avant le signal
"""
import pandas as pd
import numpy as np
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\quinson\Desktop\Claude')

from backtest_round_numbers import (
    build_market_hours_mask_fast, detect_crossings_vectorized,
    apply_2h_filter, simulate_trades, compute_metrics
)

CSV_PATH = r"C:\Users\quinson\Desktop\Claude\Historique données bourse\historique_usa30idxusd_1min.csv"

print("Chargement des donnees...", flush=True)
df = pd.read_csv(CSV_PATH, sep=';', decimal=',', parse_dates=['Date'])
market_mask = build_market_hours_mask_fast(df)
closes = df['Close'].values
highs = df['High'].values
lows = df['Low'].values

# Precalculer des indicateurs
print("Calcul des indicateurs...", flush=True)

# ATR 60 min (1h)
tr = np.maximum(highs[1:] - lows[1:],
                np.maximum(abs(highs[1:] - closes[:-1]),
                           abs(lows[1:] - closes[:-1])))
tr = np.insert(tr, 0, highs[0] - lows[0])
atr60 = pd.Series(tr).rolling(60).mean().values

# ATR 390 min (~1 session)
atr390 = pd.Series(tr).rolling(390).mean().values

# SMA 200 barres (~3h20)
sma200 = pd.Series(closes).rolling(200).mean().values

# SMA 1000 barres (~16h = ~2.5 sessions)
sma1000 = pd.Series(closes).rolling(1000).mean().values

# RSI 14 periodes (sur 1 min)
delta = pd.Series(closes).diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / loss
rsi14 = (100 - 100 / (1 + rs)).values

# Range de la session en cours (depuis 14:30 UTC)
session_range = np.zeros(len(df))
session_high = closes[0]
session_low = closes[0]
prev_hour = -1
for i in range(len(df)):
    h = df['Date'].iloc[i].hour
    m = df['Date'].iloc[i].minute
    # Reset au debut de la session (~14:30 UTC hiver)
    if (h == 14 and m == 30) or (h == 13 and m == 30):
        session_high = highs[i]
        session_low = lows[i]
    else:
        session_high = max(session_high, highs[i])
        session_low = min(session_low, lows[i])
    session_range[i] = session_high - session_low

print("Detection des signaux et simulation...", flush=True)
crossings = detect_crossings_vectorized(closes, market_mask.values, [1000])
signals = apply_2h_filter(crossings, 120)
trades = simulate_trades(df, signals, 0.3, 0.5)

print(f"{len(trades)} trades a analyser\n")

# =====================================================
# Enrichir chaque trade avec des features
# =====================================================

for t in trades:
    i = t['entry_idx']
    t['hour_utc'] = df['Date'].iloc[i].hour
    t['minute'] = df['Date'].iloc[i].minute
    t['weekday'] = df['Date'].iloc[i].weekday()  # 0=lundi
    t['weekday_name'] = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'][t['weekday']]
    t['atr60'] = atr60[i] if not np.isnan(atr60[i]) else 0
    t['atr390'] = atr390[i] if not np.isnan(atr390[i]) else 0
    t['sma200'] = sma200[i] if not np.isnan(sma200[i]) else 0
    t['sma1000'] = sma1000[i] if not np.isnan(sma1000[i]) else 0
    t['rsi14'] = rsi14[i] if not np.isnan(rsi14[i]) else 50
    t['session_range'] = session_range[i]

    # Tendance: prix au-dessus ou en dessous de la SMA
    if t['sma1000'] > 0:
        t['trend'] = 'UP' if closes[i] > t['sma1000'] else 'DOWN'
    else:
        t['trend'] = 'N/A'

    # Avec-tendance ou contre-tendance
    if t['trend'] == 'UP':
        t['with_trend'] = 1 if t['direction'] == 'BUY' else 0
    elif t['trend'] == 'DOWN':
        t['with_trend'] = 1 if t['direction'] == 'SELL' else 0
    else:
        t['with_trend'] = -1

    # Distance au chiffre rond (en points)
    t['dist_round'] = abs(t['entry_price'] - t['level'])

    # Momentum: vitesse sur les 5 dernieres barres (pts/min)
    if i >= 5:
        t['momentum_5'] = abs(closes[i] - closes[i-5]) / 5
    else:
        t['momentum_5'] = 0

    # Momentum 15 barres
    if i >= 15:
        t['momentum_15'] = abs(closes[i] - closes[i-15]) / 15
    else:
        t['momentum_15'] = 0

    # ATR relative (% du prix)
    t['atr60_pct'] = t['atr60'] / closes[i] * 100 if closes[i] > 0 else 0
    t['atr390_pct'] = t['atr390'] / closes[i] * 100 if closes[i] > 0 else 0

    # Volatilite normalisee: session range / prix (%)
    t['session_range_pct'] = t['session_range'] / closes[i] * 100 if closes[i] > 0 else 0

    # Win ou lose
    t['win'] = 1 if t['pnl_points'] > 0 else 0
    t['result_cat'] = 'TP' if t['result'] == 'tp' else ('SL' if t['result'] == 'sl' else 'Timeout')


tdf = pd.DataFrame(trades)

# =====================================================
# ANALYSES
# =====================================================

def print_analysis(title, group_col, tdf):
    """Affiche les stats par groupe."""
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}\n")
    grouped = tdf.groupby(group_col)
    rows = []
    for name, g in grouped:
        n = len(g)
        w = g['win'].sum()
        wr = w / n * 100 if n > 0 else 0
        pnl = g['pnl_points'].sum()
        avg_pnl = g['pnl_points'].mean()
        wins_sum = g.loc[g['pnl_points'] > 0, 'pnl_points'].sum()
        losses_sum = abs(g.loc[g['pnl_points'] <= 0, 'pnl_points'].sum())
        pf = wins_sum / losses_sum if losses_sum > 0 else float('inf')
        rows.append((name, n, wr, pnl, avg_pnl, pf))

    print(f"{'Groupe':<15} {'Trades':>7} {'Win%':>7} {'PnL (pts)':>12} {'Avg PnL':>10} {'PF':>7}")
    print("-" * 62)
    for name, n, wr, pnl, avg_pnl, pf in rows:
        pf_str = f"{pf:.2f}" if pf != float('inf') else "INF"
        print(f"{str(name):<15} {n:>7} {wr:>6.1f}% {pnl:>+12,.0f} {avg_pnl:>+10.1f} {pf_str:>7}")


# --- 1. HEURE DE LA JOURNEE ---
# Convertir heure UTC en heure Paris approximative (+1 ou +2)
tdf['hour_paris'] = tdf['hour_utc'] + 1  # Approximation CET
tdf.loc[tdf['hour_paris'] > 23, 'hour_paris'] = tdf['hour_utc'] + 2  # CEST
# Creer des tranches horaires
def hour_bucket(h):
    if h <= 15: return '15h30-16h'
    elif h <= 16: return '16h-17h'
    elif h <= 17: return '17h-18h'
    elif h <= 18: return '18h-19h'
    elif h <= 19: return '19h-20h'
    elif h <= 20: return '20h-21h'
    else: return '21h-22h'

tdf['heure_tranche'] = tdf['hour_utc'].apply(lambda h: hour_bucket(h+1))
print_analysis("PAR TRANCHE HORAIRE (heure Paris approx.)", 'heure_tranche', tdf)

# --- 2. JOUR DE LA SEMAINE ---
print_analysis("PAR JOUR DE LA SEMAINE", 'weekday_name', tdf)

# --- 3. VOLATILITE (ATR 1h) ---
tdf['atr60_bucket'] = pd.qcut(tdf['atr60'], q=4, labels=['Basse','Moyenne-','Moyenne+','Haute'])
print_analysis("PAR VOLATILITE (ATR 1h, quartiles)", 'atr60_bucket', tdf)

# --- 4. VOLATILITE SESSION ---
tdf['sessrange_bucket'] = pd.qcut(tdf['session_range_pct'], q=4, labels=['Faible','Moyen-','Moyen+','Fort'], duplicates='drop')
print_analysis("PAR RANGE DE LA SESSION (% du prix)", 'sessrange_bucket', tdf)

# --- 5. TENDANCE (SMA 1000) ---
print_analysis("PAR TENDANCE (SMA 1000 barres)", 'trend', tdf)

# --- 6. AVEC / CONTRE TENDANCE ---
tdf['trend_align'] = tdf['with_trend'].map({1: 'Avec tendance', 0: 'Contre tendance', -1: 'N/A'})
print_analysis("AVEC vs CONTRE TENDANCE", 'trend_align', tdf)

# --- 7. MOMENTUM AU FRANCHISSEMENT ---
tdf['momentum_bucket'] = pd.qcut(tdf['momentum_5'], q=4, labels=['Lent','Moyen-','Moyen+','Rapide'], duplicates='drop')
print_analysis("PAR MOMENTUM (vitesse franchissement, 5 barres)", 'momentum_bucket', tdf)

# --- 8. DISTANCE AU CHIFFRE ROND ---
tdf['dist_bucket'] = pd.qcut(tdf['dist_round'], q=4, labels=['Tres proche','Proche','Moyen','Loin'], duplicates='drop')
print_analysis("PAR DISTANCE AU CHIFFRE ROND A L'ENTREE", 'dist_bucket', tdf)

# --- 9. RSI ---
def rsi_bucket(r):
    if r < 30: return 'Survendu (<30)'
    elif r < 40: return 'Bas (30-40)'
    elif r < 60: return 'Neutre (40-60)'
    elif r < 70: return 'Haut (60-70)'
    else: return 'Surachete (>70)'

tdf['rsi_bucket'] = tdf['rsi14'].apply(rsi_bucket)
print_analysis("PAR RSI (14 periodes)", 'rsi_bucket', tdf)

# --- 10. DIRECTION (rappel) ---
print_analysis("PAR DIRECTION", 'direction', tdf)

# --- 11. TYPE DE SORTIE ---
print_analysis("PAR TYPE DE SORTIE", 'result_cat', tdf)

# =====================================================
# CORRELATIONS
# =====================================================
print(f"\n{'='*65}")
print("  CORRELATIONS AVEC LE RESULTAT (win=1, lose=0)")
print(f"{'='*65}\n")

numeric_features = ['atr60', 'atr390', 'atr60_pct', 'session_range_pct',
                    'momentum_5', 'momentum_15', 'dist_round', 'rsi14',
                    'hour_utc', 'weekday', 'with_trend']

print(f"{'Feature':<25} {'Correlation':>12} {'Interpretation'}")
print("-" * 65)
for feat in numeric_features:
    valid = tdf[[feat, 'win']].dropna()
    if len(valid) > 10:
        corr = valid[feat].corr(valid['win'])
        # Interpretation
        if abs(corr) < 0.03:
            interp = "Pas d'impact"
        elif corr > 0.1:
            interp = ">> FAVORISE les gains"
        elif corr > 0.03:
            interp = "> Legerement positif"
        elif corr < -0.1:
            interp = ">> FAVORISE les pertes"
        elif corr < -0.03:
            interp = "> Legerement negatif"
        else:
            interp = "Negligeable"
        print(f"{feat:<25} {corr:>+12.4f} {interp}")

# =====================================================
# FILTRE COMBINE: meilleures conditions
# =====================================================
print(f"\n{'='*65}")
print("  TEST DE FILTRES COMBINES")
print(f"{'='*65}")

def test_filter(name, mask, tdf):
    """Teste un filtre et affiche les resultats."""
    filtered = tdf[mask]
    excluded = tdf[~mask]
    if len(filtered) == 0:
        print(f"  {name}: 0 trades (filtre trop restrictif)")
        return

    w_f = filtered['win'].sum()
    wr_f = w_f / len(filtered) * 100
    pnl_f = filtered['pnl_points'].sum()
    wins_f = filtered.loc[filtered['pnl_points'] > 0, 'pnl_points'].sum()
    losses_f = abs(filtered.loc[filtered['pnl_points'] <= 0, 'pnl_points'].sum())
    pf_f = wins_f / losses_f if losses_f > 0 else float('inf')

    w_e = excluded['win'].sum() if len(excluded) > 0 else 0
    wr_e = w_e / len(excluded) * 100 if len(excluded) > 0 else 0
    pnl_e = excluded['pnl_points'].sum() if len(excluded) > 0 else 0

    pf_str = f"{pf_f:.2f}" if pf_f != float('inf') else "INF"
    print(f"\n  FILTRE: {name}")
    print(f"  Gardes : {len(filtered):>4} trades | Win {wr_f:.1f}% | PnL {pnl_f:>+8,.0f} pts | PF {pf_str}")
    print(f"  Exclus : {len(excluded):>4} trades | Win {wr_e:.1f}% | PnL {pnl_e:>+8,.0f} pts")
    print(f"  {'>>> AMELIORATION' if pf_f > 1.15 else '    Pas concluant'}")

# Reference
print(f"\n  REFERENCE (sans filtre):")
ref_wr = tdf['win'].sum() / len(tdf) * 100
ref_pnl = tdf['pnl_points'].sum()
ref_wins = tdf.loc[tdf['pnl_points'] > 0, 'pnl_points'].sum()
ref_losses = abs(tdf.loc[tdf['pnl_points'] <= 0, 'pnl_points'].sum())
ref_pf = ref_wins / ref_losses if ref_losses > 0 else 0
print(f"  {len(tdf)} trades | Win {ref_wr:.1f}% | PnL {ref_pnl:>+8,.0f} pts | PF {ref_pf:.2f}")

# Filtres individuels
atr60_median = tdf['atr60'].median()
atr60_q25 = tdf['atr60'].quantile(0.25)
atr60_q75 = tdf['atr60'].quantile(0.75)
mom5_median = tdf['momentum_5'].median()
dist_median = tdf['dist_round'].median()

test_filter("Volatilite basse (ATR60 < mediane)", tdf['atr60'] < atr60_median, tdf)
test_filter("Volatilite haute (ATR60 > mediane)", tdf['atr60'] >= atr60_median, tdf)
test_filter("Volatilite tres basse (ATR60 < Q25)", tdf['atr60'] < atr60_q25, tdf)
test_filter("Volatilite tres haute (ATR60 > Q75)", tdf['atr60'] >= atr60_q75, tdf)
test_filter("Avec la tendance (SMA1000)", tdf['with_trend'] == 1, tdf)
test_filter("Contre la tendance (SMA1000)", tdf['with_trend'] == 0, tdf)
test_filter("Momentum lent (< mediane)", tdf['momentum_5'] < mom5_median, tdf)
test_filter("Momentum rapide (>= mediane)", tdf['momentum_5'] >= mom5_median, tdf)
test_filter("Proche du chiffre rond (< mediane)", tdf['dist_round'] < dist_median, tdf)
test_filter("Loin du chiffre rond (>= mediane)", tdf['dist_round'] >= dist_median, tdf)
test_filter("RSI neutre (40-60)", (tdf['rsi14'] >= 40) & (tdf['rsi14'] <= 60), tdf)
test_filter("RSI extreme (<30 ou >70)", (tdf['rsi14'] < 30) | (tdf['rsi14'] > 70), tdf)
test_filter("Session range faible (<0.5%)", tdf['session_range_pct'] < 0.5, tdf)
test_filter("Session range fort (>1%)", tdf['session_range_pct'] > 1.0, tdf)
test_filter("Heures 15h30-18h", tdf['hour_utc'].isin([13,14,15,16]), tdf)
test_filter("Heures 18h-22h", tdf['hour_utc'].isin([17,18,19,20]), tdf)

# Filtres combines
test_filter("Vol basse + Avec tendance",
            (tdf['atr60'] < atr60_median) & (tdf['with_trend'] == 1), tdf)
test_filter("Vol basse + Momentum lent",
            (tdf['atr60'] < atr60_median) & (tdf['momentum_5'] < mom5_median), tdf)
test_filter("Avec tendance + Momentum lent",
            (tdf['with_trend'] == 1) & (tdf['momentum_5'] < mom5_median), tdf)
test_filter("Vol basse + Avec tendance + Momentum lent",
            (tdf['atr60'] < atr60_median) & (tdf['with_trend'] == 1) & (tdf['momentum_5'] < mom5_median), tdf)
test_filter("Vol basse + RSI neutre",
            (tdf['atr60'] < atr60_median) & (tdf['rsi14'] >= 40) & (tdf['rsi14'] <= 60), tdf)
test_filter("Avec tendance + Session range < 1%",
            (tdf['with_trend'] == 1) & (tdf['session_range_pct'] < 1.0), tdf)
test_filter("Heures 15h30-18h + Vol basse",
            tdf['hour_utc'].isin([13,14,15,16]) & (tdf['atr60'] < atr60_median), tdf)

print(f"\n{'='*65}")
print("  Analyse terminee.")
print(f"{'='*65}")
