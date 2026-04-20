"""
Backtest NAS 15 OPR R2 réinv V1.1
Réplication fidèle de la stratégie PRT sur données 1min resamplees en 15min
"""
import pandas as pd
import numpy as np
from datetime import time, timedelta
import warnings, sys, io
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# 1. CHARGEMENT ET RESAMPLING DES DONNÉES
# ============================================================
print("=" * 70)
print("CHARGEMENT DES DONNÉES NASDAQ 1MIN...")
print("=" * 70)

DATA_PATH = r"C:\Users\quinson\Desktop\Claude\Historique données bourse\historique_usatechidxusd_1min.csv"

df_raw = pd.read_csv(
    DATA_PATH,
    sep=';',
    decimal=',',
    parse_dates=['Date'],
    index_col='Date'
)

print(f"Données brutes : {len(df_raw):,} barres 1min")
print(f"Période : {df_raw.index[0]} → {df_raw.index[-1]}")

# Resample en 15 minutes
df = df_raw.resample('15min').agg({
    'Open': 'first',
    'High': 'max',
    'Low': 'min',
    'Close': 'last'
}).dropna()

print(f"Données 15min : {len(df):,} barres")

# ============================================================
# 2. CALCUL ATR 14 sur barres 15min
# ============================================================
df['PrevClose'] = df['Close'].shift(1)
df['TR'] = np.maximum(
    df['High'] - df['Low'],
    np.maximum(
        abs(df['High'] - df['PrevClose']),
        abs(df['Low'] - df['PrevClose'])
    )
)
df['ATR14'] = df['TR'].ewm(span=14, adjust=False).mean()

# ============================================================
# 3. PARAMÈTRES DE LA STRATÉGIE
# ============================================================
class StrategyParams:
    CoeffBE = 1.2
    CoeffStop = 3.2
    TargetMult = 2.2
    CoefLockProfit = 0.3
    CapInit = 5300
    Risque = 2.2
    Reinvestir = 1  # ON pour tester le réinvestissement
    PipValue = 1.0  # US Tech 100 Cash (1€)

params = StrategyParams()

