"""
Backtest NAS 15 OPR - V2 OPTIMISATION APPROFONDIE
Identification des vrais leviers d'amélioration
"""
import pandas as pd
import numpy as np
from datetime import time
import sys, io
import warnings
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# CHARGEMENT ET RESAMPLING
# ============================================================
DATA_PATH = r"C:\Users\quinson\Desktop\Claude\Historique données bourse\historique_usatechidxusd_1min.csv"

df_raw = pd.read_csv(DATA_PATH, sep=';', decimal=',', parse_dates=['Date'], index_col='Date')
df = df_raw.resample('15min').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
df['PrevClose'] = df['Close'].shift(1)
df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['PrevClose']), abs(df['Low']-df['PrevClose'])))
df['ATR14'] = df['TR'].ewm(span=14, adjust=False).mean()

print("Donnees chargees :", len(df), "barres 15min")

# ============================================================
# MOTEUR DE BACKTEST PARAMÉTRABLE
# ============================================================
def run_backtest(df, config):
    """Config dict avec tous les parametres ajustables"""
    c = {
        'CoeffBE': 1.2, 'CoeffStop': 3.2, 'TargetMult': 2.2,
        'CoefLockProfit': 0.3, 'CapInit': 5300, 'Risque': 2.2,
        'Reinvestir': 0, 'PipValue': 1.0,
        'use_trailing': True,       # Active/désactive le trailing
        'allow_short': True,        # Autoriser les shorts
        'allow_long': True,         # Autoriser les longs
        'entry_start': time(15,30), # Début fenêtre d'entrée
        'entry_end': time(17,30),   # Fin fenêtre d'entrée
        'opr_time': time(15,30),    # Heure OPR
        'eod_time': time(21,55),    # Clôture fin de journée
        'stop_min': 85, 'stop_max': 185,
        'be_offset': 5,             # Points au-dessus du BE
        'lock_trigger_pct': 0.6,    # Seuil activation lock (% du target)
        'atr_period': 14,
        'opr_filter_min': 0,        # Taille min de l'OPR pour trader
        'opr_filter_max': 9999,     # Taille max de l'OPR
    }
    c.update(config)

    trades = []
    strategy_profit = 0.0
    position = 0
    entry_price = stop_dyn = target_dyn = 0
    niveau_stop = static_be_trigger = static_lock_trigger = static_lock_profit = 0.0
    pos_size = 0.0
    opr_high = opr_low = None
    today_trade = 0
    current_date = None
    trade_entry_time = None
    trade_type = ""

    bars = df.reset_index()

    for i in range(14, len(bars)):
        row = bars.iloc[i]
        dt = row['Date']
        o, h, l, cl = row['Open'], row['High'], row['Low'], row['Close']
        atr = row['ATR14']
        t = dt.time()
        d = dt.date()

        if d != current_date:
            current_date = d
            today_trade = 0
            opr_high = opr_low = None

        if t == c['opr_time']:
            opr_high = h
            opr_low = l

        stop_dyn_calc = round(max(c['stop_min'], min(c['stop_max'], atr * c['CoeffStop'])))
        target_dyn_calc = round(stop_dyn_calc * c['TargetMult'])

        if c['Reinvestir'] == 1:
            cap_actuel = c['CapInit'] + strategy_profit
        else:
            cap_actuel = c['CapInit']

        if stop_dyn_calc > 0:
            raw_size = (cap_actuel * (c['Risque'] / 100)) / (stop_dyn_calc * c['PipValue'])
            pos_size_calc = round(max(0.01, raw_size), 2)
        else:
            pos_size_calc = 0.5

        # --- GESTION POSITION ---
        if position != 0:
            closed = False
            close_reason = ""
            trade_pnl_points = 0

            if position == 1:
                if l <= entry_price - stop_dyn:
                    trade_pnl_points = -stop_dyn; closed = True; close_reason = "Stop Loss"
                elif h >= entry_price + target_dyn:
                    trade_pnl_points = target_dyn; closed = True; close_reason = "Target"
            else:
                if h >= entry_price + stop_dyn:
                    trade_pnl_points = -stop_dyn; closed = True; close_reason = "Stop Loss"
                elif l <= entry_price - target_dyn:
                    trade_pnl_points = target_dyn; closed = True; close_reason = "Target"

            if not closed and c['use_trailing']:
                # Breakeven
                if position == 1 and (cl - entry_price) > static_be_trigger:
                    niveau_stop = max(niveau_stop, entry_price + c['be_offset'])
                elif position == -1 and (entry_price - cl) > static_be_trigger:
                    ns = entry_price - c['be_offset']
                    niveau_stop = ns if niveau_stop == 0 else min(niveau_stop, ns)

                # Lock profit
                if position == 1 and (cl - entry_price) > static_lock_trigger:
                    niveau_stop = max(niveau_stop, entry_price + static_lock_profit)
                elif position == -1 and (entry_price - cl) > static_lock_trigger:
                    ns = entry_price - static_lock_profit
                    niveau_stop = ns if niveau_stop == 0 else min(niveau_stop, ns)

                # Check trailing stop
                if position == 1 and niveau_stop > 0 and l <= niveau_stop:
                    trade_pnl_points = niveau_stop - entry_price; closed = True; close_reason = "Trailing Stop"
                elif position == -1 and niveau_stop > 0 and h >= niveau_stop:
                    trade_pnl_points = entry_price - niveau_stop; closed = True; close_reason = "Trailing Stop"

            if not closed and t >= c['eod_time']:
                trade_pnl_points = (cl - entry_price) if position == 1 else (entry_price - cl)
                closed = True; close_reason = "EOD Close"

            if closed:
                pnl_euros = trade_pnl_points * pos_size * c['PipValue']
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
                    'opr_range': round(opr_high - opr_low, 2) if opr_high and opr_low else 0
                })
                position = 0
                today_trade = 1

        # --- ENTRÉE ---
        if position == 0 and today_trade == 0 and opr_high is not None:
            if t > c['entry_start'] and t <= c['entry_end']:
                opr_range = opr_high - opr_low
                if opr_range < c['opr_filter_min'] or opr_range > c['opr_filter_max']:
                    pass  # Filtre OPR
                else:
                    entered = False
                    if c['allow_long'] and cl > opr_high:
                        position = 1; entry_price = cl; trade_type = "Long"; entered = True
                    elif c['allow_short'] and cl < opr_low:
                        position = -1; entry_price = cl; trade_type = "Short"; entered = True

                    if entered:
                        stop_dyn = stop_dyn_calc
                        target_dyn = target_dyn_calc
                        pos_size = pos_size_calc
                        trade_entry_time = dt
                        today_trade = 1
                        static_be_trigger = atr * c['CoeffBE']
                        static_lock_trigger = target_dyn * c['lock_trigger_pct']
                        static_lock_profit = target_dyn * c['CoefLockProfit']
                        niveau_stop = 0

    return pd.DataFrame(trades)


