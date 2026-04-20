import pandas as pd
import numpy as np
from datetime import time as dtime
import warnings
warnings.filterwarnings('ignore')

# ─── CHARGEMENT ───────────────────────────────────────────────────────────────
print("Chargement des données...")
df1 = pd.read_csv(
    "C:/Users/quinson/Desktop/Claude/Historique données bourse/historique_usatechidxusd_1min.csv",
    sep=';', decimal=','
)
df1['Date'] = pd.to_datetime(df1['Date'])
df1 = df1.sort_values('Date').reset_index(drop=True)

# ─── AGRÉGATION 15 MIN ────────────────────────────────────────────────────────
print("Agrégation en 15 min...")
df1.set_index('Date', inplace=True)
df15 = df1.resample('15min').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna(subset=['Open'])
df15.reset_index(inplace=True)
df15 = df15[df15['High'] > df15['Low']].copy()

# ─── ATR WILDER 14 ────────────────────────────────────────────────────────────
prev_close = df15['Close'].shift(1)
tr = pd.concat([
    df15['High'] - df15['Low'],
    (df15['High'] - prev_close).abs(),
    (df15['Low']  - prev_close).abs()
], axis=1).max(axis=1)
df15['ATR14'] = tr.ewm(com=13, adjust=False).mean()

df15['date_only'] = df15['Date'].dt.date
df15['bar_time']  = df15['Date'].dt.time
print(f"Donnees : {len(df15)} bougies 15min  |  {df15['Date'].min().date()} -> {df15['Date'].max().date()}\n")

OPR_TIME   = dtime(14, 30)   # 15h30 Paris = 14h30 UTC
ENTRY_END  = dtime(16, 30)   # 17h30 Paris = 16h30 UTC
EOD_TIME   = dtime(20, 55)   # 21h55 Paris = 20h55 UTC
CoeffBE    = 1.2
CoeffStop  = 3.2
TargetMult = 2.2

# ─── MOTEUR DE BACKTEST ───────────────────────────────────────────────────────
def run_backtest(Coeflockprofit=0.3, add_third_lock=False, label=""):
    trades = []

    for date, day_df in df15.groupby('date_only'):
        day_df = day_df.reset_index(drop=True)

        opr_rows = day_df[day_df['bar_time'] == OPR_TIME]
        if opr_rows.empty:
            continue
        opr_idx  = opr_rows.index[0]
        opr_bar  = opr_rows.iloc[0]
        OPRHigh  = opr_bar['High']
        OPRLow   = opr_bar['Low']
        atr_val  = opr_bar['ATR14']
        if pd.isna(atr_val) or atr_val == 0:
            continue

        StopDyn  = round(max(85, min(185, atr_val * CoeffStop)))
        TargetDyn= round(StopDyn * TargetMult)
        StaticBETrigger   = atr_val * CoeffBE
        StaticLockTrigger = TargetDyn * 0.6
        StaticLockProfit  = TargetDyn * Coeflockprofit

        for i in range(opr_idx + 1, len(day_df)):
            bar   = day_df.iloc[i]
            bar_t = bar['bar_time']
            if bar_t > ENTRY_END:
                break

            if   bar['Close'] > OPRHigh: direction = 'LONG'
            elif bar['Close'] < OPRLow:  direction = 'SHORT'
            else: continue

            entry = bar['Close']
            if direction == 'LONG':
                stop_p   = entry - StopDyn
                target_p = entry + TargetDyn
            else:
                stop_p   = entry + StopDyn
                target_p = entry - TargetDyn

            be_done = lock_done = third_done = False
            exit_price = exit_reason = None
            max_favorable = 0   # pour tracer le drawback

            for j in range(i + 1, len(day_df)):
                nb    = day_df.iloc[j]
                nb_t  = nb['bar_time']

                # EOD
                if nb_t >= EOD_TIME:
                    exit_price  = nb['Close']
                    exit_reason = 'EOD'
                    break

                # Profit favorable max atteint (High/Low de la bougie)
                if direction == 'LONG':
                    fav = nb['High'] - entry
                else:
                    fav = entry - nb['Low']
                max_favorable = max(max_favorable, fav)

                # ── Mise à jour des stops ──────────────────────────────────
                if direction == 'LONG':
                    if not be_done and (nb['High'] - entry) > StaticBETrigger:
                        stop_p = max(stop_p, entry + 5); be_done = True
                    if not lock_done and (nb['High'] - entry) > StaticLockTrigger:
                        stop_p = max(stop_p, entry + StaticLockProfit); lock_done = True
                    if add_third_lock and not third_done and (nb['High'] - entry) > TargetDyn * 0.85:
                        stop_p = max(stop_p, entry + TargetDyn * 0.6); third_done = True
                    stop_hit   = nb['Low']  <= stop_p
                    target_hit = nb['High'] >= target_p
                else:
                    if not be_done and (entry - nb['Low']) > StaticBETrigger:
                        stop_p = min(stop_p, entry - 5); be_done = True
                    if not lock_done and (entry - nb['Low']) > StaticLockTrigger:
                        stop_p = min(stop_p, entry - StaticLockProfit); lock_done = True
                    if add_third_lock and not third_done and (entry - nb['Low']) > TargetDyn * 0.85:
                        stop_p = min(stop_p, entry - TargetDyn * 0.6); third_done = True
                    stop_hit   = nb['High'] >= stop_p
                    target_hit = nb['Low']  <= target_p

                if stop_hit and target_hit:
                    exit_price  = stop_p; exit_reason = 'STOP'
                elif target_hit:
                    exit_price  = target_p; exit_reason = 'TARGET'
                elif stop_hit:
                    exit_price  = stop_p; exit_reason = 'STOP'

                if exit_price is not None:
                    break

            if exit_price is None:
                continue

            if direction == 'LONG':
                pnl = exit_price - entry
            else:
                pnl = entry - exit_price

            trades.append({
                'date': date, 'direction': direction,
                'entry': entry, 'exit': exit_price,
                'reason': exit_reason, 'pnl': pnl,
                'StopDyn': StopDyn, 'TargetDyn': TargetDyn, 'atr': atr_val,
                'be_done': be_done, 'lock_done': lock_done,
                'max_favorable': max_favorable,
            })
            break   # 1 trade/jour

    return pd.DataFrame(trades)