# ============================================================
# 4. MOTEUR DE BACKTEST
# ============================================================
def run_backtest(df, p, label="Baseline"):
    """
    Exécute le backtest complet de la stratégie OPR.
    Simule barre par barre en 15min.
    """
    trades = []
    equity_curve = []

    # État du système
    strategy_profit = 0.0
    position = 0       # 1=long, -1=short, 0=flat
    entry_price = 0.0
    stop_dyn = 0
    target_dyn = 0
    niveau_stop = 0.0
    static_be_trigger = 0.0
    static_lock_trigger = 0.0
    static_lock_profit = 0.0
    pos_size = 0.0

    # Variables journalières
    opr_high = None
    opr_low = None
    today_trade = 0
    current_date = None

    # Pour tracking du trade en cours
    trade_entry_time = None
    trade_type = ""

    bars = df.reset_index()

    for i in range(14, len(bars)):  # skip first 14 for ATR warmup
        row = bars.iloc[i]
        dt = row['Date']
        o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
        atr = row['ATR14']
        t = dt.time()
        d = dt.date()

        # --- Nouveau jour ---
        if d != current_date:
            current_date = d
            today_trade = 0
            opr_high = None
            opr_low = None

        # --- OPR à 15h30 ---
        if t == time(15, 30):
            opr_high = h
            opr_low = l

        # --- Calcul dynamique Stop/Target ---
        stop_dyn_calc = round(max(85, min(185, atr * p.CoeffStop)))
        target_dyn_calc = round(stop_dyn_calc * p.TargetMult)

        # --- Calcul taille de position ---
        if p.Reinvestir == 1:
            cap_actuel = p.CapInit + strategy_profit
        else:
            cap_actuel = p.CapInit

        if stop_dyn_calc > 0:
            raw_size = (cap_actuel * (p.Risque / 100)) / (stop_dyn_calc * p.PipValue)
            pos_size_calc = round(max(0.01, raw_size), 2)
        else:
            pos_size_calc = 0.5

        # --- GESTION POSITION EN COURS ---
        if position != 0:
            trade_pnl_points = 0
            closed = False
            close_reason = ""

            # Vérifier stop loss (pLOSS)
            if position == 1:  # Long
                if l <= entry_price - stop_dyn:
                    trade_pnl_points = -stop_dyn
                    closed = True
                    close_reason = "Stop Loss"
                elif h >= entry_price + target_dyn:
                    trade_pnl_points = target_dyn
                    closed = True
                    close_reason = "Target"
            elif position == -1:  # Short
                if h >= entry_price + stop_dyn:
                    trade_pnl_points = -stop_dyn
                    closed = True
                    close_reason = "Stop Loss"
                elif l <= entry_price - target_dyn:
                    trade_pnl_points = target_dyn
                    closed = True
                    close_reason = "Target"

            if not closed:
                # PALIER 1 : Breakeven
                if position == 1 and (c - entry_price) > static_be_trigger:
                    new_stop = entry_price + 5
                    niveau_stop = max(niveau_stop, new_stop)
                elif position == -1 and (entry_price - c) > static_be_trigger:
                    new_stop = entry_price - 5
                    if niveau_stop == 0:
                        niveau_stop = new_stop
                    else:
                        niveau_stop = min(niveau_stop, new_stop)

                # PALIER 2 : Lock Profit
                if position == 1 and (c - entry_price) > static_lock_trigger:
                    new_stop = entry_price + static_lock_profit
                    niveau_stop = max(niveau_stop, new_stop)
                elif position == -1 and (entry_price - c) > static_lock_trigger:
                    new_stop = entry_price - static_lock_profit
                    if niveau_stop == 0:
                        niveau_stop = new_stop
                    else:
                        niveau_stop = min(niveau_stop, new_stop)

                # Check stop dynamique (NiveauStop)
                if position == 1 and niveau_stop > 0 and l <= niveau_stop:
                    trade_pnl_points = niveau_stop - entry_price
                    closed = True
                    close_reason = "Trailing Stop"
                elif position == -1 and niveau_stop > 0 and h >= niveau_stop:
                    trade_pnl_points = entry_price - niveau_stop
                    closed = True
                    close_reason = "Trailing Stop"

                # Clôture fin de journée (21h55)
                if not closed and t >= time(21, 55):
                    if position == 1:
                        trade_pnl_points = c - entry_price
                    else:
                        trade_pnl_points = entry_price - c
                    closed = True
                    close_reason = "EOD Close"

            if closed:
                trade_pnl_euros = trade_pnl_points * pos_size * p.PipValue
                strategy_profit += trade_pnl_euros
                trades.append({
                    'entry_time': trade_entry_time,
                    'exit_time': dt,
                    'type': trade_type,
                    'entry_price': entry_price,
                    'exit_reason': close_reason,
                    'pnl_points': round(trade_pnl_points, 2),
                    'pos_size': pos_size,
                    'pnl_euros': round(trade_pnl_euros, 2),
                    'cumul_profit': round(strategy_profit, 2),
                    'stop_dyn': stop_dyn,
                    'target_dyn': target_dyn,
                    'cap_actuel': round(cap_actuel, 2)
                })
                position = 0
                today_trade = 1  # Marquer qu'on a tradé aujourd'hui

        # --- ENTRÉE ---
        if position == 0 and today_trade == 0 and opr_high is not None:
            if t > time(15, 30) and t <= time(17, 30):
                entered = False
                if c > opr_high:
                    position = 1
                    entry_price = c  # AT MARKET = close de la bougie
                    trade_type = "Long"
                    entered = True
                elif c < opr_low:
                    position = -1
                    entry_price = c
                    trade_type = "Short"
                    entered = True

                if entered:
                    stop_dyn = stop_dyn_calc
                    target_dyn = target_dyn_calc
                    pos_size = pos_size_calc
                    trade_entry_time = dt
                    today_trade = 1

                    # Fixer les seuils statiques
                    static_be_trigger = atr * p.CoeffBE
                    static_lock_trigger = target_dyn * 0.6
                    static_lock_profit = target_dyn * p.CoefLockProfit

                    if position == 1:
                        niveau_stop = entry_price - stop_dyn
                    else:
                        niveau_stop = entry_price + stop_dyn
                    # Reset niveau_stop pour la logique trailing
                    niveau_stop = 0  # Le trailing commence à 0, le pLOSS gère le stop initial

        # Equity curve
        equity_curve.append({
            'date': dt,
            'equity': p.CapInit + strategy_profit
        })

    return trades, equity_curve