def stats(tdf, label=""):
    if len(tdf) == 0:
        print(f"  {label}: AUCUN TRADE")
        return
    n = len(tdf)
    w = tdf[tdf['pnl_euros']>0]
    l = tdf[tdf['pnl_euros']<0]
    wr = len(w)/n*100
    pf = abs(w['pnl_euros'].sum()/l['pnl_euros'].sum()) if len(l)>0 and l['pnl_euros'].sum()!=0 else 999
    profit = tdf['pnl_euros'].sum()
    esp = tdf['pnl_euros'].mean()
    # Drawdown
    peak = dd = 0
    for p in tdf['pnl_euros'].cumsum():
        peak = max(peak, p); dd = max(dd, peak - p)
    print(f"  {label:45s} | {n:>4} trades | WR: {wr:5.1f}% | PF: {pf:5.2f} | Profit: {profit:>9,.0f}EUR | Esp: {esp:>7.1f}EUR | DD: {dd:>7,.0f}EUR")


# ============================================================
# ANALYSE BASELINE
# ============================================================
print("\n" + "=" * 120)
print("ANALYSE BASELINE (sans reinvestissement)")
print("=" * 120)

baseline = run_backtest(df, {'Reinvestir': 0})
stats(baseline, "BASELINE original")

# ============================================================
# TEST 1 : IMPACT DU TRAILING STOP
# ============================================================
print("\n" + "=" * 120)
print("TEST 1 : TRAILING STOP (le plus gros probleme)")
print("=" * 120)

no_trail = run_backtest(df, {'use_trailing': False})
stats(no_trail, "SANS trailing (target + stop + EOD seulement)")
stats(baseline, "AVEC trailing (baseline)")

# Analyser ce que le trailing fait
if len(baseline) > 0:
    trail_trades = baseline[baseline['exit_reason'] == 'Trailing Stop']
    eod_baseline = baseline[baseline['exit_reason'] == 'EOD Close']
    eod_notrail = no_trail[no_trail['exit_reason'] == 'EOD Close']
    print(f"\n  Le trailing transforme {len(trail_trades)} trades en sortie anticipee")
    print(f"  Gain moyen trailing: {trail_trades['pnl_points'].mean():.1f} pts")
    print(f"  Gain moyen EOD baseline: {eod_baseline['pnl_points'].mean():.1f} pts")
    print(f"  Gain moyen EOD sans trailing: {eod_notrail['pnl_points'].mean():.1f} pts")
    print(f"  --> Le trailing COUPE les gagnants a {trail_trades['pnl_points'].mean():.1f} pts au lieu de les laisser courir")

