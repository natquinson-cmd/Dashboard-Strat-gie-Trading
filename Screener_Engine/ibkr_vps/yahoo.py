# yahoo.py — source de donnees GRATUITE (Yahoo Finance non officiel) pour le screen large.
# Valide depuis un environnement serveur (crumb + screener + quoteSummary repondent).
# Tourne sur le VPS (IP normale), bien plus fiable que depuis une IP Cloudflare.
#
# Deux briques :
#   screen(operands)      -> liste de tickers filtres cote serveur (croissance/cap/region)
#   quote_summary(symbol) -> fondamentaux + prix (croissance CA/BPA, marges, ROE, MM50/200, 52s-haut, cap, volume, secteur)
import time
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

    # --- Cours "live" (dernier prix + variation du jour) pour le suivi des positions ---
    def live_quote(self, symbol):
        """Renvoie {price, changePct, exchange, ts} via la meta du chart. None si indispo."""
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