# ============================================================
# 5. EXÉCUTION BASELINE
# ============================================================
print("\n" + "=" * 70)
print("BACKTEST BASELINE - Paramètres originaux")
print("=" * 70)

trades, equity = run_backtest(df, params, "Baseline")
trades_df = pd.DataFrame(trades)

if len(trades_df) == 0:
    print("ERREUR : Aucun trade généré !")
else:
    # Statistiques globales
    total_trades = len(trades_df)
    winners = trades_df[trades_df['pnl_euros'] > 0]
    losers = trades_df[trades_df['pnl_euros'] < 0]
    breakeven = trades_df[trades_df['pnl_euros'] == 0]

    win_rate = len(winners) / total_trades * 100
    avg_win = winners['pnl_euros'].mean() if len(winners) > 0 else 0
    avg_loss = losers['pnl_euros'].mean() if len(losers) > 0 else 0
    profit_factor = abs(winners['pnl_euros'].sum() / losers['pnl_euros'].sum()) if len(losers) > 0 and losers['pnl_euros'].sum() != 0 else float('inf')

    total_profit = trades_df['pnl_euros'].sum()
    max_drawdown_euros = 0
    peak = 0
    for pnl in trades_df['pnl_euros'].cumsum():
        peak = max(peak, pnl)
        dd = peak - pnl
        max_drawdown_euros = max(max_drawdown_euros, dd)

    # Ratio gain/perte moyen
    ratio_rr = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Espérance mathématique par trade
    esperance = trades_df['pnl_euros'].mean()

    # Analyse par type de sortie
    exit_stats = trades_df.groupby('exit_reason').agg(
        count=('pnl_euros', 'count'),
        total=('pnl_euros', 'sum'),
        avg=('pnl_euros', 'mean'),
        avg_points=('pnl_points', 'mean')
    ).round(2)

    # Analyse Long vs Short
    long_trades = trades_df[trades_df['type'] == 'Long']
    short_trades = trades_df[trades_df['type'] == 'Short']

    # Analyse par année
    trades_df['year'] = pd.to_datetime(trades_df['entry_time']).dt.year
    yearly = trades_df.groupby('year').agg(
        nb_trades=('pnl_euros', 'count'),
        profit=('pnl_euros', 'sum'),
        win_rate=('pnl_euros', lambda x: (x > 0).mean() * 100),
        avg_trade=('pnl_euros', 'mean'),
        max_win=('pnl_euros', 'max'),
        max_loss=('pnl_euros', 'min')
    ).round(2)

    # Séries de pertes consécutives
    is_loss = (trades_df['pnl_euros'] < 0).astype(int)
    loss_streaks = []
    current_streak = 0
    for val in is_loss:
        if val == 1:
            current_streak += 1
        else:
            if current_streak > 0:
                loss_streaks.append(current_streak)
            current_streak = 0
    if current_streak > 0:
        loss_streaks.append(current_streak)
    max_loss_streak = max(loss_streaks) if loss_streaks else 0

    # Séries de gains consécutifs
    is_win = (trades_df['pnl_euros'] > 0).astype(int)
    win_streaks = []
    current_streak = 0
    for val in is_win:
        if val == 1:
            current_streak += 1
        else:
            if current_streak > 0:
                win_streaks.append(current_streak)
            current_streak = 0
    if current_streak > 0:
        win_streaks.append(current_streak)
    max_win_streak = max(win_streaks) if win_streaks else 0

    # Distribution des PnL en points
    pnl_points = trades_df['pnl_points']

    # Analyse de la taille de position dans le temps
    pos_sizes = trades_df[['entry_time', 'pos_size', 'cap_actuel']].copy()
    pos_sizes['entry_time'] = pd.to_datetime(pos_sizes['entry_time'])
    first_size = pos_sizes.iloc[0]['pos_size']
    last_size = pos_sizes.iloc[-1]['pos_size']

    print(f"\n{'─' * 50}")
    print(f"  RÉSULTATS GLOBAUX")
    print(f"{'─' * 50}")
    print(f"  Période         : {trades_df.iloc[0]['entry_time']} → {trades_df.iloc[-1]['entry_time']}")
    print(f"  Nombre de trades: {total_trades}")
    print(f"  Trades gagnants : {len(winners)} ({win_rate:.1f}%)")
    print(f"  Trades perdants : {len(losers)} ({100-win_rate:.1f}%)")
    print(f"  Breakeven       : {len(breakeven)}")
    print(f"{'─' * 50}")
    print(f"  Profit total    : {total_profit:,.2f} €")
    print(f"  Gain moyen      : {avg_win:,.2f} €")
    print(f"  Perte moyenne   : {avg_loss:,.2f} €")
    print(f"  Ratio R:R moyen : {ratio_rr:.2f}")
    print(f"  Profit Factor   : {profit_factor:.2f}")
    print(f"  Espérance/trade : {esperance:,.2f} €")
    print(f"{'─' * 50}")
    print(f"  Max Drawdown    : {max_drawdown_euros:,.2f} €")
    print(f"  Max série pertes: {max_loss_streak}")
    print(f"  Max série gains : {max_win_streak}")
    print(f"{'─' * 50}")
    print(f"  Capital initial : {params.CapInit:,.2f} €")
    print(f"  Capital final   : {params.CapInit + total_profit:,.2f} €")
    print(f"  Rendement total : {(total_profit/params.CapInit)*100:.1f}%")

    print(f"\n{'─' * 50}")
    print(f"  RÉINVESTISSEMENT - ÉVOLUTION TAILLE DE POSITION")
    print(f"{'─' * 50}")
    print(f"  Taille initiale : {first_size}")
    print(f"  Taille finale   : {last_size}")
    print(f"  Progression     : {((last_size/first_size)-1)*100:.1f}%")
    # Échantillons tous les 200 trades
    print(f"  Évolution :")
    step = max(1, len(pos_sizes) // 10)
    for idx in range(0, len(pos_sizes), step):
        row = pos_sizes.iloc[idx]
        print(f"    Trade {idx+1:>5} | {str(row['entry_time'])[:10]} | Size: {row['pos_size']:.2f} | Capital: {row['cap_actuel']:,.0f}€")
    # Dernier
    row = pos_sizes.iloc[-1]
    print(f"    Trade {len(pos_sizes):>5} | {str(row['entry_time'])[:10]} | Size: {row['pos_size']:.2f} | Capital: {row['cap_actuel']:,.0f}€")

    print(f"\n{'─' * 50}")
    print(f"  ANALYSE PAR TYPE DE SORTIE")
    print(f"{'─' * 50}")
    print(exit_stats.to_string())

    print(f"\n{'─' * 50}")
    print(f"  LONG vs SHORT")
    print(f"{'─' * 50}")
    if len(long_trades) > 0:
        long_wr = (long_trades['pnl_euros'] > 0).mean() * 100
        print(f"  Long  : {len(long_trades)} trades | WR: {long_wr:.1f}% | Total: {long_trades['pnl_euros'].sum():,.2f}€ | Moy: {long_trades['pnl_euros'].mean():,.2f}€")
    if len(short_trades) > 0:
        short_wr = (short_trades['pnl_euros'] > 0).mean() * 100
        print(f"  Short : {len(short_trades)} trades | WR: {short_wr:.1f}% | Total: {short_trades['pnl_euros'].sum():,.2f}€ | Moy: {short_trades['pnl_euros'].mean():,.2f}€")

    print(f"\n{'─' * 50}")
    print(f"  ANALYSE PAR ANNÉE")
    print(f"{'─' * 50}")
    print(yearly.to_string())

    print(f"\n{'─' * 50}")
    print(f"  DISTRIBUTION DES RÉSULTATS (en points)")
    print(f"{'─' * 50}")
    print(f"  Min          : {pnl_points.min():.0f}")
    print(f"  P10          : {pnl_points.quantile(0.10):.0f}")
    print(f"  P25          : {pnl_points.quantile(0.25):.0f}")
    print(f"  Médiane      : {pnl_points.median():.0f}")
    print(f"  P75          : {pnl_points.quantile(0.75):.0f}")
    print(f"  P90          : {pnl_points.quantile(0.90):.0f}")
    print(f"  Max          : {pnl_points.max():.0f}")

    # Analyse des stops touchés
    stop_hit = trades_df[trades_df['exit_reason'] == 'Stop Loss']
    if len(stop_hit) > 0:
        print(f"\n{'─' * 50}")
        print(f"  ANALYSE DES STOPS LOSS")
        print(f"{'─' * 50}")
        print(f"  Stop Dyn moyen quand touché : {stop_hit['stop_dyn'].mean():.0f} pts")
        print(f"  Distribution Stop Dyn :")
        print(f"    85 pts  : {(stop_hit['stop_dyn'] == 85).sum()} fois ({(stop_hit['stop_dyn'] == 85).mean()*100:.1f}%)")
        print(f"    86-130  : {((stop_hit['stop_dyn'] > 85) & (stop_hit['stop_dyn'] <= 130)).sum()} fois")
        print(f"    131-184 : {((stop_hit['stop_dyn'] > 130) & (stop_hit['stop_dyn'] < 185)).sum()} fois")
        print(f"    185 pts : {(stop_hit['stop_dyn'] == 185).sum()} fois ({(stop_hit['stop_dyn'] == 185).mean()*100:.1f}%)")

    # Analyse de l'heure d'entrée
    trades_df['entry_hour'] = pd.to_datetime(trades_df['entry_time']).dt.hour
    trades_df['entry_minute'] = pd.to_datetime(trades_df['entry_time']).dt.minute
    trades_df['entry_hm'] = trades_df['entry_hour'].astype(str) + ':' + trades_df['entry_minute'].astype(str).str.zfill(2)

    hour_stats = trades_df.groupby('entry_hm').agg(
        nb=('pnl_euros', 'count'),
        profit=('pnl_euros', 'sum'),
        wr=('pnl_euros', lambda x: (x > 0).mean() * 100),
        avg=('pnl_euros', 'mean')
    ).round(2)

    print(f"\n{'─' * 50}")
    print(f"  ANALYSE PAR HEURE D'ENTRÉE (15min slots)")
    print(f"{'─' * 50}")
    print(hour_stats.to_string())

    # Analyse ATR à l'entrée
    print(f"\n{'─' * 50}")
    print(f"  ANALYSE ATR / STOP DYN À L'ENTRÉE")
    print(f"{'─' * 50}")
    print(f"  Stop Dyn moyen : {trades_df['stop_dyn'].mean():.0f} pts")
    print(f"  Target Dyn moy : {trades_df['target_dyn'].mean():.0f} pts")
    print(f"  Distribution Stop Dyn :")
    for val in sorted(trades_df['stop_dyn'].unique()):
        count = (trades_df['stop_dyn'] == val).sum()
        subset = trades_df[trades_df['stop_dyn'] == val]
        wr = (subset['pnl_euros'] > 0).mean() * 100
        avg_pnl = subset['pnl_points'].mean()
        print(f"    {val:>4} pts : {count:>4} trades | WR: {wr:.1f}% | Moy: {avg_pnl:.1f} pts")

    # ============================================================
    # 6. DIAGNOSTIC RÉINVESTISSEMENT
    # ============================================================
    print(f"\n{'=' * 70}")
    print(f"  DIAGNOSTIC RÉINVESTISSEMENT")
    print(f"{'=' * 70}")

    # Simuler SANS réinvestissement pour comparer
    params_no_reinv = StrategyParams()
    params_no_reinv.Reinvestir = 0
    trades_no_reinv, equity_no_reinv = run_backtest(df, params_no_reinv, "No Reinv")
    trades_no_reinv_df = pd.DataFrame(trades_no_reinv)

    if len(trades_no_reinv_df) > 0:
        profit_no_reinv = trades_no_reinv_df['pnl_euros'].sum()
        profit_reinv = total_profit

        print(f"  SANS réinvestissement : {profit_no_reinv:,.2f} €")
        print(f"  AVEC réinvestissement : {profit_reinv:,.2f} €")
        print(f"  Bonus réinvestissement: {profit_reinv - profit_no_reinv:,.2f} € ({((profit_reinv/profit_no_reinv)-1)*100:.1f}%)")

        # Taille position comparée
        first_no = trades_no_reinv_df.iloc[0]['pos_size']
        last_no = trades_no_reinv_df.iloc[-1]['pos_size']
        print(f"\n  Taille pos sans réinv : {first_no} → {last_no} (fixe)")
        print(f"  Taille pos avec réinv : {first_size} → {last_size} (+{((last_size/first_size)-1)*100:.1f}%)")

        # Pourquoi c'est lent ?
        print(f"\n  POURQUOI LA CROISSANCE EST LENTE ?")
        print(f"  {'─' * 40}")
        avg_risk_per_trade = params.CapInit * (params.Risque / 100)
        print(f"  Risque par trade (initial) : {avg_risk_per_trade:.2f}€")
        print(f"  Espérance par trade        : {esperance:.2f}€")
        print(f"  Ratio espérance/risque     : {esperance/avg_risk_per_trade*100:.2f}%")
        print(f"  → Pour doubler le capital ({params.CapInit}€ de profit),")
        print(f"    il faudrait ~{params.CapInit/max(esperance,0.01):.0f} trades à l'espérance actuelle")
        print(f"  → Sur {total_trades} trades en {(pd.to_datetime(trades_df.iloc[-1]['entry_time']).year - pd.to_datetime(trades_df.iloc[0]['entry_time']).year + 1)} ans,")
        print(f"    le profit ({total_profit:,.0f}€) ne fait que {total_profit/params.CapInit*100:.0f}% du capital")
        print(f"    → La taille de position ne peut pas croître vite")

    # ============================================================
    # 7. SUGGESTIONS D'OPTIMISATION
    # ============================================================
    print(f"\n{'=' * 70}")
    print(f"  PISTES D'OPTIMISATION")
    print(f"{'=' * 70}")

    # Test rapide : varier CoeffStop
    print(f"\n  --- Test CoeffStop (stop plus ou moins large) ---")
    for cs in [2.4, 2.8, 3.0, 3.2, 3.6, 4.0]:
        p_test = StrategyParams()
        p_test.CoeffStop = cs
        p_test.Reinvestir = 0  # Comparer sans réinv pour isoler l'effet
        t_test, _ = run_backtest(df, p_test)
        t_df = pd.DataFrame(t_test)
        if len(t_df) > 0:
            pf = abs(t_df[t_df['pnl_euros']>0]['pnl_euros'].sum() / t_df[t_df['pnl_euros']<0]['pnl_euros'].sum()) if t_df[t_df['pnl_euros']<0]['pnl_euros'].sum() != 0 else 999
            wr = (t_df['pnl_euros'] > 0).mean() * 100
            print(f"    CoeffStop={cs:.1f} | {len(t_df)} trades | WR: {wr:.1f}% | PF: {pf:.2f} | Profit: {t_df['pnl_euros'].sum():,.0f}€")

    # Test : varier TargetMult
    print(f"\n  --- Test TargetMult (ratio target/stop) ---")
    for tm in [1.6, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0]:
        p_test = StrategyParams()
        p_test.TargetMult = tm
        p_test.Reinvestir = 0
        t_test, _ = run_backtest(df, p_test)
        t_df = pd.DataFrame(t_test)
        if len(t_df) > 0:
            pf = abs(t_df[t_df['pnl_euros']>0]['pnl_euros'].sum() / t_df[t_df['pnl_euros']<0]['pnl_euros'].sum()) if t_df[t_df['pnl_euros']<0]['pnl_euros'].sum() != 0 else 999
            wr = (t_df['pnl_euros'] > 0).mean() * 100
            print(f"    TargetMult={tm:.1f} | {len(t_df)} trades | WR: {wr:.1f}% | PF: {pf:.2f} | Profit: {t_df['pnl_euros'].sum():,.0f}€")

    # Test : varier CoeffBE
    print(f"\n  --- Test CoeffBE (seuil breakeven) ---")
    for cbe in [0.6, 0.8, 1.0, 1.2, 1.5, 2.0]:
        p_test = StrategyParams()
        p_test.CoeffBE = cbe
        p_test.Reinvestir = 0
        t_test, _ = run_backtest(df, p_test)
        t_df = pd.DataFrame(t_test)
        if len(t_df) > 0:
            pf = abs(t_df[t_df['pnl_euros']>0]['pnl_euros'].sum() / t_df[t_df['pnl_euros']<0]['pnl_euros'].sum()) if t_df[t_df['pnl_euros']<0]['pnl_euros'].sum() != 0 else 999
            wr = (t_df['pnl_euros'] > 0).mean() * 100
            # Aussi check combien finissent en trailing stop
            ts_count = len(t_df[t_df['exit_reason'] == 'Trailing Stop'])
            print(f"    CoeffBE={cbe:.1f} | {len(t_df)} trades | WR: {wr:.1f}% | PF: {pf:.2f} | Profit: {t_df['pnl_euros'].sum():,.0f}€ | Trailing: {ts_count}")

    # Test : varier CoefLockProfit
    print(f"\n  --- Test CoefLockProfit (profit verrouillé) ---")
    for clp in [0.15, 0.2, 0.3, 0.4, 0.5, 0.6]:
        p_test = StrategyParams()
        p_test.CoefLockProfit = clp
        p_test.Reinvestir = 0
        t_test, _ = run_backtest(df, p_test)
        t_df = pd.DataFrame(t_test)
        if len(t_df) > 0:
            pf = abs(t_df[t_df['pnl_euros']>0]['pnl_euros'].sum() / t_df[t_df['pnl_euros']<0]['pnl_euros'].sum()) if t_df[t_df['pnl_euros']<0]['pnl_euros'].sum() != 0 else 999
            wr = (t_df['pnl_euros'] > 0).mean() * 100
            print(f"    CoefLockProfit={clp:.2f} | {len(t_df)} trades | WR: {wr:.1f}% | PF: {pf:.2f} | Profit: {t_df['pnl_euros'].sum():,.0f}€")

    # Test : fenêtre d'entrée élargie
    print(f"\n  --- Info : La fenêtre d'entrée est 15h30-17h30 ---")
    print(f"  Répartition temporelle des entrées actuelles :")
    for hm, grp in trades_df.groupby('entry_hm'):
        pct = len(grp) / total_trades * 100
        avg_pnl = grp['pnl_euros'].mean()
        print(f"    {hm} : {len(grp)} trades ({pct:.1f}%) | Moy: {avg_pnl:.2f}€")

    print(f"\n{'=' * 70}")
    print("BACKTEST TERMINÉ")
    print(f"{'=' * 70}")