# ============================================================
# TEST 2 : LONG ONLY vs SHORT ONLY vs BOTH
# ============================================================
print("\n" + "=" * 120)
print("TEST 2 : LONG vs SHORT")
print("=" * 120)

long_only = run_backtest(df, {'allow_short': False})
short_only = run_backtest(df, {'allow_long': False})
stats(long_only, "LONG ONLY")
stats(short_only, "SHORT ONLY")
stats(baseline, "LONG + SHORT (baseline)")

# ============================================================
# TEST 3 : CoeffBE (seuil breakeven)
# ============================================================
print("\n" + "=" * 120)
print("TEST 3 : SEUIL BREAKEVEN (CoeffBE)")
print("=" * 120)

for cbe in [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 999]:
    label = f"CoeffBE={cbe}" if cbe < 999 else "PAS de BE (trailing off)"
    t = run_backtest(df, {'CoeffBE': cbe})
    stats(t, label)

# ============================================================
# TEST 4 : COMBINAISONS SANS TRAILING
# ============================================================
print("\n" + "=" * 120)
print("TEST 4 : SANS TRAILING - VARIER STOP ET TARGET")
print("=" * 120)

for cs in [2.4, 2.8, 3.2, 3.6, 4.0]:
    for tm in [1.5, 2.0, 2.5, 3.0]:
        t = run_backtest(df, {'use_trailing': False, 'CoeffStop': cs, 'TargetMult': tm})
        stats(t, f"NoTrail CS={cs} TM={tm}")

# ============================================================
# TEST 5 : FILTRE OPR (taille du range)
# ============================================================
print("\n" + "=" * 120)
print("TEST 5 : FILTRE TAILLE OPR")
print("=" * 120)

# D'abord analyser la distribution OPR
if len(baseline) > 0 and 'opr_range' in baseline.columns:
    opr_ranges = baseline['opr_range']
    print(f"  Distribution OPR range : min={opr_ranges.min():.0f} | med={opr_ranges.median():.0f} | max={opr_ranges.max():.0f}")
    print(f"  P25={opr_ranges.quantile(0.25):.0f} | P75={opr_ranges.quantile(0.75):.0f}")

    # Tester des filtres
    for opr_min in [0, 20, 40, 60]:
        for opr_max in [100, 150, 200, 9999]:
            if opr_min < opr_max:
                t = run_backtest(df, {'opr_filter_min': opr_min, 'opr_filter_max': opr_max})
                if len(t) > 100:  # Au moins 100 trades pour être significatif
                    stats(t, f"OPR [{opr_min}-{opr_max}]")

# ============================================================
# TEST 6 : SANS TRAILING + LONG ONLY (les 2 meilleurs leviers combines)
# ============================================================
print("\n" + "=" * 120)
print("TEST 6 : COMBINAISON DES MEILLEURS LEVIERS")
print("=" * 120)

stats(baseline, "BASELINE")

# Sans trailing + long only
t = run_backtest(df, {'use_trailing': False, 'allow_short': False})
stats(t, "Sans trailing + Long only")

# Long only avec trailing plus relax
for cbe in [1.5, 2.0, 2.5, 3.0]:
    t = run_backtest(df, {'allow_short': False, 'CoeffBE': cbe})
    stats(t, f"Long only + CoeffBE={cbe}")

# Sans trailing + Long only + variations stop/target
for cs in [2.8, 3.2, 3.6]:
    for tm in [2.0, 2.5, 3.0]:
        t = run_backtest(df, {'use_trailing': False, 'allow_short': False, 'CoeffStop': cs, 'TargetMult': tm})
        stats(t, f"LongOnly NoTrail CS={cs} TM={tm}")

# Long only + trailing relax + OPR filter
for cbe in [2.0, 2.5]:
    for opr_max in [120, 150, 200]:
        t = run_backtest(df, {'allow_short': False, 'CoeffBE': cbe, 'opr_filter_max': opr_max})
        if len(t) > 100:
            stats(t, f"Long BE={cbe} OPR<{opr_max}")

# ============================================================
# TEST 7 : BORNES DE STOP DYNAMIQUE
# ============================================================
print("\n" + "=" * 120)
print("TEST 7 : BORNES MIN/MAX DU STOP DYNAMIQUE")
print("=" * 120)

for smin in [60, 75, 85, 100]:
    for smax in [150, 185, 220, 250]:
        if smin < smax:
            t = run_backtest(df, {'stop_min': smin, 'stop_max': smax})
            stats(t, f"Stop bornes [{smin}-{smax}]")

