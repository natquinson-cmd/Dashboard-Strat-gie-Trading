"""
Backtest NAS 15 OPR R2.2 reinv V1.2 - V3 CORRIGE
Corrections :
1. ATR Wilder (alpha=1/14) au lieu de EWM span=14
2. Priorite intra-barre : check target AVANT stop si open est favorable
3. Periode alignee sur PRT : sept 2022 -> mars 2026
4. NiveauStop initialise correctement a entry-StopDyn (comme PRT)
5. Logique PRT fidele : SET STOP pLOSS + SET TARGET pPROFIT + SELL AT NiveauStop STOP
"""
import pandas as pd
import numpy as np
from datetime import time, datetime
import sys, io, warnings
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# CHARGEMENT ET RESAMPLING
# ============================================================
DATA_PATH = r"C:\Users\quinson\Desktop\Claude\Historique données bourse\historique_usatechidxusd_1min.csv"

print("Chargement des donnees 1min...")
df_raw = pd.read_csv(DATA_PATH, sep=';', decimal=',', parse_dates=['Date'], index_col='Date')

# Resample 15min
df = df_raw.resample('15min').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
print(f"Donnees 15min : {len(df):,} barres | {df.index[0]} -> {df.index[-1]}")

# ============================================================
# ATR WILDER (methode PRT)
# Wilder's smoothing: ATR(n) = (ATR(n-1) * (period-1) + TR(n)) / period
# Equivalent a EWM avec alpha=1/period (pas 2/(period+1))
# ============================================================
df['PrevClose'] = df['Close'].shift(1)
df['TR'] = np.maximum(
    df['High'] - df['Low'],
    np.maximum(
        abs(df['High'] - df['PrevClose']),
        abs(df['Low'] - df['PrevClose'])
    )
)

# Wilder's ATR : alpha = 1/14
atr_period = 14
atr_values = np.zeros(len(df))
tr_arr = df['TR'].values

# Premier ATR = SMA des 14 premiers TR
first_valid = 0
for i in range(len(tr_arr)):
    if not np.isnan(tr_arr[i]):
        first_valid = i
        break

# SMA initiale
atr_values[first_valid + atr_period - 1] = np.mean(tr_arr[first_valid:first_valid + atr_period])

# Wilder's smoothing
for i in range(first_valid + atr_period, len(tr_arr)):
    atr_values[i] = (atr_values[i-1] * (atr_period - 1) + tr_arr[i]) / atr_period

df['ATR14'] = atr_values

# ============================================================
# PARAMETRES
# ============================================================
class Params:
    CoeffBE = 1.2
    CoeffStop = 3.2
    TargetMult = 2.2
    CoefLockProfit = 0.3
    CapInit = 5300
    Risque = 2.2
    Reinvestir = 1
    PipValue = 1.0  # US Tech 100 Cash (1EUR)

