# =====================================================================
# GOLD FEAR STRATEGY — QuantConnect Algorithm
# =====================================================================
# Stratégie basée sur des signaux de peur "monde réel" qui PRÉCÈDENT
# les mouvements de l'or, sans indicateurs techniques retardés.
#
# Signaux utilisés (tous gratuits sur QuantConnect) :
#   1. VIX (via VIXY ETF) — spike de peur → or monte après
#   2. Dollar US (UUP ETF) — dollar faiblit → or monte après
#   3. Taux réels (TIP vs IEF) — taux réels baissent → or monte après
#   4. Credit spreads (HYG vs LQD) — spreads s'élargissent → peur → or
#   5. US Treasury Yield Curve — inversion = récession = peur = or
#
# Actif tradé : GLD (SPDR Gold Shares ETF)
# =====================================================================

from AlgorithmImports import *
import numpy as np


class GoldFearStrategy(QCAlgorithm):

    def initialize(self):
        # ----- Configuration -----
        self.set_start_date(2016, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(100_000)

        # ----- Assets (tous gratuits sur QC) -----
        self.gld  = self.add_equity("GLD",  Resolution.DAILY).symbol  # Or
        self.vixy = self.add_equity("VIXY", Resolution.DAILY).symbol  # VIX proxy
        self.uup  = self.add_equity("UUP",  Resolution.DAILY).symbol  # Dollar US
        self.tip  = self.add_equity("TIP",  Resolution.DAILY).symbol  # TIPS (inflation-protected)
        self.ief  = self.add_equity("IEF",  Resolution.DAILY).symbol  # 7-10Y Treasuries
        self.hyg  = self.add_equity("HYG",  Resolution.DAILY).symbol  # High Yield Corp Bonds
        self.lqd  = self.add_equity("LQD",  Resolution.DAILY).symbol  # Investment Grade Corp Bonds
        self.spy  = self.add_equity("SPY",  Resolution.DAILY).symbol  # S&P 500 (contexte)

        # ----- US Treasury Yield Curve (gratuit natif QC) -----
        self.yield_curve = self.add_data(
            USTreasuryYieldCurveRate, "USTYCR", Resolution.DAILY
        ).symbol

        # ----- Paramètres de la stratégie -----
        self.lookback           = 10   # Jours pour mesurer les variations
        self.vix_spike_thresh   = 0.15 # +15% de hausse du VIX sur N jours
        self.dollar_drop_thresh = -0.02 # -2% de baisse du dollar
        self.spread_widen_thresh = 0.03 # Élargissement des credit spreads
        self.real_rate_drop     = -0.01 # Baisse des taux réels

        # ----- Seuils du score composite -----
        self.entry_score   = 3   # Score minimum pour acheter (sur 5)
        self.exit_score    = 1   # Score en dessous duquel on vend

        # ----- Gestion du risque -----
        self.max_allocation = 0.90  # 90% max en GLD
        self.stop_loss_pct  = 0.07  # Stop-loss à -7%
        self.entry_price    = None

        # ----- Historiques -----
        self.window_size = self.lookback + 5
        self.history_ready = False

        # ----- Warm-up -----
        self.set_warm_up(timedelta(days=30))

        # ----- Schedule : évaluer chaque jour à 15h30 -----
        self.schedule.on(
            self.date_rules.every_day(self.gld),
            self.time_rules.before_market_close(self.gld, 30),
            self.evaluate_fear_signals
        )

    # =================================================================
    # SIGNAL 1 : VIX Spike (la peur monte-t-elle ?)
    # =================================================================
    def get_vix_signal(self):
        """
        Un spike du VIX PRÉCÈDE souvent un rally de l'or de 2-5 jours.
        On mesure la variation du VIXY sur N jours.
        Score : 1 si spike détecté, 0 sinon.
        """
        history = self.history(self.vixy, self.lookback + 1, Resolution.DAILY)
        if history.empty or len(history) < self.lookback + 1:
            return 0

        closes = history["close"].values
        change = (closes[-1] - closes[0]) / closes[0]

        if change > self.vix_spike_thresh:
            self.debug(f"  [VIX] Spike détecté: {change:.2%}")
            return 1
        return 0

    # =================================================================
    # SIGNAL 2 : Dollar Weakness (le dollar s'affaiblit-il ?)
    # =================================================================
    def get_dollar_signal(self):
        """
        Un dollar qui s'affaiblit PRÉCÈDE la montée de l'or.
        Corrélation inverse historique très forte (~ -0.80).
        Score : 1 si le dollar baisse significativement, 0 sinon.
        """
        history = self.history(self.uup, self.lookback + 1, Resolution.DAILY)
        if history.empty or len(history) < self.lookback + 1:
            return 0

        closes = history["close"].values
        change = (closes[-1] - closes[0]) / closes[0]

        if change < self.dollar_drop_thresh:
            self.debug(f"  [USD] Faiblesse détectée: {change:.2%}")
            return 1
        return 0

    # =================================================================
    # SIGNAL 3 : Taux Réels en baisse (TIP vs IEF)
    # =================================================================
    def get_real_rate_signal(self):
        """
        Les taux réels = rendement nominal - inflation anticipée.
        Proxy : ratio TIP/IEF. Quand TIP surperforme IEF,
        les anticipations d'inflation montent → taux réels baissent → or monte.
        Ce signal PRÉCÈDE l'or car les marchés obligataires réagissent plus vite.
        Score : 1 si taux réels en baisse, 0 sinon.
        """
        hist_tip = self.history(self.tip, self.lookback + 1, Resolution.DAILY)
        hist_ief = self.history(self.ief, self.lookback + 1, Resolution.DAILY)

        if hist_tip.empty or hist_ief.empty:
            return 0
        if len(hist_tip) < self.lookback + 1 or len(hist_ief) < self.lookback + 1:
            return 0

        tip_closes = hist_tip["close"].values
        ief_closes = hist_ief["close"].values

        # Ratio TIP/IEF : hausse = inflation anticipée monte = taux réels baissent
        ratio_now = tip_closes[-1] / ief_closes[-1]
        ratio_before = tip_closes[0] / ief_closes[0]
        change = (ratio_now - ratio_before) / ratio_before

        # On inverse : une hausse du ratio TIP/IEF signifie taux réels en baisse
        if change > abs(self.real_rate_drop):
            self.debug(f"  [TAUX RÉELS] Baisse détectée via TIP/IEF: {change:.2%}")
            return 1
        return 0

    # =================================================================
    # SIGNAL 4 : Credit Spreads (le marché du crédit a-t-il peur ?)
    # =================================================================
    def get_credit_spread_signal(self):
        """
        Credit spread = HYG (high yield) vs LQD (investment grade).
        Quand HYG sous-performe LQD, les spreads s'élargissent → PEUR.
        Ce signal PRÉCÈDE l'or : le marché du crédit réagit 1-3 jours
        avant les actifs refuges.
        Score : 1 si spreads s'élargissent, 0 sinon.
        """
        hist_hyg = self.history(self.hyg, self.lookback + 1, Resolution.DAILY)
        hist_lqd = self.history(self.lqd, self.lookback + 1, Resolution.DAILY)

        if hist_hyg.empty or hist_lqd.empty:
            return 0
        if len(hist_hyg) < self.lookback + 1 or len(hist_lqd) < self.lookback + 1:
            return 0

        hyg_closes = hist_hyg["close"].values
        lqd_closes = hist_lqd["close"].values

        # Ratio HYG/LQD : baisse = spreads s'élargissent = peur
        ratio_now = hyg_closes[-1] / lqd_closes[-1]
        ratio_before = hyg_closes[0] / lqd_closes[0]
        change = (ratio_now - ratio_before) / ratio_before

        if change < -self.spread_widen_thresh:
            self.debug(f"  [CREDIT] Spreads en hausse: {change:.2%}")
            return 1
        return 0

    # =================================================================
    # SIGNAL 5 : Yield Curve Inversion (récession en vue ?)
    # =================================================================
    def get_yield_curve_signal(self):
        """
        Courbe des taux inversée (10Y - 2Y < 0) = signal de récession.
        Historiquement, l'inversion PRÉCÈDE les crises de 6-18 mois,
        et l'or performe très bien dans ces périodes.
        Données gratuites natives sur QuantConnect.
        Score : 1 si courbe inversée ou proche de l'inversion, 0 sinon.
        """
        yc = self.securities[self.yield_curve]
        if yc is None or yc.price == 0:
            return 0

        yc_data = yc.get_data()
        if yc_data is None:
            return 0

        ten_year = getattr(yc_data, "ten_year", None)
        two_year = getattr(yc_data, "two_year", None)

        if ten_year is None or two_year is None:
            return 0

        spread = ten_year - two_year

        if spread < 0.25:  # Inversée ou proche de l'inversion
            self.debug(f"  [YIELD CURVE] Spread 10Y-2Y: {spread:.3f}%")
            return 1
        return 0

    # =================================================================
    # SCORE COMPOSITE DE PEUR
    # =================================================================
    def compute_fear_score(self):
        """
        Combine les 5 signaux en un score de 0 à 5.
        Plus le score est élevé, plus la peur est forte → acheter de l'or.
        """
        s1 = self.get_vix_signal()
        s2 = self.get_dollar_signal()
        s3 = self.get_real_rate_signal()
        s4 = self.get_credit_spread_signal()
        s5 = self.get_yield_curve_signal()

        total = s1 + s2 + s3 + s4 + s5

        self.plot("Fear Score", "Score", total)
        self.plot("Fear Score", "Entry Threshold", self.entry_score)
        self.plot("Fear Score", "Exit Threshold", self.exit_score)

        return total

    # =================================================================
    # LOGIQUE DE TRADING
    # =================================================================
    def evaluate_fear_signals(self):
        """
        Appelé chaque jour à 15h30.
        Décision basée sur le score composite de peur.
        """
        if self.is_warming_up:
            return

        # Vérifier que tous les prix sont disponibles
        for symbol in [self.gld, self.vixy, self.uup, self.tip,
                       self.ief, self.hyg, self.lqd]:
            if not self.securities[symbol].has_data:
                return

        fear_score = self.compute_fear_score()
        is_invested = self.portfolio[self.gld].invested
        current_price = self.securities[self.gld].price

        self.debug(f"[{self.time}] Fear Score: {fear_score}/5 | Investi: {is_invested}")

        # ----- ENTRÉE : la peur est élevée → acheter de l'or -----
        if not is_invested and fear_score >= self.entry_score:
            # Allocation proportionnelle au score
            allocation = min(
                self.max_allocation,
                0.30 + (fear_score - self.entry_score) * 0.20
            )
            self.set_holdings(self.gld, allocation)
            self.entry_price = current_price
            self.log(f">>> ACHAT GLD @ {current_price:.2f} | "
                     f"Fear Score: {fear_score}/5 | Allocation: {allocation:.0%}")

        # ----- SORTIE : la peur retombe → vendre l'or -----
        elif is_invested:
            # Stop-loss
            if self.entry_price and current_price < self.entry_price * (1 - self.stop_loss_pct):
                self.liquidate(self.gld)
                pnl = (current_price - self.entry_price) / self.entry_price
                self.log(f"<<< STOP-LOSS GLD @ {current_price:.2f} | PnL: {pnl:.2%}")
                self.entry_price = None

            # Score trop bas → sortie
            elif fear_score <= self.exit_score:
                self.liquidate(self.gld)
                pnl = (current_price - self.entry_price) / self.entry_price if self.entry_price else 0
                self.log(f"<<< VENTE GLD @ {current_price:.2f} | "
                         f"Fear Score: {fear_score}/5 | PnL: {pnl:.2%}")
                self.entry_price = None

            # Score intermédiaire → ajuster la position
            elif fear_score >= self.entry_score:
                new_allocation = min(
                    self.max_allocation,
                    0.30 + (fear_score - self.entry_score) * 0.20
                )
                self.set_holdings(self.gld, new_allocation)

    # =================================================================
    # EVENT HANDLERS
    # =================================================================
    def on_order_event(self, order_event):
        if order_event.status == OrderStatus.FILLED:
            self.debug(f"Ordre exécuté: {order_event}")

    def on_end_of_algorithm(self):
        self.log("="*60)
        self.log("RÉSUMÉ FINAL")
        self.log(f"Capital final: ${self.portfolio.total_portfolio_value:,.2f}")
        self.log(f"Performance: {((self.portfolio.total_portfolio_value / 100_000) - 1) * 100:.2f}%")
        self.log("="*60)
