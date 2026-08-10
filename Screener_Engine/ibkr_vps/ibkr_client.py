# ibkr_client.py — enveloppe fine autour de ib_async (fork maintenu d'ib_insync).
# Connexion en LECTURE SEULE par defaut (aucun passage d'ordre). Se branche a IB Gateway
# tournant en local sur le VPS (piloté par IBC). Aucune cle : hote/port depuis l'env.
#
# Ports par defaut : IB Gateway live=4001, paper=4002 ; TWS live=7496, paper=7497.

from momentum import compute_momentum

try:
    from ib_async import IB, Stock, ScannerSubscription
except Exception:  # pragma: no cover - dependance installee sur le VPS
    IB = Stock = ScannerSubscription = None


class IBKRClient:
    def __init__(self, host='127.0.0.1', port=4002, client_id=17, readonly=True, timeout=20):
        if IB is None:
            raise RuntimeError("ib_async non installe (pip install ib_async). Requis uniquement sur le VPS.")
        self.host, self.port, self.client_id = host, port, client_id
        self.readonly, self.timeout = readonly, timeout
        self.ib = IB()

    def connect(self):
        self.ib.connect(self.host, self.port, clientId=self.client_id, readonly=self.readonly, timeout=self.timeout)
        return self

    def disconnect(self):
        try:
            self.ib.disconnect()
        except Exception:
            pass

    def __enter__(self):
        return self.connect()

    def __exit__(self, *a):
        self.disconnect()

    # --- Positions / compte (source de verite live) ---
    def positions(self):
        out = []
        for p in self.ib.portfolio():
            c = p.contract
            out.append({
                'symbol': c.symbol,
                'secType': c.secType,
                'currency': c.currency,
                'position': p.position,
                'avgCost': p.averageCost,
                'marketPrice': p.marketPrice,
                'marketValue': p.marketValue,
                'unrealizedPnl': p.unrealizedPNL,
                'realizedPnl': p.realizedPNL,
            })
        return out

    def account_summary(self):
        vals = {}
        for v in self.ib.accountSummary():
            if v.tag in ('NetLiquidation', 'TotalCashValue', 'AvailableFunds', 'BuyingPower', 'GrossPositionValue'):
                vals[v.tag] = _f(v.value)
        return vals

    # --- Tradabilite ---
    def is_tradable(self, symbol):
        try:
            cds = self.ib.reqContractDetails(Stock(symbol, 'SMART', 'USD'))
            return bool(cds)
        except Exception:
            return False

    # --- Barres historiques -> momentum ---
    def momentum(self, symbol, duration='1 Y', bar_size='1 day'):
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            bars = self.ib.reqHistoricalData(
                contract, endDateTime='', durationStr=duration,
                barSizeSetting=bar_size, whatToShow='TRADES', useRTH=True, formatDate=1)
            if not bars:
                return None
            series = [{'close': b.close, 'high': b.high, 'low': b.low, 'volume': b.volume} for b in bars]
            return compute_momentum(series)
        except Exception as e:
            print(f'  [ibkr] momentum {symbol} echec: {e}')
            return None

    # --- Cours snapshot ---
    def snapshot(self, symbol):
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            t = self.ib.reqMktData(contract, '', snapshot=True, regulatorySnapshot=False)
            self.ib.sleep(2)
            price = t.marketPrice()
            return {'price': price if price == price else None,  # NaN check
                    'bid': _nan(t.bid), 'ask': _nan(t.ask), 'volume': _nan(t.volume)}
        except Exception:
            return None

    # --- Scanner de decouverte momentum ---
    def scanner(self, scan_code='TOP_PERC_GAIN', location='STK.US.MAJOR', number_of_rows=50,
                above_price=5, below_price=None, above_market_cap=None, above_volume=200000):
        try:
            sub = ScannerSubscription(
                instrument='STK', locationCode=location, scanCode=scan_code,
                numberOfRows=number_of_rows,
                abovePrice=above_price, belowPrice=below_price or 0,
                aboveVolume=above_volume, marketCapAbove=above_market_cap or 0)
            data = self.ib.reqScannerData(sub)
            return [d.contractDetails.contract.symbol for d in data if d.contractDetails and d.contractDetails.contract]
        except Exception as e:
            print(f'  [ibkr] scanner {scan_code} echec: {e}')
            return []


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def _nan(x):
    return x if isinstance(x, (int, float)) and x == x else None