# ============================================================
# TEST 8 : HEURE DE CLOTURE EOD
# ============================================================
print("\n" + "=" * 120)
print("TEST 8 : HEURE DE CLOTURE EOD")
print("=" * 120)

for eod_h, eod_m in [(19,55), (20,25), (20,55), (21,25), (21,55), (22,0)]:
    t = run_backtest(df, {'eod_time': time(eod_h, eod_m)})
    stats(t, f"EOD a {eod_h}h{eod_m:02d}")

# ============================================================
# TEST 9 : MEILLEURE COMBINAISON GLOBALE
# ============================================================
print("\n" + "=" * 120)
print("TEST 9 : RECHERCHE DE LA MEILLEURE CONFIG")
print("=" * 120)

best_profit = -999999
best_config = {}
results = []

# Grid search sur les parametres les plus impactants
for use_trail in [True, False]:
    for allow_sh in [True, False]:
        for cbe in [1.5, 2.0, 2.5]:
            for cs in [2.8, 3.2, 3.6]:
                for tm in [2.0, 2.5, 3.0]:
                    cfg = {
                        'use_trailing': use_trail,
                        'allow_short': allow_sh,
                        'CoeffBE': cbe,
                        'CoeffStop': cs,
                        'TargetMult': tm,
                        'Reinvestir': 0,
                    }
                    t = run_backtest(df, cfg)
                    if len(t) > 50:
                        n = len(t)
                        w = t[t['pnl_euros']>0]
                        l = t[t['pnl_euros']<0]
                        pf = abs(w['pnl_euros'].sum()/l['pnl_euros'].sum()) if len(l)>0 and l['pnl_euros'].sum()!=0 else 999
                        profit = t['pnl_euros'].sum()
                        wr = len(w)/n*100
                        # Drawdown
                        peak = dd = 0
                        for p in t['pnl_euros'].cumsum():
                            peak = max(peak, p); dd = max(dd, peak - p)
                        # Score combine : profit / drawdown
                        score = profit / max(dd, 1)
                        results.append({
                            'trail': use_trail, 'short': allow_sh,
                            'cbe': cbe, 'cs': cs, 'tm': tm,
                            'n': n, 'wr': wr, 'pf': pf,
                            'profit': profit, 'dd': dd, 'score': score
                        })

results_df = pd.DataFrame(results).sort_values('score', ascending=False)
print("\n  TOP 15 CONFIGS (par ratio profit/drawdown) :")
print(f"  {'Trail':>5} {'Short':>5} {'CoeffBE':>7} {'CS':>4} {'TM':>4} | {'Trades':>6} {'WR':>6} {'PF':>6} | {'Profit':>10} {'DD':>9} {'Score':>7}")
print(f"  {'-'*95}")
for _, r in results_df.head(15).iterrows():
    print(f"  {'ON' if r['trail'] else 'OFF':>5} {'ON' if r['short'] else 'OFF':>5} {r['cbe']:>7.1f} {r['cs']:>4.1f} {r['tm']:>4.1f} | {int(r['n']):>6} {r['wr']:>5.1f}% {r['pf']:>6.2f} | {r['profit']:>9,.0f}EUR {r['dd']:>8,.0f}EUR {r['score']:>7.2f}")

# Afficher aussi la meilleure config
best = results_df.iloc[0]
print(f"\n  MEILLEURE CONFIG :")
print(f"    Trailing     : {'ON' if best['trail'] else 'OFF'}")
print(f"    Short        : {'ON' if best['short'] else 'OFF'}")
print(f"    CoeffBE      : {best['cbe']}")
print(f"    CoeffStop    : {best['cs']}")
print(f"    TargetMult   : {best['tm']}")
print(f"    Profit       : {best['profit']:,.0f} EUR")
print(f"    Drawdown     : {best['dd']:,.0f} EUR")
print(f"    Profit Factor: {best['pf']:.2f}")

# Tester avec reinvestissement
best_cfg = {
    'use_trailing': bool(best['trail']),
    'allow_short': bool(best['short']),
    'CoeffBE': best['cbe'],
    'CoeffStop': best['cs'],
    'TargetMult': best['tm'],
    'Reinvestir': 1,
}
t_reinv = run_backtest(df, best_cfg)
print(f"\n  AVEC REINVESTISSEMENT :")
stats(t_reinv, "Meilleure config + reinv")
if len(t_reinv) > 0:
    print(f"    Taille pos initiale: {t_reinv.iloc[0]['pos_size']}")
    print(f"    Taille pos finale  : {t_reinv.iloc[-1]['pos_size']}")
    print(f"    Capital final      : {t_reinv.iloc[-1]['cap_actuel'] + t_reinv.iloc[-1]['pnl_euros']:,.0f} EUR")

print("\n" + "=" * 120)
print("ANALYSE TERMINEE")
print("=" * 120)
