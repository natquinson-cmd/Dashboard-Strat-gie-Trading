"""
Analyse des vrais resultats PRT exportes
Comparaison avec/sans reinvestissement + diagnostic
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Donnees PRT reelles - AVEC reinvestissement
reinv = {
    2018: 66.79, 2019: -0.36, 2020: 12.37, 2021: 31.45,
    2022: 67.64, 2023: 57.04, 2024: 194.21, 2025: 56.11, 2026: 36.03
}

# Donnees PRT reelles - SANS reinvestissement
no_reinv = {
    2018: 53.60, 2019: 0.61, 2020: 10.39, 2021: 18.60,
    2022: 29.06, 2023: 19.07, 2024: 36.57, 2025: 11.99, 2026: 6.72
}

print("=" * 80)
print("ANALYSE DES RESULTATS PRT REELS")
print("=" * 80)

# Screenshot PRT (periode sept 2022 - mars 2026)
print("\n  RESULTATS SCREENSHOT PRT (12 sept 2022 -> 6 mars 2026)")
print("  " + "-" * 50)
print(f"  Capital initial : 5,300 EUR")
print(f"  Profit total    : 53,812 EUR")
print(f"  Capital final   : 59,112 EUR")
print(f"  Rendement       : +1,015%")
print(f"  Trades           : 894")
print(f"  Win Rate         : 67.9%")
print(f"  Profit Factor    : 1.51")
print(f"  R/R ratio        : 0.71")
print(f"  Gain moyen       : 60.19 EUR/trade")
print(f"  Gain moyen win   : 262.17 EUR")
print(f"  Perte moy loss   : -366.99 EUR")
print(f"  Max Drawdown     : -8,558 EUR")
print(f"  MFE moyen        : 315.80 EUR")
print(f"  MAE moyen        : -158.45 EUR")

print(f"\n  COMPARAISON ANNUELLE : AVEC vs SANS reinvestissement")
print(f"  {'Annee':>6} | {'Sans reinv':>12} | {'Avec reinv':>12} | {'Boost':>10}")
print(f"  {'-'*50}")

cap_reinv = 5300
cap_no_reinv = 5300
for year in sorted(reinv.keys()):
    r = reinv[year]
    nr = no_reinv[year]
    boost = r - nr
    cap_reinv *= (1 + r/100)
    cap_no_reinv *= (1 + nr/100)
    print(f"  {year:>6} | {nr:>+10.2f}% | {r:>+10.2f}% | {boost:>+8.2f}%")

print(f"  {'-'*50}")
print(f"  Capital final sans reinv : {cap_no_reinv:>12,.0f} EUR")
print(f"  Capital final avec reinv : {cap_reinv:>12,.0f} EUR")
print(f"  Ratio                    : x{cap_reinv/cap_no_reinv:.1f}")

# Simulation de croissance de la taille de position
print(f"\n" + "=" * 80)
print(f"SIMULATION : EVOLUTION DE LA TAILLE DE POSITION AVEC REINVESTISSEMENT")
print("=" * 80)

# Reconstituer la croissance du capital trimestre par trimestre
# Avec les donnees mensuelles du fichier Reinv
monthly_reinv = {
    (2022, 1): -5.02, (2022, 2): 9.70, (2022, 3): -5.63, (2022, 4): 37.57,
    (2022, 5): 22.25, (2022, 6): -13.00, (2022, 7): -1.76, (2022, 8): 11.95,
    (2022, 9): -5.79, (2022, 10): 1.70, (2022, 11): 8.35, (2022, 12): 2.05,
    (2023, 1): 24.41, (2023, 2): 6.52, (2023, 3): -1.19, (2023, 4): -10.00,
    (2023, 5): 2.34, (2023, 6): 6.27, (2023, 7): -7.83, (2023, 8): 23.51,
    (2023, 9): -8.51, (2023, 10): 17.07, (2023, 11): 5.35, (2023, 12): -4.61,
    (2024, 1): 3.20, (2024, 2): -2.85, (2024, 3): -1.01, (2024, 4): 9.02,
    (2024, 5): 9.66, (2024, 6): -4.86, (2024, 7): 25.63, (2024, 8): 5.82,
    (2024, 9): 15.66, (2024, 10): 20.20, (2024, 11): 13.31, (2024, 12): 24.45,
    (2025, 1): -1.33, (2025, 2): 23.34, (2025, 3): -5.95, (2025, 4): 2.82,
    (2025, 5): 1.01, (2025, 6): -16.11, (2025, 7): 0.92, (2025, 8): 11.72,
    (2025, 9): 7.98, (2025, 10): 10.60, (2025, 11): -1.71, (2025, 12): 18.28,
    (2026, 1): 9.02, (2026, 2): 24.78,
}

monthly_no_reinv = {
    (2022, 1): -2.16, (2022, 2): 4.93, (2022, 3): -2.46, (2022, 4): 16.08,
    (2022, 5): 9.02, (2022, 6): -5.22, (2022, 7): -0.55, (2022, 8): 4.93,
    (2022, 9): -2.23, (2022, 10): 0.79, (2022, 11): 3.41, (2022, 12): 1.05,
    (2023, 1): 8.48, (2023, 2): 2.31, (2023, 3): -0.28, (2023, 4): -3.48,
    (2023, 5): 1.02, (2023, 6): 2.34, (2023, 7): -2.70, (2023, 8): 7.68,
    (2023, 9): -2.75, (2023, 10): 5.48, (2023, 11): 1.77, (2023, 12): -1.44,
    (2024, 1): 1.17, (2024, 2): -0.84, (2024, 3): -0.19, (2024, 4): 3.09,
    (2024, 5): 2.95, (2024, 6): -1.42, (2024, 7): 7.23, (2024, 8): 1.89,
    (2024, 9): 4.17, (2024, 10): 5.06, (2024, 11): 3.31, (2024, 12): 5.55,
    (2025, 1): -0.18, (2025, 2): 5.09, (2025, 3): -1.30, (2025, 4): 0.82,
    (2025, 5): 0.31, (2025, 6): -3.82, (2025, 7): 0.26, (2025, 8): 2.71,
    (2025, 9): 1.88, (2025, 10): 2.42, (2025, 11): -0.33, (2025, 12): 3.82,
    (2026, 1): 1.90, (2026, 2): 4.73,
}

# Simuler la croissance
cap = 5300.0
stop_moyen = 130  # Estimation stop moyen
risque_pct = 2.2
pip_value = 1.0

print(f"\n  {'Mois':>10} | {'Capital':>12} | {'Risque EUR':>10} | {'Taille pos':>10} | {'Rendement':>10}")
print(f"  {'-'*65}")

for year in range(2022, 2027):
    for month in range(1, 13):
        if (year, month) not in monthly_reinv:
            continue
        r = monthly_reinv[(year, month)]
        risque_eur = cap * risque_pct / 100
        taille = round(max(0.01, risque_eur / (stop_moyen * pip_value)), 2)
        print(f"  {year}-{month:02d}    | {cap:>10,.0f} EUR | {risque_eur:>8,.0f} EUR | {taille:>10.2f} | {r:>+8.2f}%")
        cap *= (1 + r/100)

print(f"\n  Capital final simule : {cap:,.0f} EUR")

# ============================================================
# DIAGNOSTIC REINVESTISSEMENT
# ============================================================
print(f"\n" + "=" * 80)
print(f"DIAGNOSTIC : LE REINVESTISSEMENT EST-IL LENT ?")
print("=" * 80)

# Calculer les rendements cumules
cap_r = 5300.0
cap_nr = 5300.0
months_r = []
months_nr = []

for year in range(2018, 2027):
    for month in range(1, 13):
        if (year, month) in monthly_reinv:
            r = monthly_reinv[(year, month)]
            nr = monthly_no_reinv.get((year, month), 0)
            cap_r *= (1 + r/100)
            cap_nr *= (1 + nr/100)
            months_r.append((year, month, cap_r))
            months_nr.append((year, month, cap_nr))

if months_r:
    print(f"\n  Depuis jan 2022 :")
    print(f"  Capital SANS reinv : 5,300 -> {cap_nr:,.0f} EUR (x{cap_nr/5300:.1f})")
    print(f"  Capital AVEC reinv : 5,300 -> {cap_r:,.0f} EUR (x{cap_r/5300:.1f})")
    print(f"\n  Le reinvestissement a multiplie le capital par {cap_r/cap_nr:.1f}x de plus !")
    print(f"  Ce n'est PAS lent - le compositing fonctionne tres bien.")
    print(f"\n  La taille de position passe de ~1.0 a ~{round(cap_r * 0.022 / 130, 2)}")

# ============================================================
# ANALYSE STRUCTURELLE POUR OPTIMISATION
# ============================================================
print(f"\n" + "=" * 80)
print(f"PISTES D'OPTIMISATION (a tester dans PRT)")
print("=" * 80)

print(f"""
  CONSTAT depuis les donnees PRT :
  - La strategie est RENTABLE : PF 1.51, WR 67.9%
  - Le reinvestissement fonctionne : 5,300 -> 59,112 EUR en 3.5 ans (+1015%)
  - Max DD : -8,558 EUR (environ 14% du capital au moment du DD)

  POINTS D'ATTENTION :
  1. R/R ratio = 0.71 (gain moyen 262 EUR vs perte moy 367 EUR)
     -> Les pertes sont 40% plus grosses que les gains
     -> La strategie repose FORTEMENT sur un win rate eleve (67.9%)
     -> Si le WR baisse a ~59%, la strategie devient neutre

  2. MFE moyen = 315.80 EUR vs Gain moyen = 262.17 EUR
     -> Vous laissez 53.63 EUR sur la table en moyenne (17% du MFE)
     -> Le trailing stop / lock profit coupe peut-etre trop tot

  3. MAE moyen = -158.45 EUR vs Perte moy = -366.99 EUR
     -> Le MAE moyen est bien inferieur a la perte moyenne
     -> Certains trades plongent directement au stop

  OPTIMISATIONS SUGGEREES (sans reduire le nb de trades) :

  A) RELACHER LE SEUIL BREAKEVEN (CoeffBE)
     Actuellement : CoeffBE = 1.2 (BE a 1.2x ATR du prix d'entree)
     Test : CoeffBE = 1.5 a 2.0
     Pourquoi : Le trailing stop coupe des trades gagnants trop tot
     Le MFE moyen (315 EUR) >> Gain moyen (262 EUR) confirme ca
     Impact attendu : WR baisse legerement, mais gain moyen augmente
     => PF devrait augmenter

  B) AUGMENTER LE LOCK PROFIT (CoefLockProfit)
     Actuellement : 0.3 (verrouille 30% du target)
     Test : 0.4 a 0.5
     Pourquoi : Quand le lock se declenche, on ne capture que 30% du target
     Avec 50%, on securise plus de profit par trade gagnant

  C) AJUSTER LE TargetMult
     Actuellement : 2.2 (target = 2.2x le stop)
     Test : 2.5 a 3.0
     Pourquoi : Avec un WR de 67.9%, vous pouvez vous permettre
     un target plus eloigne (quelques trades en moins mais gains plus gros)
     La cle : le target est rarement atteint directement,
     donc l'augmenter n'eliminera pas de trades (la plupart sortent en EOD)

  D) FILTRER LA TAILLE DE L'OPR
     Si l'OPR est tres petit (< 20 pts), le breakout est souvent un faux signal
     Si l'OPR est tres grand (> 150 pts), le mouvement post-OPR est epuise
     Test : filtrer OPR entre 30 et 130 pts
     Impact : elimine les trades les moins fiables

  E) HEURE DE CLOTURE EOD
     Actuellement : 21h55
     Test : 20h55 ou 21h25
     Pourquoi : Les derniers trades de la journee (apres 20h)
     peuvent etre erratiques (faible volume US)

  F) OPTIMISATION DU REINVESTISSEMENT SPECIFIQUEMENT
     Actuellement : CapActuel = CapInit + StrategyProfit (lineaire)
     Alternatives a tester :
     1. Levier sur profits : CapActuel = CapInit + StrategyProfit * 1.3
        -> Accelere la croissance quand ca va bien
     2. Plafond de risque : ne jamais risquer plus de X% du capital actuel
     3. Reduction en drawdown : si StrategyProfit < 0, reduire encore plus
        -> CapActuel = CapInit + MAX(0, StrategyProfit)
        -> Protege pendant les mauvaises periodes
""")

print("=" * 80)
print("ANALYSE TERMINEE")
print("=" * 80)
