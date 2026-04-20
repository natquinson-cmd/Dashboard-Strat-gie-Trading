"""
Backtest: Rebond sur Chiffres Ronds - Dow Jones (US30)
======================================================
Strategie mean reversion: quand le prix franchit un chiffre rond (500/1000 pts),
on trade le retour vers ce niveau.

- Franchissement haussier → SELL
- Franchissement baissier → BUY
- Filtre: pas de franchissement du meme niveau dans les 2h precedentes
- Heures US uniquement (15h30-22h00 Paris)
- TP/SL en % du prix (s'adapte a la valeur de l'indice)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import sys

# ============================================================================
# CONFIGURATION
# ============================================================================

CSV_PATH = r"C:\Users\quinson\Desktop\Claude\Historique données bourse\historique_usa30idxusd_1min.csv"
ROUND_LEVELS = [1000]       # Niveaux 1000 uniquement
LOOKBACK_MINUTES = 120      # Valeur par defaut (sera optimisee)

# Grille d'optimisation TP/SL (en % du prix)
TP_GRID = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]
SL_GRID = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]

# Grille d'optimisation du lookback (en minutes)
LOOKBACK_GRID = [120, 240, 480, 720, 1440]  # 2h, 4h, 8h, 12h, 24h

# Timeout: fermeture forcee si ni TP ni SL touche apres N minutes
MAX_TRADE_DURATION = 390  # ~6.5h (une session complete)


# ============================================================================
# DST: Heures de marche US en UTC
# ============================================================================

def get_dst_transitions(year):
    """Retourne les dates de changement d'heure en Europe (CET/CEST)."""
    # Dernier dimanche de mars → passage a CEST (UTC+2)
    march_last = datetime(year, 3, 31)
    while march_last.weekday() != 6:  # 6 = dimanche
        march_last -= timedelta(days=1)
    to_summer = march_last.replace(hour=1, minute=0, second=0)  # 1h UTC

    # Dernier dimanche d'octobre → retour a CET (UTC+1)
    oct_last = datetime(year, 10, 31)
    while oct_last.weekday() != 6:
        oct_last -= timedelta(days=1)
    to_winter = oct_last.replace(hour=1, minute=0, second=0)  # 1h UTC

    return to_summer, to_winter


def build_market_hours_mask(timestamps):
    """
    Cree un masque boolen pour les heures de marche US.
    15h30-22h00 heure de Paris → en UTC:
      - Hiver (CET, UTC+1): 14:30 - 21:00 UTC
      - Ete (CEST, UTC+2): 13:30 - 20:00 UTC
    """
    mask = np.zeros(len(timestamps), dtype=bool)

    # Pre-calculer les transitions DST pour toutes les annees
    years = sorted(set(ts.year for ts in timestamps))
    transitions = {}
    for y in years:
        transitions[y] = get_dst_transitions(y)

    for i, ts in enumerate(timestamps):
        year = ts.year
        to_summer, to_winter = transitions[year]

        if to_summer <= ts < to_winter:
            # CEST (ete): 13:30 - 20:00 UTC
            start_h, start_m = 13, 30
            end_h, end_m = 20, 0
        else:
            # CET (hiver): 14:30 - 21:00 UTC
            start_h, start_m = 14, 30
            end_h, end_m = 21, 0

        t = ts.hour * 60 + ts.minute
        if start_h * 60 + start_m <= t < end_h * 60 + end_m:
            # Exclure weekends (samedi=5, dimanche=6)
            if ts.weekday() < 5:
                mask[i] = True

    return mask