# ============================================================
# MOTEUR DE BACKTEST V3 - FIDELE A PRT
# ============================================================
def run_backtest(df, p, start_date=None, end_date=None):
    trades = []
    strategy_profit = 0.0
    position = 0
    entry_price = 0.0
    stop_dyn = 0
    target_dyn = 0
    niveau_stop = 0.0
    static_be_trigger = 0.0
    static_lock_trigger = 0.0
    static_lock_profit = 0.0
    static_target_prix = 0.0
    pos_size = 0.0
    opr_high = opr_low = None
    today_trade = 0
    current_date = None
    daily_profit = 0.0
    trade_entry_time = None
    trade_type = ""

    bars = df.reset_index()

    for i in range(max(atr_period + 1, 1), len(bars)):
        row = bars.iloc[i]
        dt = row['Date']
        o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
        atr = row['ATR14']
        t = dt.time()
        d = dt.date()

        # Filtrer par date
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue

        # Skip si ATR pas encore calcule
        if atr == 0 or np.isnan(atr):
            continue

        # --- Nouveau jour (PRT: IF Date <> Date[1]) ---
        if d != current_date:
            current_date = d
            today_trade = 0
            daily_profit = strategy_profit
            niveau_stop = 0
            static_target_prix = 0

        # --- OPR (15h30) ---
        if t == time(15, 30):
            opr_high = h
            opr_low = l

        # --- Calculs dynamiques (recalcules a chaque barre) ---
        stop_dyn_calc = round(max(85, min(185, atr * p.CoeffStop)))
        target_dyn_calc = round(stop_dyn_calc * p.TargetMult)

        # --- TodayTrade detection (PRT logic) ---
        # IF STRATEGYPROFIT <> DailyProfit OR ONMARKET THEN TodayTrade = 1
        if strategy_profit != daily_profit or position != 0:
            today_trade = 1

        # --- Capital et taille de position ---
        if p.Reinvestir == 1:
            cap_actuel = p.CapInit + strategy_profit
        else:
            cap_actuel = p.CapInit

        if stop_dyn_calc > 0:
            raw_size = (cap_actuel * (p.Risque / 100)) / (stop_dyn_calc * p.PipValue)
            pos_size_calc = round(max(0.01, raw_size), 2)
        else:
            pos_size_calc = 0.5

        # ===============================================
        # GESTION POSITION EN COURS
        # ===============================================
        if position != 0:
            closed = False
            close_reason = ""
            trade_pnl_points = 0
            exit_price = 0

            # ----- LOGIQUE PRT INTRA-BARRE -----
            # PRT verifie SET STOP pLOSS et SET TARGET pPROFIT
            # Priorite : si les deux sont touches dans la meme barre,
            # PRT regarde l'Open de la barre pour determiner la direction probable

            stop_price_long = entry_price - stop_dyn
            target_price_long = entry_price + target_dyn
            stop_price_short = entry_price + stop_dyn
            target_price_short = entry_price - target_dyn

            if position == 1:  # LONG
                stop_hit = (l <= stop_price_long)
                target_hit = (h >= target_price_long)
                # Check aussi NiveauStop (trailing)
                trailing_hit = (niveau_stop > stop_price_long and l <= niveau_stop)

                if stop_hit and target_hit:
                    # Les deux touches : utiliser l'Open pour determiner l'ordre
                    if o <= stop_price_long:
                        # Open deja sous le stop -> stop en premier
                        trade_pnl_points = -stop_dyn; close_reason = "Stop Loss"; closed = True
                    elif o >= target_price_long:
                        # Open deja au-dessus du target -> target en premier
                        trade_pnl_points = target_dyn; close_reason = "Target"; closed = True
                    else:
                        # Open entre les deux : PRT favorise le target dans certaines implem
                        # Mais par defaut : distance la plus proche de l'Open
                        dist_to_stop = o - stop_price_long
                        dist_to_target = target_price_long - o
                        if dist_to_target <= dist_to_stop:
                            trade_pnl_points = target_dyn; close_reason = "Target"; closed = True
                        else:
                            trade_pnl_points = -stop_dyn; close_reason = "Stop Loss"; closed = True
                elif target_hit:
                    trade_pnl_points = target_dyn; close_reason = "Target"; closed = True
                elif trailing_hit:
                    trade_pnl_points = niveau_stop - entry_price; close_reason = "Trailing Stop"; closed = True
                elif stop_hit:
                    trade_pnl_points = -stop_dyn; close_reason = "Stop Loss"; closed = True

            elif position == -1:  # SHORT
                stop_hit = (h >= stop_price_short)
                target_hit = (l <= target_price_short)
                trailing_hit = (niveau_stop > 0 and niveau_stop < stop_price_short and h >= niveau_stop)

                if stop_hit and target_hit:
                    if o >= stop_price_short:
                        trade_pnl_points = -stop_dyn; close_reason = "Stop Loss"; closed = True
                    elif o <= target_price_short:
                        trade_pnl_points = target_dyn; close_reason = "Target"; closed = True
                    else:
                        dist_to_stop = stop_price_short - o
                        dist_to_target = o - target_price_short
                        if dist_to_target <= dist_to_stop:
                            trade_pnl_points = target_dyn; close_reason = "Target"; closed = True
                        else:
                            trade_pnl_points = -stop_dyn; close_reason = "Stop Loss"; closed = True
                elif target_hit:
                    trade_pnl_points = target_dyn; close_reason = "Target"; closed = True
                elif trailing_hit:
                    trade_pnl_points = entry_price - niveau_stop; close_reason = "Trailing Stop"; closed = True
                elif stop_hit:
                    trade_pnl_points = -stop_dyn; close_reason = "Stop Loss"; closed = True

            # Si pas ferme par stop/target/trailing, gerer le trailing et EOD
            if not closed:
                # Mise a jour des paliers trailing
                # PALIER 1 : Breakeven
                if position == 1 and (c - entry_price) > static_be_trigger:
                    nouv_stop = entry_price + 5  # tradeprice + 5
                    niveau_stop = max(niveau_stop, nouv_stop)
                elif position == -1 and (entry_price - c) > static_be_trigger:
                    nouv_stop = entry_price - 5
                    if niveau_stop == 0:
                        niveau_stop = nouv_stop
                    else:
                        niveau_stop = min(niveau_stop, nouv_stop)

                # PALIER 2 : Lock Profit
                if position == 1 and (c - entry_price) > static_lock_trigger:
                    nouv_stop = entry_price + static_lock_profit
                    niveau_stop = max(niveau_stop, nouv_stop)
                elif position == -1 and (entry_price - c) > static_lock_trigger:
                    nouv_stop = entry_price - static_lock_profit
                    if niveau_stop == 0:
                        niveau_stop = nouv_stop
                    else:
                        niveau_stop = min(niveau_stop, nouv_stop)

                # Cloture fin de journee
                if t >= time(21, 55):
                    if position == 1:
                        trade_pnl_points = c - entry_price
                    else:
                        trade_pnl_points = entry_price - c
                    closed = True
                    close_reason = "EOD Close"

            if closed:
                pnl_euros = trade_pnl_points * pos_size * p.PipValue
                strategy_profit += pnl_euros
                trades.append({
                    'entry_time': trade_entry_time, 'exit_time': dt,
                    'type': trade_type, 'entry_price': entry_price,
                    'exit_reason': close_reason,
                    'pnl_points': round(trade_pnl_points, 2),
                    'pos_size': pos_size, 'pnl_euros': round(pnl_euros, 2),
                    'cumul_profit': round(strategy_profit, 2),
                    'stop_dyn': stop_dyn, 'target_dyn': target_dyn,
                    'cap_actuel': round(cap_actuel, 2),
                    'atr': round(atr, 2)
                })
                position = 0

        # ===============================================
        # CONDITIONS D'ENTREE
        # ===============================================
        if today_trade == 0 and opr_high is not None and position == 0:
            if t > time(15, 30) and t <= time(17, 30):
                if c > opr_high:
                    position = 1
                    entry_price = c
                    trade_type = "Long"
                    stop_dyn = stop_dyn_calc
                    target_dyn = target_dyn_calc
                    pos_size = pos_size_calc
                    trade_entry_time = dt
                    # Fixer les seuils STATIQUES (comme PRT : MonATR au moment de l'entree)
                    static_be_trigger = atr * p.CoeffBE
                    static_lock_trigger = target_dyn * 0.6
                    static_lock_profit = target_dyn * p.CoefLockProfit
                    static_target_prix = c + target_dyn
                    # NiveauStop = close - StopDyn (comme PRT)
                    niveau_stop = c - stop_dyn
                    today_trade = 1

                elif c < opr_low:
                    position = -1
                    entry_price = c
                    trade_type = "Short"
                    stop_dyn = stop_dyn_calc
                    target_dyn = target_dyn_calc
                    pos_size = pos_size_calc
                    trade_entry_time = dt
                    static_be_trigger = atr * p.CoeffBE
                    static_lock_trigger = target_dyn * 0.6
                    static_lock_profit = target_dyn * p.CoefLockProfit
                    static_target_prix = c - target_dyn
                    # NiveauStop = close + StopDyn (comme PRT pour short)
                    niveau_stop = c + stop_dyn
                    today_trade = 1

    return pd.DataFrame(trades)


