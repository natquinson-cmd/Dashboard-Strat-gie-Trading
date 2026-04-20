"""Compare PRT backtest results with Python backtest for the same period."""
import pandas as pd
import numpy as np
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# =====================================================
# 1. CHARGER ET ANALYSER LES TRADES PRT
# =====================================================

PRT_PATH = r"C:\Users\quinson\Downloads\Rapport détaillé - ProBacktest - DOW 1 min - chiffres ronds V1 - 1 minute - Wall Street Cash (1€).csv"

prt = pd.read_csv(PRT_PATH, sep='\t', encoding='windows-1252', skipinitialspace=True)
prt = prt.dropna(how='all')
prt.columns = [c.strip().strip('"') for c in prt.columns]

# Extraire gain unitaire (nettoyer le format)
gains_raw = prt['Gain unitaire'].astype(str).str.replace('"','').str.replace('+','').str.replace(',','.').str.strip()
prt_gains = pd.to_numeric(gains_raw, errors='coerce').dropna()

# Types
types = prt['Type'].astype(str).str.replace('"','').str.strip()

n_prt = len(prt_gains)
wins_prt = prt_gains[prt_gains > 0]
losses_prt = prt_gains[prt_gains <= 0]
pnl_prt = prt_gains.sum()
pf_prt = wins_prt.sum() / abs(losses_prt.sum()) if losses_prt.sum() != 0 else float('inf')

cum_prt = prt_gains.iloc[::-1].cumsum()  # PRT est en ordre inverse (recent en haut)
peak_prt = cum_prt.cummax()
dd_prt = peak_prt - cum_prt
maxdd_prt = dd_prt.max()

# Direction
longs_prt = prt_gains[types == 'Long']
shorts_prt = prt_gains[types == 'Court']

print("=" * 65)
print("  COMPARAISON PRT vs PYTHON (15 aout 2025 - 2 mars 2026)")
print("=" * 65)

print("\n--- RESULTATS PRT ---\n")
print(f"  Trades        : {n_prt}")
print(f"  Gagnants      : {len(wins_prt)} ({len(wins_prt)/n_prt*100:.1f}%)")
print(f"  Perdants      : {len(losses_prt)}")
print(f"  PnL total     : {pnl_prt:+,.1f} pts")
print(f"  Gain moyen    : {wins_prt.mean():+,.1f} pts")
print(f"  Perte moyenne : {losses_prt.mean():+,.1f} pts")
print(f"  Profit Factor : {pf_prt:.2f}")
print(f"  Max Drawdown  : {maxdd_prt:,.1f} pts")
print(f"  BUY  (Long)   : {len(longs_prt)} trades, PnL {longs_prt.sum():+,.1f} pts")
print(f"  SELL (Court)  : {len(shorts_prt)} trades, PnL {shorts_prt.sum():+,.1f} pts")

# =====================================================
# 2. LANCER LE BACKTEST PYTHON SUR LA MEME PERIODE
# =====================================================

# Importer les fonctions du backtest
sys.path.insert(0, r'C:\Users\quinson\Desktop\Claude')
from backtest_round_numbers import (
    build_market_hours_mask_fast, detect_crossings_vectorized,
    apply_2h_filter, simulate_trades, compute_metrics, get_dst_transitions
)

CSV_PATH = r"C:\Users\quinson\Desktop\Claude\Historique données bourse\historique_usa30idxusd_1min.csv"

print("\n--- CHARGEMENT PYTHON ---\n")
df = pd.read_csv(CSV_PATH, sep=';', decimal=',', parse_dates=['Date'])
print(f"  {len(df):,} bougies chargees")

# Filtrer sur la meme periode que PRT
mask_period = (df['Date'] >= '2025-08-15') & (df['Date'] <= '2026-03-02 23:59:59')
# On garde tout le DF pour le lookback mais on note les indices
period_start_idx = df[mask_period].index[0]
period_end_idx = df[mask_period].index[-1]

market_mask = build_market_hours_mask_fast(df)
closes = df['Close'].values
crossings = detect_crossings_vectorized(closes, market_mask.values, [1000])
signals = apply_2h_filter(crossings, 120)  # lookback = 2h

