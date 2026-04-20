"""
Analyse detaillee du filtre DISTANCE AU CHIFFRE ROND.
Objectif: trouver le seuil optimal de distance max pour filtrer les trades.

La distance = abs(prix_entree - niveau_rond_franchi)
Plus on entre pres du chiffre rond, meilleur est le trade (hypothese a valider).
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

print("Detection des signaux...", flush=True)
crossings = detect_crossings_vectorized(closes, market_mask.values, [1000])
signals = apply_2h_filter(crossings, 120)

# =====================================================
# Tester avec TP=0.3% SL=0.5% (config actuelle PRT)
# =====================================================
trades = simulate_trades(df, signals, 0.3, 0.5)

# Ajouter la distance au chiffre rond
for t in trades:
    t['dist_round'] = abs(t['entry_price'] - t['level'])
    t['dist_round_pct'] = t['dist_round'] / t['entry_price'] * 100
    t['win'] = 1 if t['pnl_points'] > 0 else 0

tdf = pd.DataFrame(trades)

print(f"\n{len(tdf)} trades au total")
print(f"Distance min:    {tdf['dist_round'].min():.1f} pts")
print(f"Distance max:    {tdf['dist_round'].max():.1f} pts")
print(f"Distance mediane:{tdf['dist_round'].median():.1f} pts")
print(f"Distance moyenne:{tdf['dist_round'].mean():.1f} pts")

# =====================================================
# 1. DISTRIBUTION DE LA DISTANCE
# =====================================================
print(f"\n{'='*70}")
print("  DISTRIBUTION DE LA DISTANCE AU CHIFFRE ROND")
print(f"{'='*70}\n")

# Par quantiles
print("--- Par quantiles ---\n")
quantiles = [0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0]
for q in quantiles:
    val = tdf['dist_round'].quantile(q)
    print(f"  Q{q*100:>5.0f}% : {val:>8.1f} pts ({val/tdf['entry_price'].mean()*100:.3f}% du prix)")

# =====================================================
# 2. TEST PAR SEUIL ABSOLU (en points)
# =====================================================
print(f"\n{'='*70}")
print("  TEST PAR SEUIL DE DISTANCE MAX (en points)")
print(f"{'='*70}\n")

# Tester des seuils de 10 en 10, puis plus fins autour du meilleur
thresholds_pts = list(range(10, 210, 10)) + [5, 15, 25, 35, 45, 55, 250, 300, 400, 500]
thresholds_pts = sorted(set(thresholds_pts))

print(f"{'MaxDist (pts)':>15} {'Trades':>7} {'Gardes%':>8} {'Win%':>7} {'PnL (pts)':>12} {'PF':>7} {'AvgWin':>8} {'AvgLoss':>9} {'MaxDD':>8}")
print("-" * 95)

best_pf_pts = 0
best_threshold_pts = 0
results_pts = []

for threshold in thresholds_pts:
    mask = tdf['dist_round'] <= threshold
    filtered = tdf[mask]
    n = len(filtered)
    if n < 10:
        continue

    wins = filtered[filtered['pnl_points'] > 0]
    losses = filtered[filtered['pnl_points'] <= 0]
    pnl = filtered['pnl_points'].sum()
    wr = len(wins) / n * 100
    wins_sum = wins['pnl_points'].sum() if len(wins) > 0 else 0
    losses_sum = abs(losses['pnl_points'].sum()) if len(losses) > 0 else 0
    pf = wins_sum / losses_sum if losses_sum > 0 else float('inf')
    avg_win = wins['pnl_points'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl_points'].mean() if len(losses) > 0 else 0

    # Max drawdown
    cumul = filtered['pnl_points'].cumsum()
    peak = cumul.cummax()
    dd = (peak - cumul).max()

    pf_str = f"{pf:.2f}" if pf != float('inf') else "INF"
    pct_kept = n / len(tdf) * 100
    print(f"{threshold:>15} {n:>7} {pct_kept:>7.1f}% {wr:>6.1f}% {pnl:>+12,.0f} {pf_str:>7} {avg_win:>+8.1f} {avg_loss:>+9.1f} {dd:>8,.0f}")

    results_pts.append({
        'threshold': threshold,
        'n_trades': n,
        'pct_kept': pct_kept,
        'win_rate': wr,
        'pnl': pnl,
        'pf': pf,
        'max_dd': dd
    })

    if pf > best_pf_pts and n >= 50:  # Au moins 50 trades pour etre significatif
        best_pf_pts = pf
        best_threshold_pts = threshold

# =====================================================
# 3. TEST PAR SEUIL EN % DU PRIX
# =====================================================
print(f"\n{'='*70}")
print("  TEST PAR SEUIL DE DISTANCE MAX (en % du prix)")
print(f"{'='*70}\n")

thresholds_pct = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10,
                  0.12, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]

print(f"{'MaxDist (%)':>15} {'Trades':>7} {'Gardes%':>8} {'Win%':>7} {'PnL (pts)':>12} {'PF':>7} {'AvgWin':>8} {'AvgLoss':>9} {'MaxDD':>8}")
print("-" * 95)

best_pf_pct = 0
best_threshold_pct = 0

for threshold in thresholds_pct:
    mask = tdf['dist_round_pct'] <= threshold
    filtered = tdf[mask]
    n = len(filtered)
    if n < 10:
        continue

    wins = filtered[filtered['pnl_points'] > 0]
    losses = filtered[filtered['pnl_points'] <= 0]
    pnl = filtered['pnl_points'].sum()
    wr = len(wins) / n * 100
    wins_sum = wins['pnl_points'].sum() if len(wins) > 0 else 0
    losses_sum = abs(losses['pnl_points'].sum()) if len(losses) > 0 else 0
    pf = wins_sum / losses_sum if losses_sum > 0 else float('inf')
    avg_win = wins['pnl_points'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl_points'].mean() if len(losses) > 0 else 0

    cumul = filtered['pnl_points'].cumsum()
    peak = cumul.cummax()
    dd = (peak - cumul).max()

    pf_str = f"{pf:.2f}" if pf != float('inf') else "INF"
    pct_kept = n / len(tdf) * 100
    print(f"{threshold:>14.2f}% {n:>7} {pct_kept:>7.1f}% {wr:>6.1f}% {pnl:>+12,.0f} {pf_str:>7} {avg_win:>+8.1f} {avg_loss:>+9.1f} {dd:>8,.0f}")

    if pf > best_pf_pct and n >= 50:
        best_pf_pct = pf
        best_threshold_pct = threshold

# =====================================================
# 4. RESUME ET RECOMMANDATION
# =====================================================
print(f"\n{'='*70}")
print("  RECOMMANDATION")
print(f"{'='*70}\n")

print(f"  Meilleur seuil absolu (>= 50 trades) : {best_threshold_pts} pts (PF {best_pf_pts:.2f})")
print(f"  Meilleur seuil relatif (>= 50 trades): {best_threshold_pct:.2f}% (PF {best_pf_pct:.2f})")

# Le seuil en points est plus simple a implementer dans PRT
# mais le % s'adapte mieux a l'evolution du prix de l'indice
print(f"\n  Note: le seuil en % s'adapte a la valeur de l'indice (meilleur long terme)")
print(f"  Note: le seuil en points est plus simple a implementer dans PRT")

# =====================================================
# 5. AUSSI TESTER AVEC TP=0.5% SL=0.5% (meilleur combo global)
# =====================================================
print(f"\n{'='*70}")
print("  VERIFICATION AVEC TP=0.5% SL=0.5% (meilleur combo global)")
print(f"{'='*70}\n")

trades2 = simulate_trades(df, signals, 0.5, 0.5)
for t in trades2:
    t['dist_round'] = abs(t['entry_price'] - t['level'])
    t['dist_round_pct'] = t['dist_round'] / t['entry_price'] * 100
tdf2 = pd.DataFrame(trades2)

# Tester les seuils cles
key_thresholds = [30, 40, 50, 60, 70, 80, 90, 100, 120, 150, 200, 500]
print(f"{'MaxDist (pts)':>15} {'Trades':>7} {'Win%':>7} {'PnL (pts)':>12} {'PF':>7} {'MaxDD':>8}")
print("-" * 65)

# Reference sans filtre
ref2 = compute_metrics(trades2)
pf_ref = f"{ref2['profit_factor']:.2f}" if ref2['profit_factor'] != float('inf') else "INF"
print(f"{'(sans filtre)':>15} {ref2['n_trades']:>7} {ref2['win_rate']:>6.1f}% {ref2['pnl_total']:>+12,.0f} {pf_ref:>7} {ref2['max_dd']:>8,.0f}")

for threshold in key_thresholds:
    mask = tdf2['dist_round'] <= threshold
    filtered = tdf2[mask]
    n = len(filtered)
    if n < 10:
        continue
    wins = filtered[filtered['pnl_points'] > 0]
    losses = filtered[filtered['pnl_points'] <= 0]
    pnl = filtered['pnl_points'].sum()
    wr = len(wins) / n * 100
    wins_sum = wins['pnl_points'].sum() if len(wins) > 0 else 0
    losses_sum = abs(losses['pnl_points'].sum()) if len(losses) > 0 else 0
    pf = wins_sum / losses_sum if losses_sum > 0 else float('inf')
    cumul = filtered['pnl_points'].cumsum()
    peak = cumul.cummax()
    dd = (peak - cumul).max()
    pf_str = f"{pf:.2f}" if pf != float('inf') else "INF"
    print(f"{threshold:>15} {n:>7} {wr:>6.1f}% {pnl:>+12,.0f} {pf_str:>7} {dd:>8,.0f}")

# =====================================================
# 6. DETAIL : trades proches vs loin
# =====================================================
print(f"\n{'='*70}")
print("  DETAIL: COMPARAISON TRADES PROCHES vs LOIN (TP=0.3% SL=0.5%)")
print(f"{'='*70}\n")

# Utiliser le meilleur seuil trouve
threshold_detail = best_threshold_pts
proches = tdf[tdf['dist_round'] <= threshold_detail]
loin = tdf[tdf['dist_round'] > threshold_detail]

print(f"  Seuil utilise: {threshold_detail} pts\n")
print(f"  {'':>15} {'PROCHES':>15} {'LOIN':>15}")
print(f"  {'-'*45}")
print(f"  {'Trades':<15} {len(proches):>15} {len(loin):>15}")

if len(proches) > 0 and len(loin) > 0:
    wp = proches['win'].sum() / len(proches) * 100
    wl = loin['win'].sum() / len(loin) * 100
    print(f"  {'Win rate':<15} {wp:>14.1f}% {wl:>14.1f}%")

    pp = proches['pnl_points'].sum()
    pl = loin['pnl_points'].sum()
    print(f"  {'PnL total':<15} {pp:>+15,.0f} {pl:>+15,.0f}")

    wins_p = proches.loc[proches['pnl_points'] > 0, 'pnl_points'].sum()
    loss_p = abs(proches.loc[proches['pnl_points'] <= 0, 'pnl_points'].sum())
    pf_p = wins_p / loss_p if loss_p > 0 else float('inf')

    wins_l = loin.loc[loin['pnl_points'] > 0, 'pnl_points'].sum()
    loss_l = abs(loin.loc[loin['pnl_points'] <= 0, 'pnl_points'].sum())
    pf_l = wins_l / loss_l if loss_l > 0 else float('inf')

    pf_p_str = f"{pf_p:.2f}" if pf_p != float('inf') else "INF"
    pf_l_str = f"{pf_l:.2f}" if pf_l != float('inf') else "INF"
    print(f"  {'Profit Factor':<15} {pf_p_str:>15} {pf_l_str:>15}")

    avg_dist_p = proches['dist_round'].mean()
    avg_dist_l = loin['dist_round'].mean()
    print(f"  {'Dist moyenne':<15} {avg_dist_p:>14.1f}p {avg_dist_l:>14.1f}p")

    # Montrer les trades exclus (ceux qui etaient gagnants)
    loin_wins = loin[loin['pnl_points'] > 0]
    loin_losses = loin[loin['pnl_points'] <= 0]
    print(f"\n  Trades EXCLUS (loin): {len(loin_wins)} gagnants elimines, {len(loin_losses)} perdants elimines")
    print(f"  Ratio de gains exclus: {loin_wins['pnl_points'].sum():+,.0f} pts (manques)")
    print(f"  Ratio de pertes evitees: {abs(loin_losses['pnl_points'].sum()):,.0f} pts (evites)")
    print(f"  Benefice net du filtre: {abs(loin_losses['pnl_points'].sum()) - loin_wins['pnl_points'].sum():+,.0f} pts")

print(f"\n{'='*70}")
print("  Analyse distance terminee.")
print(f"{'='*70}")