def print_stats(tdf, label=""):
    if len(tdf) == 0:
        print(f"  {label}: AUCUN TRADE"); return
    n = len(tdf)
    w = tdf[tdf['pnl_euros'] > 0]
    lo = tdf[tdf['pnl_euros'] < 0]
    be = tdf[tdf['pnl_euros'] == 0]
    wr = len(w)/n*100
    pf = abs(w['pnl_euros'].sum()/lo['pnl_euros'].sum()) if len(lo)>0 and lo['pnl_euros'].sum()!=0 else 999
    profit = tdf['pnl_euros'].sum()
    avg_win = w['pnl_euros'].mean() if len(w)>0 else 0
    avg_loss = lo['pnl_euros'].mean() if len(lo)>0 else 0
    peak = dd = 0
    for p in tdf['pnl_euros'].cumsum():
        peak = max(peak, p); dd = max(dd, peak - p)
    print(f"\n  === {label} ===")
    print(f"  Trades       : {n} (G:{len(w)} P:{len(lo)} N:{len(be)})")
    print(f"  Win Rate     : {wr:.1f}%")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  Profit Total : {profit:,.2f} EUR")
    print(f"  Gain moyen   : {avg_win:,.2f} EUR")
    print(f"  Perte moyenne: {avg_loss:,.2f} EUR")
    print(f"  Esperance    : {profit/n:,.2f} EUR / trade")
    print(f"  Max Drawdown : {dd:,.2f} EUR")
    if len(tdf) > 0:
        print(f"  Capital final: {tdf.iloc[-1]['cap_actuel'] + tdf.iloc[-1]['pnl_euros']:,.2f} EUR")
        print(f"  Taille pos   : {tdf.iloc[0]['pos_size']} -> {tdf.iloc[-1]['pos_size']}")
    # Par type sortie
    exit_stats = tdf.groupby('exit_reason').agg(
        count=('pnl_euros','count'),
        total_eur=('pnl_euros','sum'),
        avg_pts=('pnl_points','mean')
    ).round(2)
    print(f"\n  Sorties:")
    for reason, row in exit_stats.iterrows():
        print(f"    {reason:15s}: {int(row['count']):>4} trades | Total: {row['total_eur']:>10,.2f}EUR | Moy: {row['avg_pts']:.1f} pts")
    # Long vs Short
    for tt in ['Long', 'Short']:
        sub = tdf[tdf['type'] == tt]
        if len(sub) > 0:
            sub_wr = (sub['pnl_euros']>0).mean()*100
            print(f"  {tt:5s}: {len(sub)} trades | WR: {sub_wr:.1f}% | Total: {sub['pnl_euros'].sum():,.2f}EUR")
    # Par annee
    tdf_copy = tdf.copy()
    tdf_copy['year'] = pd.to_datetime(tdf_copy['entry_time']).dt.year
    yearly = tdf_copy.groupby('year').agg(
        nb=('pnl_euros','count'), profit=('pnl_euros','sum'),
        wr=('pnl_euros', lambda x: (x>0).mean()*100)
    ).round(2)
    print(f"\n  Par annee:")
    for y, row in yearly.iterrows():
        print(f"    {y}: {int(row['nb']):>4} trades | {row['profit']:>10,.2f}EUR | WR: {row['wr']:.1f}%")