def build_market_hours_mask_fast(df):
    """Version vectorisee rapide du filtre horaire."""
    ts = df['Date']
    hour = ts.dt.hour
    minute = ts.dt.minute
    weekday = ts.dt.weekday
    t = hour * 60 + minute  # minutes depuis minuit

    # Determiner si chaque timestamp est en heure d'ete (CEST)
    year = ts.dt.year
    is_summer = pd.Series(False, index=df.index)

    for y in year.unique():
        to_summer, to_winter = get_dst_transitions(y)
        to_summer = pd.Timestamp(to_summer)
        to_winter = pd.Timestamp(to_winter)
        year_mask = year == y
        is_summer = is_summer | (year_mask & (ts >= to_summer) & (ts < to_winter))

    # Heures de marche en UTC
    # Ete (CEST): 13:30 - 20:00 UTC
    summer_mask = is_summer & (t >= 13 * 60 + 30) & (t < 20 * 60)
    # Hiver (CET): 14:30 - 21:00 UTC
    winter_mask = ~is_summer & (t >= 14 * 60 + 30) & (t < 21 * 60)

    # Exclure weekends
    not_weekend = weekday < 5

    return (summer_mask | winter_mask) & not_weekend


# ============================================================================
# DETECTION DES FRANCHISSEMENTS
# ============================================================================