# ─── ANALYSE ──────────────────────────────────────────────────────────────────
def analyze(df, label):
    if df.empty:
        print(f"{label}: aucun trade\n"); return
    n   = len(df)
    win = (df['pnl'] > 0).sum()
    los = (df['pnl'] < 0).sum()
    neu = (df['pnl'] == 0).sum()
    wr  = win / n * 100
    tot = df['pnl'].sum()
    avg_w = df[df['pnl'] > 0]['pnl'].mean() if win else 0
    avg_l = df[df['pnl'] < 0]['pnl'].mean() if los else 0
    # Max favorable sans toucher le target
    miss = df[(df['max_favorable'] > df['TargetDyn'] * 0.7) & (df['reason'] != 'TARGET')]

    print(f"\n{'='*54}")
    print(f"  {label}")
    print(f"{'='*54}")
    print(f"  Trades  : {n}  |  Win {win} ({wr:.1f}%)  |  Loss {los}  |  BE/flat {neu}")
    print(f"  P&L tot : {tot:+.0f} pts  |  avg win {avg_w:+.0f}  |  avg loss {avg_l:+.0f}")
    print(f"  Sorties : {df['reason'].value_counts().to_dict()}")
    print(f"  Trades ayant atteint 70% target SANS clôturer au target : {len(miss)}")

    df['year'] = pd.to_datetime(df['date']).dt.year
    for yr, g in df.groupby('year'):
        yr_pnl = g['pnl'].sum()
        yr_wr  = (g['pnl'] > 0).sum() / len(g) * 100
        print(f"    {yr} : {len(g):3d} trades  P&L {yr_pnl:+7.0f} pts  WR {yr_wr:.1f}%")

# ─── LANCEMENT ────────────────────────────────────────────────────────────────
print("Backtest V0 - Actuel (lock 30%)...")
t0 = run_backtest(0.3, False, "V0")
print("Backtest V1 - 3e palier à 85% target...")
t1 = run_backtest(0.3, True,  "V1")
print("Backtest V2 - Lock 50%...")
t2 = run_backtest(0.5, False, "V2")
print("Backtest V3 - Lock 50% + 3e palier...")
t3 = run_backtest(0.5, True,  "V3")

analyze(t0, "V0 – Actuel  (Coeflockprofit=0.30, pas de 3e palier)")
analyze(t1, "V1 – 3e palier à 85% -> lock à 60% target")
analyze(t2, "V2 – Coeflockprofit=0.50  (lock plus haut)")
analyze(t3, "V3 – Combo : lock 50% + 3e palier 85%")

# ─── DÉTAIL : trades où on a laissé filer plus de 100 pts sans sécuriser ─────
print(f"\n{'='*54}")
print("  ANALYSE : trades V0 avec max_favorable > 100 pts mais sortie ≤ lock")
print(f"{'='*54}")
prob = t0[(t0['max_favorable'] > 100) & (t0['reason'] != 'TARGET')].copy()
prob['recupere'] = prob['pnl']
prob['laisse_filer'] = prob['max_favorable'] - prob['pnl']
print(f"  {len(prob)} trades concernés sur {len(t0)}")
print(f"  Points laissés en moyenne : {prob['laisse_filer'].mean():.0f}")
print(f"  Points laissés au total   : {prob['laisse_filer'].sum():.0f}")
print(f"  P&L moyen de ces trades   : {prob['pnl'].mean():.0f}")

# Comparaison même population sur V3
prob3 = t3[(t3['max_favorable'] > 100) & (t3['reason'] != 'TARGET')].copy()
prob3['laisse_filer'] = prob3['max_favorable'] - prob3['pnl']
print(f"\n  Même population sur V3 (lock 50% + 3e palier) :")
print(f"  Points laissés en moyenne : {prob3['laisse_filer'].mean():.0f}")
print(f"  P&L moyen de ces trades   : {prob3['pnl'].mean():.0f}")
print(f"\nFini.")