# ============================================================
# TESTS
# ============================================================
p = Params()

# 1. Meme periode que PRT : 12 sept 2022 -> 6 mars 2026
print("\n" + "=" * 80)
print("TEST A : MEME PERIODE QUE PRT (12 sept 2022 -> 6 mars 2026)")
print("AVEC reinvestissement (Reinvestir=1)")
print("=" * 80)

from datetime import date
p.Reinvestir = 1
trades_prt_period = run_backtest(df, p,
    start_date=date(2022, 9, 12),
    end_date=date(2026, 3, 6))
print_stats(trades_prt_period, "Periode PRT - AVEC reinv")

# 2. Meme periode SANS reinvestissement
print("\n" + "=" * 80)
print("TEST B : MEME PERIODE SANS REINVESTISSEMENT")
print("=" * 80)
p2 = Params()
p2.Reinvestir = 0
trades_prt_no_reinv = run_backtest(df, p2,
    start_date=date(2022, 9, 12),
    end_date=date(2026, 3, 6))
print_stats(trades_prt_no_reinv, "Periode PRT - SANS reinv")

# 3. Comparaison cible
print("\n" + "=" * 80)
print("COMPARAISON AVEC LES RESULTATS PRT")
print("=" * 80)
my_n = len(trades_prt_period) if len(trades_prt_period) > 0 else 0
my_w = len(trades_prt_period[trades_prt_period['pnl_euros']>0]) if my_n > 0 else 0
my_wr = my_w/my_n*100 if my_n > 0 else 0
my_profit = trades_prt_period['pnl_euros'].sum() if my_n > 0 else 0