# Filtrer les signaux dans la periode
signals_period = [(i, l, d, s) for i, l, d, s in signals if period_start_idx <= i <= period_end_idx]

# Simuler avec TP=0.3% SL=0.5%
trades_py = simulate_trades(df, signals_period, 0.3, 0.5)
metrics_py = compute_metrics(trades_py)

print("\n--- RESULTATS PYTHON (meme periode, TP=0.3% SL=0.5% LB=2h) ---\n")
print(f"  Trades        : {metrics_py['n_trades']}")
print(f"  Gagnants      : {metrics_py['n_wins']} ({metrics_py['win_rate']:.1f}%)")
print(f"  Perdants      : {metrics_py['n_losses']}")
print(f"  Timeout       : {metrics_py['n_timeout']}")
print(f"  PnL total     : {metrics_py['pnl_total']:+,.1f} pts")
print(f"  Gain moyen    : {metrics_py['avg_win']:+,.1f} pts")
print(f"  Perte moyenne : {metrics_py['avg_loss']:+,.1f} pts")
print(f"  Profit Factor : {metrics_py['profit_factor']:.2f}")
print(f"  Max Drawdown  : {metrics_py['max_dd']:,.1f} pts")

buys_py = [t for t in trades_py if t['direction'] == 'BUY']
sells_py = [t for t in trades_py if t['direction'] == 'SELL']
buy_pnl = sum(t['pnl_points'] for t in buys_py)
sell_pnl = sum(t['pnl_points'] for t in sells_py)
print(f"  BUY           : {len(buys_py)} trades, PnL {buy_pnl:+,.1f} pts")
print(f"  SELL          : {len(sells_py)} trades, PnL {sell_pnl:+,.1f} pts")

# =====================================================
# 3. COMPARAISON TRADE PAR TRADE
# =====================================================

print("\n--- COMPARAISON COTE A COTE ---\n")
print(f"{'Metrique':<20} {'PRT':>12} {'Python':>12} {'Ecart':>12}")
print("-" * 58)
print(f"{'Trades':<20} {n_prt:>12} {metrics_py['n_trades']:>12} {n_prt - metrics_py['n_trades']:>+12}")
print(f"{'Win rate':<20} {len(wins_prt)/n_prt*100:>11.1f}% {metrics_py['win_rate']:>11.1f}% {len(wins_prt)/n_prt*100 - metrics_py['win_rate']:>+11.1f}%")
print(f"{'PnL total (pts)':<20} {pnl_prt:>+12,.1f} {metrics_py['pnl_total']:>+12,.1f} {pnl_prt - metrics_py['pnl_total']:>+12,.1f}")
print(f"{'Profit Factor':<20} {pf_prt:>12.2f} {metrics_py['profit_factor']:>12.2f} {pf_prt - metrics_py['profit_factor']:>+12.2f}")
print(f"{'Max Drawdown':<20} {maxdd_prt:>12,.1f} {metrics_py['max_dd']:>12,.1f} {maxdd_prt - metrics_py['max_dd']:>+12,.1f}")
print(f"{'BUY trades':<20} {len(longs_prt):>12} {len(buys_py):>12} {len(longs_prt) - len(buys_py):>+12}")
print(f"{'SELL trades':<20} {len(shorts_prt):>12} {len(sells_py):>12} {len(shorts_prt) - len(sells_py):>+12}")

# =====================================================
# 4. DETAIL DES TRADES PYTHON (pour comparaison manuelle)
# =====================================================

print(f"\n--- TRADES PYTHON (chronologique) ---\n")
print(f"{'Date entree':>20}  {'Dir':>5}  {'Niveau':>7}  {'Entry':>10}  {'Exit':>10}  {'Result':>7}  {'PnL':>8}")
print("-" * 78)
for t in trades_py:
    print(f"{str(t['entry_date']):>20}  {t['direction']:>5}  {t['level']:>7}  {t['entry_price']:>10.1f}  {t['exit_price']:>10.1f}  {t['result']:>7}  {t['pnl_points']:>+8.1f}")