def find_nearby_round_levels(price, levels=[500, 1000]):
    """Retourne les chiffres ronds proches du prix actuel."""
    result = set()
    for step in levels:
        lower = (price // step) * step
        upper = lower + step
        result.add(lower)
        result.add(upper)
    return result


def detect_crossings(closes, market_mask, levels=[500, 1000]):
    """
    Detecte les franchissements de chiffres ronds.
    Retourne une liste de (index, round_level, direction)
    direction: 'up' = haussier, 'down' = baissier
    """
    crossings = []
    n = len(closes)

    # Pour chaque paire de bougies consecutives pendant les heures de marche
    for i in range(1, n):
        if not market_mask[i]:
            continue

        prev_close = closes[i - 1]
        curr_close = closes[i]

        if prev_close == curr_close:
            continue

        # Determiner les niveaux ronds entre prev et curr
        price_min = min(prev_close, curr_close)
        price_max = max(prev_close, curr_close)

        for step in levels:
            # Premier multiple de step >= price_min
            first_level = int(np.ceil(price_min / step)) * step
            level = first_level
            while level <= price_max:
                if level == 0:
                    level += step
                    continue
                # Verifier le franchissement
                if prev_close < level <= curr_close:
                    crossings.append((i, level, 'up', step))
                elif prev_close > level >= curr_close:
                    crossings.append((i, level, 'down', step))
                level += step

    return crossings


def detect_crossings_vectorized(closes, market_mask, levels=[500, 1000]):
    """Version optimisee de la detection de franchissements."""
    crossings = []
    n = len(closes)

    prev = closes[:-1]
    curr = closes[1:]
    # Indices ou le marche est ouvert et le prix a bouge
    valid = market_mask[1:] & (prev != curr)
    valid_indices = np.where(valid)[0]

    for step in levels:
        for idx in valid_indices:
            p = prev[idx]
            c = curr[idx]
            i = idx + 1  # index reel dans le DataFrame

            lo, hi = (p, c) if p < c else (c, p)
            first_level = int(np.ceil(lo / step)) * step

            level = first_level
            while level <= hi:
                if level == 0:
                    level += step
                    continue
                if p < level <= c:
                    crossings.append((i, level, 'up', step))
                elif p > level >= c:
                    crossings.append((i, level, 'down', step))
                level += step

    # Trier par index chronologique
    crossings.sort(key=lambda x: x[0])
    return crossings


# ============================================================================
# FILTRE 2 HEURES
# ============================================================================

def apply_2h_filter(crossings, lookback=LOOKBACK_MINUTES):
    """
    Filtre les franchissements: on garde un signal seulement si le meme
    chiffre rond n'a pas ete franchi dans les `lookback` dernieres minutes.
    """
    # D'abord, deduplicer les crossings au meme index+level (500 et 1000 detectent le meme)
    seen = set()
    unique_crossings = []
    for idx, level, direction, step in crossings:
        key = (idx, level)
        if key not in seen:
            seen.add(key)
            # Assigner le level_type selon que le niveau est multiple de 1000 ou seulement 500
            level_type = 1000 if level % 1000 == 0 else 500
            unique_crossings.append((idx, level, direction, level_type))

    # Dictionnaire: level → dernier index de franchissement
    last_crossing = {}
    filtered = []

    for idx, level, direction, level_type in unique_crossings:
        if level in last_crossing:
            prev_idx = last_crossing[level]
            # Verifier si la difference d'index < lookback minutes
            # (chaque index = 1 minute)
            if idx - prev_idx < lookback:
                # Trop recent, on saute mais on met a jour le dernier franchissement
                last_crossing[level] = idx
                continue

        last_crossing[level] = idx
        filtered.append((idx, level, direction, level_type))

    return filtered


# ============================================================================
# SIMULATION DES TRADES
# ============================================================================

def simulate_trades(df, signals, tp_pct, sl_pct, max_duration=MAX_TRADE_DURATION):
    """
    Simule les trades a partir des signaux.
    Entree au close de la bougie de signal.
    TP/SL en % du prix d'entree.
    """
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    n = len(df)

    trades = []

    for sig_idx, level, direction, step in signals:
        entry_price = closes[sig_idx]
        tp_distance = entry_price * tp_pct / 100
        sl_distance = entry_price * sl_pct / 100

        if direction == 'up':
            # SELL: on gagne si le prix baisse
            tp_price = entry_price - tp_distance
            sl_price = entry_price + sl_distance
        else:
            # BUY: on gagne si le prix monte
            tp_price = entry_price + tp_distance
            sl_price = entry_price - sl_distance

        # Simuler bougie par bougie
        result = 'timeout'
        exit_price = entry_price
        exit_idx = min(sig_idx + max_duration, n - 1)

        for j in range(sig_idx + 1, min(sig_idx + max_duration + 1, n)):
            h = highs[j]
            l = lows[j]

            if direction == 'up':  # SELL
                # SL touche si le prix monte au-dessus du SL
                sl_hit = h >= sl_price
                # TP touche si le prix descend en dessous du TP
                tp_hit = l <= tp_price
            else:  # BUY
                # SL touche si le prix descend en dessous du SL
                sl_hit = l <= sl_price
                # TP touche si le prix monte au-dessus du TP
                tp_hit = h >= tp_price

            if sl_hit and tp_hit:
                # Hypothese conservatrice: SL touche en premier
                result = 'sl'
                exit_price = sl_price
                exit_idx = j
                break
            elif sl_hit:
                result = 'sl'
                exit_price = sl_price
                exit_idx = j
                break
            elif tp_hit:
                result = 'tp'
                exit_price = tp_price
                exit_idx = j
                break

        if result == 'timeout':
            exit_price = closes[exit_idx]

        # Calculer le PnL en points
        if direction == 'up':  # SELL
            pnl = entry_price - exit_price
        else:  # BUY
            pnl = exit_price - entry_price

        trades.append({
            'entry_idx': sig_idx,
            'exit_idx': exit_idx,
            'entry_date': df['Date'].iloc[sig_idx],
            'exit_date': df['Date'].iloc[exit_idx],
            'direction': 'SELL' if direction == 'up' else 'BUY',
            'level': level,
            'level_type': step,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'result': result,
            'pnl_points': pnl,
            'pnl_pct': pnl / entry_price * 100,
            'duration_min': exit_idx - sig_idx,
        })

    return trades


# ============================================================================
# METRIQUES
# ============================================================================

def compute_metrics(trades):
    """Calcule les metriques de performance."""
    if not trades:
        return {
            'n_trades': 0, 'win_rate': 0, 'pnl_total': 0,
            'avg_win': 0, 'avg_loss': 0, 'profit_factor': 0,
            'max_dd': 0
        }

    pnls = [t['pnl_points'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    cumulative = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumulative)
    drawdown = peak - cumulative
    max_dd = np.max(drawdown) if len(drawdown) > 0 else 0

    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 0

    return {
        'n_trades': len(trades),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'pnl_total': sum(pnls),
        'avg_win': np.mean(wins) if wins else 0,
        'avg_loss': np.mean(losses) if losses else 0,
        'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
        'max_dd': max_dd,
        'n_wins': len(wins),
        'n_losses': len(losses),
        'n_timeout': sum(1 for t in trades if t['result'] == 'timeout'),
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    t0 = time.time()
    print("=" * 70)
    print("  BACKTEST: Rebond sur Chiffres Ronds - Dow Jones (US30)")
    print("  Strategie Mean Reversion | Niveaux 1000 pts uniquement")
    print("  Optimisation 3D : TP x SL x Lookback")
    print("=" * 70)
    print()

    # --- Chargement des donnees ---
    print("[1/4] Chargement des donnees...", end=" ", flush=True)
    df = pd.read_csv(
        CSV_PATH,
        sep=';',
        decimal=',',
        parse_dates=['Date'],
    )
    print(f"OK ({len(df):,} bougies, {df['Date'].iloc[0].date()} -> {df['Date'].iloc[-1].date()})")

    # --- Filtrage heures de marche ---
    print("[2/4] Filtrage heures de marche US (15h30-22h00 Paris)...", end=" ", flush=True)
    market_mask = build_market_hours_mask_fast(df)
    n_market = market_mask.sum()
    print(f"OK ({n_market:,} bougies en marche, {n_market / len(df) * 100:.1f}%)")

    # --- Detection des franchissements ---
    print("[3/4] Detection des franchissements (niveaux 1000 pts)...", end=" ", flush=True)
    closes = df['Close'].values
    crossings = detect_crossings_vectorized(closes, market_mask.values, ROUND_LEVELS)
    print(f"OK ({len(crossings):,} franchissements bruts)")

    # --- Optimisation 3D: TP x SL x Lookback ---
    total_combos = len(TP_GRID) * len(SL_GRID) * len(LOOKBACK_GRID)
    print(f"[4/4] Optimisation 3D ({len(TP_GRID)} TP x {len(SL_GRID)} SL x {len(LOOKBACK_GRID)} Lookback = {total_combos} combinaisons)...")
    print()

    all_results = []
    best_pnl = -float('inf')
    best_combo = None
    best_trades = None
    combo_num = 0

    # Pour chaque lookback, on filtre une fois les signaux puis on teste tous les TP/SL
    for lookback in LOOKBACK_GRID:
        signals = apply_2h_filter(crossings, lookback)
        lookback_label = f"{lookback // 60}h" if lookback >= 60 else f"{lookback}m"

        for tp_pct in TP_GRID:
            for sl_pct in SL_GRID:
                combo_num += 1
                sys.stdout.write(f"\r     [{combo_num}/{total_combos}] Lookback={lookback_label} TP={tp_pct}% SL={sl_pct}%...")
                sys.stdout.flush()

                trades = simulate_trades(df, signals, tp_pct, sl_pct)
                metrics = compute_metrics(trades)

                all_results.append({
                    'lookback_min': lookback,
                    'lookback_label': lookback_label,
                    'tp_pct': tp_pct,
                    'sl_pct': sl_pct,
                    **metrics
                })

                if metrics['pnl_total'] > best_pnl:
                    best_pnl = metrics['pnl_total']
                    best_combo = (tp_pct, sl_pct, lookback)
                    best_trades = trades
                    best_signals = signals

    print(f"\r     {total_combos} combinaisons testees.{' ' * 50}")
    elapsed = time.time() - t0
    print(f"\n     Temps d'execution: {elapsed:.1f}s")

    results_df = pd.DataFrame(all_results)

    # ========================================================================
    # RESULTATS
    # ========================================================================

    print()
    print("=" * 70)
    print("  RESULTATS DE L'OPTIMISATION")
    print("=" * 70)

    # --- Impact du Lookback ---
    print("\n--- Impact du Lookback (meilleur TP/SL pour chaque lookback) ---\n")
    print(f"{'Lookback':>10}  {'Signaux':>8}  {'Best TP':>8}  {'Best SL':>8}  {'Trades':>7}  {'Win%':>6}  {'PnL (pts)':>12}  {'PF':>6}  {'MaxDD':>8}")
    print("-" * 85)

    for lookback in LOOKBACK_GRID:
        lb_df = results_df[results_df['lookback_min'] == lookback]
        best_row = lb_df.loc[lb_df['pnl_total'].idxmax()]
        lb_label = f"{lookback // 60}h" if lookback >= 60 else f"{lookback}m"
        # Nombre de signaux pour ce lookback
        lb_signals = apply_2h_filter(crossings, lookback)
        pf_str = f"{best_row['profit_factor']:.2f}" if best_row['profit_factor'] != float('inf') else "INF"
        print(f"{lb_label:>10}  {len(lb_signals):>8}  {best_row['tp_pct']:>7.2f}%  {best_row['sl_pct']:>7.2f}%  {best_row['n_trades']:>7.0f}  {best_row['win_rate']:>5.1f}%  {best_row['pnl_total']:>+12,.0f}  {pf_str:>6}  {best_row['max_dd']:>8,.0f}")

    # --- Heatmaps pour le meilleur lookback ---
    best_lb = best_combo[2]
    best_lb_label = f"{best_lb // 60}h" if best_lb >= 60 else f"{best_lb}m"
    lb_results = results_df[results_df['lookback_min'] == best_lb]

    print(f"\n--- Heatmap PnL (points) pour Lookback={best_lb_label} : TP (col) x SL (lig) ---\n")
    pivot = lb_results.pivot_table(values='pnl_total', index='sl_pct', columns='tp_pct')

    header = f"{'SL \\ TP':>10}"
    for tp in TP_GRID:
        header += f"  {tp:>8.2f}%"
    print(header)
    print("-" * len(header))

    for sl in SL_GRID:
        row = f"{sl:>9.2f}%"
        for tp in TP_GRID:
            val = pivot.loc[sl, tp]
            row += f"  {val:>+8.0f}"
        print(row)

    print(f"\n--- Heatmap Win Rate (%) pour Lookback={best_lb_label} ---\n")
    pivot_wr = lb_results.pivot_table(values='win_rate', index='sl_pct', columns='tp_pct')

    header = f"{'SL \\ TP':>10}"
    for tp in TP_GRID:
        header += f"  {tp:>8.2f}%"
    print(header)
    print("-" * len(header))

    for sl in SL_GRID:
        row = f"{sl:>9.2f}%"
        for tp in TP_GRID:
            val = pivot_wr.loc[sl, tp]
            row += f"  {val:>7.1f}%"
        print(row)

    print(f"\n--- Heatmap Profit Factor pour Lookback={best_lb_label} ---\n")
    pivot_pf = lb_results.pivot_table(values='profit_factor', index='sl_pct', columns='tp_pct')

    header = f"{'SL \\ TP':>10}"
    for tp in TP_GRID:
        header += f"  {tp:>8.2f}%"
    print(header)
    print("-" * len(header))

    for sl in SL_GRID:
        row = f"{sl:>9.2f}%"
        for tp in TP_GRID:
            val = pivot_pf.loc[sl, tp]
            if val == float('inf'):
                row += f"  {'INF':>8}"
            else:
                row += f"  {val:>8.2f}"
        print(row)

    # --- Meilleure combinaison ---
    print()
    print("=" * 70)
    print(f"  MEILLEURE COMBINAISON : TP={best_combo[0]}% / SL={best_combo[1]}% / Lookback={best_lb_label}")
    print("=" * 70)

    best_metrics = compute_metrics(best_trades)
    print(f"""
  Trades totaux     : {best_metrics['n_trades']}
  Gagnants          : {best_metrics['n_wins']} ({best_metrics['win_rate']:.1f}%)
  Perdants          : {best_metrics['n_losses']}
  Timeout           : {best_metrics['n_timeout']}

  PnL total         : {best_metrics['pnl_total']:+,.0f} points
  Gain moyen        : {best_metrics['avg_win']:+,.1f} points
  Perte moyenne     : {best_metrics['avg_loss']:+,.1f} points
  Profit Factor     : {best_metrics['profit_factor']:.2f}
  Max Drawdown      : {best_metrics['max_dd']:,.0f} points
""")

    # --- Detail par annee ---
    print("--- Performance par annee ---\n")
    print(f"{'Annee':>6}  {'Trades':>7}  {'Win%':>6}  {'PnL (pts)':>12}  {'PF':>6}  {'MaxDD':>8}")
    print("-" * 55)

    for year in sorted(set(t['entry_date'].year for t in best_trades)):
        year_trades = [t for t in best_trades if t['entry_date'].year == year]
        ym = compute_metrics(year_trades)
        pf_str = f"{ym['profit_factor']:.2f}" if ym['profit_factor'] != float('inf') else "INF"
        print(f"{year:>6}  {ym['n_trades']:>7}  {ym['win_rate']:>5.1f}%  {ym['pnl_total']:>+12,.0f}  {pf_str:>6}  {ym['max_dd']:>8,.0f}")

    # --- Detail par direction ---
    print("\n--- Performance par direction ---\n")
    print(f"{'Dir':>6}  {'Trades':>7}  {'Win%':>6}  {'PnL (pts)':>12}  {'PF':>6}")
    print("-" * 45)

    for direction in ['BUY', 'SELL']:
        dir_trades = [t for t in best_trades if t['direction'] == direction]
        dm = compute_metrics(dir_trades)
        pf_str = f"{dm['profit_factor']:.2f}" if dm['profit_factor'] != float('inf') else "INF"
        print(f"{direction:>6}  {dm['n_trades']:>7}  {dm['win_rate']:>5.1f}%  {dm['pnl_total']:>+12,.0f}  {pf_str:>6}")

    # --- Top 10 meilleures combinaisons globales ---
    print("\n--- Top 10 meilleures combinaisons (toutes dimensions) ---\n")
    top10 = results_df.nlargest(10, 'pnl_total')
    print(f"{'#':>3}  {'Lookback':>8}  {'TP%':>6}  {'SL%':>6}  {'Trades':>7}  {'Win%':>6}  {'PnL (pts)':>12}  {'PF':>6}  {'MaxDD':>8}")
    print("-" * 78)
    for rank, (_, row) in enumerate(top10.iterrows(), 1):
        pf_str = f"{row['profit_factor']:.2f}" if row['profit_factor'] != float('inf') else "INF"
        print(f"{rank:>3}  {row['lookback_label']:>8}  {row['tp_pct']:>5.2f}%  {row['sl_pct']:>5.2f}%  {row['n_trades']:>7.0f}  {row['win_rate']:>5.1f}%  {row['pnl_total']:>+12,.0f}  {pf_str:>6}  {row['max_dd']:>8,.0f}")

    # --- Echantillon de trades ---
    print(f"\n--- 10 derniers trades (meilleure combinaison) ---\n")
    print(f"{'Date entree':>20}  {'Dir':>5}  {'Niveau':>7}  {'Entry':>10}  {'Exit':>10}  {'Result':>7}  {'PnL':>8}  {'Duree':>6}")
    print("-" * 85)
    for t in best_trades[-10:]:
        print(f"{str(t['entry_date']):>20}  {t['direction']:>5}  {t['level']:>7}  {t['entry_price']:>10.1f}  {t['exit_price']:>10.1f}  {t['result']:>7}  {t['pnl_points']:>+8.1f}  {t['duration_min']:>5}m")

    print()
    print("=" * 70)
    print("  Backtest termine.")
    print("=" * 70)


if __name__ == '__main__':
    main()