print(f"  {'Metrique':<20} {'PRT':>15} {'Mon backtest':>15} {'Ecart':>12}")
print(f"  {'-'*62}")
print(f"  {'Trades':<20} {'894':>15} {my_n:>15}")
print(f"  {'Win Rate':<20} {'67.9%':>15} {my_wr:>14.1f}%")
print(f"  {'Profit':<20} {'53,812 EUR':>15} {my_profit:>12,.0f} EUR")

# 4. Analyser quelques trades pour debug
if len(trades_prt_period) > 0:
    print(f"\n  --- Premiers trades pour verification ---")
    for i in range(min(10, len(trades_prt_period))):
        t = trades_prt_period.iloc[i]
        print(f"  {i+1:>3} | {str(t['entry_time']):>20} | {t['type']:>5} | Entry: {t['entry_price']:>10.2f} | "
              f"Stop: {t['stop_dyn']:>4} | Target: {t['target_dyn']:>4} | "
              f"Exit: {t['exit_reason']:>15} | PnL: {t['pnl_points']:>8.1f} pts ({t['pnl_euros']:>8.2f}EUR) | "
              f"Size: {t['pos_size']} | ATR: {t['atr']}")

# 5. Periode complete pour reference
print("\n" + "=" * 80)
print("TEST C : PERIODE COMPLETE (2019-2026) AVEC reinvestissement")
print("=" * 80)
p3 = Params()
p3.Reinvestir = 1
trades_full = run_backtest(df, p3)
print_stats(trades_full, "Periode complete - AVEC reinv")

# 6. Diagnostic du NiveauStop
print("\n" + "=" * 80)
print("DIAGNOSTIC : IMPACT DU NIVEAUSTOP INITIAL")
print("=" * 80)
print("  Dans PRT, NiveauStop est initialise a close-StopDyn (long) ou close+StopDyn (short)")
print("  Cela signifie que SELL AT NiveauStop STOP commence au meme niveau que SET STOP pLOSS")
print("  Le trailing ne 'coupe' les trades que si le BE ou Lock trigger est active")
print("")

# Compter les trades ou le trailing a ete benefique vs EOD
if len(trades_prt_period) > 0:
    trail = trades_prt_period[trades_prt_period['exit_reason'] == 'Trailing Stop']
    eod = trades_prt_period[trades_prt_period['exit_reason'] == 'EOD Close']
    tgt = trades_prt_period[trades_prt_period['exit_reason'] == 'Target']
    sl = trades_prt_period[trades_prt_period['exit_reason'] == 'Stop Loss']
    print(f"  Stop Loss    : {len(sl):>4} trades | Moy: {sl['pnl_points'].mean():>7.1f} pts")
    print(f"  Target       : {len(tgt):>4} trades | Moy: {tgt['pnl_points'].mean():>7.1f} pts")
    print(f"  Trailing Stop: {len(trail):>4} trades | Moy: {trail['pnl_points'].mean():>7.1f} pts")
    print(f"  EOD Close    : {len(eod):>4} trades | Moy: {eod['pnl_points'].mean():>7.1f} pts")

print("\n" + "=" * 80)
print("BACKTEST V3 TERMINE")
print("=" * 80)
