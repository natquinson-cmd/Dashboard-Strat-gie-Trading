# yahoo.py — source de donnees GRATUITE (Yahoo Finance non officiel) pour le screen large.
# Valide depuis un environnement serveur (crumb + screener + quoteSummary repondent).
# Tourne sur le VPS (IP normale), bien plus fiable que depuis une IP Cloudflare.
#
# Deux briques :
#   screen(operands)      -> liste de tickers filtres cote serveur (croissance/cap/region)
#   quote_summary(symbol) -> fondamentaux + prix (croissance CA/BPA, marges, ROE, MM50/200, 52s-haut, cap, volume, secteur)
import time
import calendar
import datetime as _dt
import requests

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
BASE = 'https://query2.finance.yahoo.com'


class Yahoo:
    def __init__(self, pause=0.35, timeout=15):
        self.s = requests.Session()
        # NE PAS mettre Accept: application/json globalement : l'endpoint getcrumb renvoie
        # du texte brut et repond 406 "Not Acceptable" si on exige du JSON.
        self.s.headers.update({'User-Agent': UA})
        self.crumb = None
        self.pause = pause
        self.timeout = timeout

    def _ensure_crumb(self):
        if self.crumb:
            return
        last = ''
        hosts = ['https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com']
        for i in range(5):
            # session FRAICHE a chaque tentative : le getcrumb renvoie parfois un
            # JSON "Unauthorized" si le cookie A3 est stale -> on repart propre.
            self.s.cookies.clear()
            try:
                self.s.get('https://fc.yahoo.com/', timeout=self.timeout)
            except Exception:
                pass
            host = hosts[i % 2]
            try:
                c = self.s.get(f'{host}/v1/test/getcrumb', timeout=self.timeout).text.strip()
            except Exception:
                c = ''
            last = c
            # un crumb est un court jeton opaque : ni JSON ni HTML (le cookie A3 reste en session)
            if c and not c.startswith('{') and not c.startswith('<') and len(c) <= 60:
                self.crumb = c
                return
            time.sleep(1.5)
        raise RuntimeError(f'crumb Yahoo introuvable (blocage IP ou consent requis) repr={last[:40]!r}')

    def _get(self, url, retry=1):
        self._ensure_crumb()
        sep = '&' if '?' in url else '?'
        r = self.s.get(f'{url}{sep}crumb={self.crumb}', timeout=self.timeout)
        if r.status_code == 401 and retry:  # crumb expire -> renouvelle
            self.crumb = None
            return self._get(url, retry - 1)
        r.raise_for_status()
        return r.json()

    # --- Screener : filtres cote serveur, renvoie une liste de tickers ---
    def screen(self, operands, regions=None, size=250, sort_field='intradaymarketcap', sort_type='desc', max_total=1000):
        self._ensure_crumb()
        out, offset = [], 0
        and_ops = [{'operator': op, 'operands': [field, val]} for (op, field, val) in operands]
        if regions:  # OR sur plusieurs regions (ex US + Europe)
            and_ops.append({'operator': 'or', 'operands': [
                {'operator': 'eq', 'operands': ['region', r]} for r in regions]})
        while offset < max_total:
            body = {
                'size': min(size, 250), 'offset': offset,
                'sortField': sort_field, 'sortType': sort_type,
                'quoteType': 'equity',
                'query': {'operator': 'and', 'operands': and_ops},
                'userId': '', 'userIdType': 'guid',
            }
            r = self.s.post(f'{BASE}/v1/finance/screener?crumb={self.crumb}',
                            json=body, timeout=self.timeout)
            if r.status_code == 401:
                self.crumb = None; self._ensure_crumb(); continue
            r.raise_for_status()
            res = (r.json().get('finance') or {}).get('result')
            if not res:
                break
            page = res[0]
            quotes = page.get('quotes', [])
            for q in quotes:
                out.append({'symbol': q.get('symbol'), 'name': q.get('shortName'),
                            'marketCap': q.get('marketCap'),
                            'exchange': q.get('exchange') or q.get('fullExchangeName')})
            total = page.get('total') or 0
            offset += len(quotes)
            if not quotes or offset >= total:
                break
            time.sleep(self.pause)
        # dedupe par symbole
        seen, uniq = set(), []
        for q in out:
            s = q['symbol']
            if s and s not in seen:
                seen.add(s); uniq.append(q)
        return uniq

    # --- Fondamentaux + prix par ticker ---
    def quote_summary(self, symbol):
        mods = 'financialData,summaryDetail,price,assetProfile,defaultKeyStatistics'
        try:
            j = self._get(f'{BASE}/v10/finance/quoteSummary/{symbol}?modules={mods}')
        except Exception as e:
            return None
        res = (j.get('quoteSummary') or {}).get('result')
        if not res:
            return None
        r = res[0]
        fd, sd, pr = r.get('financialData', {}), r.get('summaryDetail', {}), r.get('price', {})
        ap, ks = r.get('assetProfile', {}), r.get('defaultKeyStatistics', {})
        g = lambda o, k: ((o.get(k) or {}) or {}).get('raw') if isinstance(o.get(k), dict) else o.get(k)
        return {
            'symbol': symbol,
            'name': (pr.get('longName') or pr.get('shortName')),
            'sector': ap.get('sector') or 'N/A',
            'exchange': pr.get('exchange'),   # code Yahoo (NMS, NYQ, ASE...) pour construire l'URL TradingView
            'price': g(fd, 'currentPrice') or g(pr, 'regularMarketPrice'),
            'marketCap': g(pr, 'marketCap') or g(sd, 'marketCap'),
            'avgVolume': g(sd, 'averageVolume') or g(sd, 'averageVolume10days'),
            'revenueGrowthYoY': g(fd, 'revenueGrowth'),
            'epsGrowthYoY': g(fd, 'earningsGrowth'),
            'grossMargin': g(fd, 'grossMargins'),
            'operatingMargin': g(fd, 'operatingMargins'),
            'roe': g(fd, 'returnOnEquity'),
            'eps': g(ks, 'trailingEps'),
            'priceAvg50': g(sd, 'fiftyDayAverage'),
            'priceAvg200': g(sd, 'twoHundredDayAverage'),
            'yearHigh': g(sd, 'fiftyTwoWeekHigh'),
        }

    def enrich(self, symbols, limit=None, log=True):
        recs = []
        syms = symbols[:limit] if limit else symbols
        for i, sym in enumerate(syms):
            r = self.quote_summary(sym)
            if r and r.get('price') is not None:
                recs.append(r)
            if log and (i + 1) % 25 == 0:
                print(f'  ...enrichi {i + 1}/{len(syms)}')
            time.sleep(self.pause)
        return recs

    # --- Mode QUALITE-VALORISATION : fondamentaux qualite + valorisation par ticker ---
    def quote_quality(self, symbol):
        mods = 'financialData,defaultKeyStatistics,summaryDetail,price,assetProfile,earnings'
        try:
            j = self._get(f'{BASE}/v10/finance/quoteSummary/{symbol}?modules={mods}')
        except Exception:
            return None
        res = (j.get('quoteSummary') or {}).get('result')
        if not res:
            return None
        r = res[0]
        fd, sd, pr = r.get('financialData', {}), r.get('summaryDetail', {}), r.get('price', {})
        ks, ap, ea = r.get('defaultKeyStatistics', {}), r.get('assetProfile', {}), r.get('earnings', {})
        g = lambda o, k: ((o.get(k) or {}) or {}).get('raw') if isinstance(o.get(k), dict) else o.get(k)
        # CAGR des BENEFICES (resultat net annuel) via earnings.financialsChart.yearly (~4 ans)
        earnings_cagr = None
        try:
            yearly = (ea.get('financialsChart') or {}).get('yearly') or []
            vals = [y['earnings']['raw'] for y in yearly if y.get('earnings') and y['earnings'].get('raw') is not None]
            if len(vals) >= 2 and vals[0] > 0 and vals[-1] > 0:
                earnings_cagr = (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
        except Exception:
            pass
        mc = g(pr, 'marketCap') or g(sd, 'marketCap')
        fcf = g(fd, 'freeCashflow')
        ebitda, debt, cash = g(fd, 'ebitda'), g(fd, 'totalDebt'), g(fd, 'totalCash')
        nd_ebitda = ((debt - (cash or 0)) / ebitda) if (ebitda and ebitda > 0 and debt is not None) else None
        return {
            'symbol': symbol, 'name': pr.get('longName') or pr.get('shortName'),
            'sector': ap.get('sector') or 'N/A', 'exchange': pr.get('exchange'),
            'price': g(fd, 'currentPrice') or g(pr, 'regularMarketPrice'), 'marketCap': mc,
            'roe': g(fd, 'returnOnEquity'), 'roa': g(fd, 'returnOnAssets'),   # roa = proxy du ROIC (DK)
            'grossMargin': g(fd, 'grossMargins'),
            'operatingMargin': g(fd, 'operatingMargins'), 'netMargin': g(fd, 'profitMargins'),
            'revenueGrowthYoY': g(fd, 'revenueGrowth'),
            'earningsGrowthYoY': g(fd, 'earningsGrowth'), 'earningsCAGR': earnings_cagr,
            'freeCashflow': fcf, 'fcfYield': (fcf / mc) if (fcf is not None and mc) else None,
            'netDebtToEbitda': nd_ebitda,
            'peg': g(ks, 'pegRatio') or g(ks, 'trailingPegRatio'),
            'trailingPE': g(sd, 'trailingPE'), 'forwardPE': g(sd, 'forwardPE'),
            'dividendYield': g(sd, 'dividendYield'), 'payoutRatio': g(sd, 'payoutRatio'),
            'website': ap.get('website'),   # pour le logo de repli (favicon du domaine)
            'country': ap.get('country'),   # pays du siege (pour la repartition geographique)
        }

    def price_cagr(self, symbol, years=5):
        try:
            j = self._get(f'{BASE}/v8/finance/chart/{symbol}?range={years}y&interval=1mo')
            res = (j.get('chart') or {}).get('result')
            closes = [c for c in res[0]['indicators']['quote'][0]['close'] if c] if res else []
            if len(closes) < 2 or closes[0] <= 0:
                return None
            return (closes[-1] / closes[0]) ** (1 / years) - 1
        except Exception:
            return None

    # --- Mini-serie de cours pour la sparkline du dashboard + variation du jour ---
    def spark(self, symbol, rng='3mo', interval='1d', max_points=30):
        """Renvoie {closes:[...], price, changePct} : serie journaliere ~3 mois (echantillonnee)
        et variation du dernier jour (dernier close vs precedent). None si indisponible."""
        try:
            j = self._get(f'{BASE}/v8/finance/chart/{symbol}?range={rng}&interval={interval}')
            res = (j.get('chart') or {}).get('result')
            if not res:
                return None
            r0 = res[0]
            meta = r0.get('meta') or {}
            q = (r0.get('indicators', {}).get('quote') or [{}])[0]
            closes = [c for c in (q.get('close') or []) if isinstance(c, (int, float))]
            if len(closes) < 2:
                return None
            # PIEGE : la derniere cloture de la serie chart est souvent None (cloture du jour pas
            # encore ecrite) et le filtre la retire -> on comparait alors J-1 vs J-2 (faux).
            # On se fie a meta.regularMarketPrice (prix reel de la derniere seance) pour le prix
            # courant, et on reconstruit la veille = derniere cloture ecrite dans la serie.
            rmp = meta.get('regularMarketPrice')
            if isinstance(rmp, (int, float)) and rmp > 0:
                price = rmp
                if abs(closes[-1] - rmp) / rmp < 1e-4:
                    prev = closes[-2]           # seance deja ecrite -> veille = avant-derniere
                else:
                    prev = closes[-1]           # serie s'arrete la veille -> rmp = derniere seance
                    closes = closes + [rmp]     # prolonge la sparkline jusqu'au prix courant
            else:
                price = closes[-1]
                prev = closes[-2]
            change_pct = ((price - prev) / prev) if prev else None
            # echantillonne a max_points en gardant toujours le tout dernier point
            if len(closes) > max_points:
                step = (len(closes) - 1) / (max_points - 1)
                closes = [closes[min(len(closes) - 1, round(i * step))] for i in range(max_points)]
                closes[-1] = price
            return {'closes': [round(c, 4) for c in closes], 'price': price, 'changePct': change_pct}
        except Exception:
            return None

    # Nom d'echange verbeux (module price) -> code court attendu par EXCH_CCY (comme le chart). Non liste = USD par defaut.
    _PRICE_EXCH = {
        'NasdaqGS': 'NMS', 'NasdaqGM': 'NGM', 'NasdaqCM': 'NCM', 'NASDAQ': 'NMS', 'NMS': 'NMS',
        'NYSE': 'NYQ', 'NYSEArca': 'PCX', 'NYSE Arca': 'PCX', 'NYSEAmerican': 'ASE', 'NYSE American': 'ASE',
        'AMEX': 'ASE', 'BATS': 'BATS', 'Cboe BZX': 'BATS', 'Cboe US': 'BATS',
        'XETRA': 'GER', 'Frankfurt': 'FRA', 'Amsterdam': 'AMS', 'Euronext Amsterdam': 'AMS',
        'Paris': 'PAR', 'Euronext Paris': 'PAR', 'Milan': 'MIL', 'Borsa Italiana': 'MIL',
        'Swiss': 'EBS', 'London': 'LSE', 'LSE': 'LSE', 'Madrid': 'MCE', 'Stockholm': 'STO',
        'Copenhagen': 'CPH', 'Helsinki': 'HEL', 'Vienna': 'VIE', 'Brussels': 'BRU', 'Lisbon': 'LIS',
    }

    # --- Cours "live" (dernier prix + variation du jour) pour le suivi des positions ---
    def live_quote(self, symbol):
        """Renvoie {price, changePct, exchange, quoteType, ts}. Prix PRE/POST-marche inclus (module price)
        pour coller a ce qu'affiche un courtier hors seance (ex Revolut) ; repli sur le chart si indispo."""
        try:
            j = self._get(f'{BASE}/v10/finance/quoteSummary/{symbol}?modules=price')
            pm = ((j.get('quoteSummary') or {}).get('result') or [{}])[0].get('price') or {}

            def raw(k):
                v = pm.get(k)
                return v.get('raw') if isinstance(v, dict) else v
            reg = raw('regularMarketPrice')
            if reg is not None:
                state = (pm.get('marketState') or '').upper()
                rpc = raw('regularMarketPreviousClose')
                pre, post = raw('preMarketPrice'), raw('postMarketPrice')
                # Variation TOUJOURS relative a la cloture pertinente selon la phase de marche.
                # Bug corrige : hors seance (nuit / week-end), l'ancien code affichait
                # `regularMarketChangePercent` = la variation de la DERNIERE SEANCE REGULIERE, qui apres minuit
                # devient "celle d'hier" (ex NVDA +8,7% = seance du 27 affichee le 28). On ne l'affiche plus.
                if state.startswith('PRE') and pre is not None:
                    price = pre; chg = raw('preMarketChangePercent')
                    if chg is None and reg: chg = pre / reg - 1                 # overnight = pre-marche vs derniere cloture
                elif state.startswith('POST') and post is not None:
                    price = post; chg = raw('postMarketChangePercent')
                    if chg is None and reg: chg = post / reg - 1                # after-hours vs cloture du jour
                elif state == 'REGULAR':
                    price = reg; chg = raw('regularMarketChangePercent')
                    if chg is None and rpc: chg = reg / rpc - 1                 # seance en cours vs veille
                else:
                    # Marche FERME : on garde le dernier prix hors-seance s'il existe (variation reelle overnight/
                    # after-hours), sinon on fige a la cloture SANS afficher la variation de la veille (chg=None -> "–").
                    if post is not None:
                        price = post; chg = raw('postMarketChangePercent')
                        if chg is None and reg: chg = post / reg - 1
                    elif pre is not None:
                        price = pre; chg = raw('preMarketChangePercent')
                        if chg is None and reg: chg = pre / reg - 1
                    else:
                        price = reg; chg = None                                 # fige a la cloture, pas de fausse "var. jour"
                exch = self._PRICE_EXCH.get(pm.get('exchangeName'), pm.get('exchangeName'))
                return {'price': price, 'changePct': chg, 'exchange': exch, 'marketState': state,
                        'quoteType': pm.get('quoteType'), 'ts': raw('regularMarketTime')}
        except Exception:
            pass
        # Repli : meta du chart (regularMarketPrice seul, pas de pre/post)
        try:
            j = self._get(f'{BASE}/v8/finance/chart/{symbol}?range=1d&interval=1d')
            meta = ((j.get('chart') or {}).get('result') or [{}])[0].get('meta') or {}
            price = meta.get('regularMarketPrice')
            prev = meta.get('chartPreviousClose') or meta.get('previousClose')
            chg = ((price - prev) / prev) if (isinstance(price, (int, float)) and isinstance(prev, (int, float)) and prev) else None
            return {'price': price, 'changePct': chg, 'exchange': meta.get('exchangeName'),
                    'quoteType': meta.get('instrumentType'), 'ts': meta.get('regularMarketTime')}
        except Exception:
            return None

    # --- Croissance du dividende (methode Dividend King) : historique via chart events=div ---
    def dividend_growth(self, symbol, years=15):
        """Renvoie {divStreak, divCagr, divGrowing, divYears} : annees consecutives de hausse du
        dividende annuel + CAGR du dividende. None si pas de dividende / historique insuffisant."""
        try:
            from datetime import datetime, timezone
            j = self._get(f'{BASE}/v8/finance/chart/{symbol}?range={years}y&interval=1mo&events=div')
            res = (j.get('chart') or {}).get('result')
            if not res:
                return None
            evs = ((res[0].get('events') or {}).get('dividends') or {})
            if not evs:
                return None
            by_year = {}
            for v in evs.values():
                ts, amt = v.get('date'), v.get('amount')
                if ts is None or amt is None:
                    continue
                y = datetime.fromtimestamp(ts, timezone.utc).year
                by_year[y] = by_year.get(y, 0) + amt
            cur = datetime.now(timezone.utc).year
            full = [y for y in sorted(by_year) if y < cur]   # on ignore l'annee courante (incomplete)
            if len(full) < 3:
                return None
            vals = [by_year[y] for y in full]
            streak = 0
            for i in range(len(vals) - 1, 0, -1):
                if vals[i] > vals[i - 1] * 1.001:            # hausse (petite tolerance)
                    streak += 1
                else:
                    break
            cagr = ((vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1) if (vals[0] > 0 and vals[-1] > 0) else None
            return {'divStreak': streak, 'divCagr': cagr, 'divGrowing': streak >= 3, 'divYears': len(full)}
        except Exception:
            return None

    # --- Croissance REGULIERE (methode DK) : CAGR annualise du CA et du FCF + rachats d'actions ---
    def fundamentals_history(self, symbol):
        """Via l'historique annuel (fundamentals-timeseries, ~4-5 ans) :
          - revCagr  : croissance annualisee du chiffre d'affaires (critere DK : reguliere >= 10 %/an)
          - fcfCagr  : croissance annualisee du free cash-flow
          - sharesChange / buyback : variation du nombre d'actions (baisse = rachats reguliers, DK)
          - roic / roicApprox : rendement du capital investi (ratio n°1 DK) = EBIT*(1-impot)/capital investi
        None si l'historique est indisponible."""
        try:
            types = ('annualTotalRevenue,annualFreeCashFlow,annualDilutedAverageShares,'
                     'annualEBIT,trailingEBIT,annualTaxRateForCalcs,trailingTaxRateForCalcs,'
                     'annualInvestedCapital,annualTotalDebt,annualStockholdersEquity,'
                     'annualCashAndCashEquivalents,annualNetIncome')
            url = (f'{BASE}/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}'
                   f'?symbol={symbol}&type={types}&period1=1104537600&period2=1893456000')
            j = self._get(url)
            res = (j.get('timeseries') or {}).get('result') or []
            series, dated = {}, {}
            for r in res:
                for k, v in r.items():
                    if k in ('meta', 'timestamp') or not isinstance(v, list):
                        continue
                    vals = [(a.get('asOfDate'), a['reportedValue'].get('raw')) for a in v
                            if a and a.get('reportedValue') and a['reportedValue'].get('raw') is not None]
                    if vals:
                        vals.sort(key=lambda x: x[0] or '')      # chronologique : [0]=plus ancien, [-1]=recent
                        series[k] = [val for _, val in vals]
                        if k in ('annualNetIncome', 'annualDilutedAverageShares'):
                            dated[k] = vals                      # on garde les dates pour le P/E moyen historique

            def last(key):
                s = series.get(key)
                return s[-1] if s else None

            def cagr(vals):
                if not vals or len(vals) < 2 or vals[0] is None or vals[-1] is None or vals[0] <= 0 or vals[-1] <= 0:
                    return None
                return (vals[-1] / vals[0]) ** (1.0 / (len(vals) - 1)) - 1

            out = {}
            rev = series.get('annualTotalRevenue')
            if rev:
                rc = cagr(rev)
                if rc is not None:
                    out['revCagr'] = round(rc, 4)
                    out['revYears'] = len(rev)
            fcf = series.get('annualFreeCashFlow')
            if fcf:
                fc = cagr(fcf)
                if fc is not None:
                    out['fcfCagr'] = round(fc, 4)
            sh = series.get('annualDilutedAverageShares')
            if sh and sh[0] and sh[-1] and sh[0] > 0:
                chg = sh[-1] / sh[0] - 1
                out['sharesChange'] = round(chg, 4)
                out['buyback'] = chg < -0.005                    # baisse nette du nb d'actions = rachats
            # ROIC = NOPAT / capital investi = EBIT*(1-impot) / capital investi (ratio n°1 DK).
            # Repli sur le resultat net si l'EBIT manque (typiquement les financieres) -> marque approx.
            ebit = last('trailingEBIT') or last('annualEBIT')
            tax = last('trailingTaxRateForCalcs')
            if tax is None:
                tax = last('annualTaxRateForCalcs')
            if tax is None or not (0 <= tax < 0.6):
                tax = 0.21
            ic = last('annualInvestedCapital')
            if not ic or ic <= 0:
                ic = (last('annualTotalDebt') or 0) + (last('annualStockholdersEquity') or 0) - (last('annualCashAndCashEquivalents') or 0)
            if ic and ic > 0:
                if ebit:
                    out['roic'] = round(ebit * (1 - tax) / ic, 4)
                    out['roicApprox'] = False
                else:
                    ni = last('annualNetIncome')
                    if ni:
                        out['roic'] = round(ni / ic, 4)          # EBIT indispo (ex financieres) -> approx
                        out['roicApprox'] = True
            # P/E MOYEN historique (multiple de sortie du DCF facon Stock Unlock) : pour chaque exercice,
            # BPA = resultat net / actions diluees, cours = cloture mensuelle a la date de cloture d'exercice,
            # P/E = cours / BPA -> moyenne sur les annees dispo. Yahoo ne donne que ~4 ans (pas de fenetre 8-10 ans).
            try:
                ni_d = dated.get('annualNetIncome') or []
                sh_map = {d: v for d, v in (dated.get('annualDilutedAverageShares') or [])}
                if ni_d and sh_map:
                    jc = self._get(f'{BASE}/v8/finance/chart/{symbol}?range=6y&interval=1mo')
                    r0 = ((jc.get('chart') or {}).get('result') or [{}])[0]
                    ts = r0.get('timestamp') or []
                    cl = ((r0.get('indicators') or {}).get('quote') or [{}])[0].get('close') or []
                    px = [(t, c) for t, c in zip(ts, cl)
                          if isinstance(t, int) and isinstance(c, (int, float)) and c > 0]

                    def price_at(datestr):
                        if not datestr or not px:
                            return None
                        try:
                            target = calendar.timegm(_dt.datetime.strptime(datestr[:10], '%Y-%m-%d').timetuple())
                        except Exception:
                            return None
                        best = min(px, key=lambda tc: abs(tc[0] - target))
                        return best[1] if abs(best[0] - target) <= 70 * 86400 else None   # cloture mensuelle a < ~70 j

                    pes = []
                    for d, ni in ni_d:
                        sh = sh_map.get(d)
                        if not sh or sh <= 0 or ni is None or ni <= 0:
                            continue
                        eps = ni / sh
                        p = price_at(d)
                        if p and eps > 0:
                            pe = p / eps
                            if 0 < pe < 200:                 # ecarte les P/E absurdes (BPA quasi nul)
                                pes.append(pe)
                    if len(pes) >= 2:
                        avg = sum(pes) / len(pes)
                        # garde anti-bug de DEVISE : pour un ADR, le benefice est en monnaie locale (TWD, CNY...)
                        # alors que le cours est en USD -> P/E aberrant (< 3). On ne garde qu'un P/E moyen plausible.
                        if 3.0 <= avg <= 150.0:
                            out['avgPe'] = round(avg, 2)
                            out['avgPeYears'] = len(pes)
            except Exception:
                pass
            return out or None
        except Exception:
            return None

    def analyst_growth(self, symbol):
        """Croissance ANALYSTE prospective pour piloter le DCF : croissance du CHIFFRE D'AFFAIRES estimee
        (module earningsTrend, periode +1y sinon 0y). On prend le CA et pas le BPA : les estimations de BPA
        a 1 an sont bruitees par des effets de base (ex GOOGL -28 %, AMZN -17 %) alors que le CA est propre et
        fiable. Yahoo ne fournit plus l'estimation de croissance a 5 ans (+5y = None). None si indisponible."""
        try:
            j = self._get(f'{BASE}/v10/finance/quoteSummary/{symbol}?modules=earningsTrend')
            trend = ((j.get('quoteSummary') or {}).get('result') or [{}])[0].get('earningsTrend') or {}
            by_period = {}
            for t in (trend.get('trend') or []):
                re_est = t.get('revenueEstimate') or {}
                g = re_est.get('growth')
                gv = g.get('raw') if isinstance(g, dict) else g
                if isinstance(gv, (int, float)):
                    by_period[t.get('period')] = gv
            for p in ('+1y', '0y'):
                if p in by_period and -0.5 <= by_period[p] <= 3.0:   # garde-fou : ecarte les valeurs absurdes
                    return round(by_period[p], 4)
            return None
        except Exception:
            return None
