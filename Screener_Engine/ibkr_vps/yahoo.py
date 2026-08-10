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
    def screen(self, operands, size=250, sort_field='intradaymarketcap', sort_type='desc', max_total=1000):
        self._ensure_crumb()
        out, offset = [], 0
        while offset < max_total:
            body = {
                'size': min(size, 250), 'offset': offset,
                'sortField': sort_field, 'sortType': sort_type,
                'quoteType': 'equity',
                'query': {'operator': 'and', 'operands': [
                    {'operator': op, 'operands': [field, val]} for (op, field, val) in operands]},
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
