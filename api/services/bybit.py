import asyncio
from pybit.unified_trading import HTTP
from api.config import settings


def _client(api_key: str | None = None, api_secret: str | None = None, testnet: bool = False) -> HTTP:
    key = api_key or settings.bybit_api_key
    secret = api_secret or settings.bybit_api_secret
    client = HTTP(
        api_key=key if key else None,
        api_secret=secret if secret else None,
        testnet=testnet,
    )
    if settings.bybit_proxy:
        client.client.proxies = {
            "http": settings.bybit_proxy,
            "https": settings.bybit_proxy,
        }
    return client


def _auth_client(api_key: str | None = None, api_secret: str | None = None, testnet: bool = False) -> HTTP:
    key = api_key or settings.bybit_api_key
    secret = api_secret or settings.bybit_api_secret
    if not key or not secret:
        msg = "No Bybit testnet keys configured. Add them in Account settings." if testnet else "No Bybit API keys configured. Add them in Account settings."
        raise RuntimeError(msg)
    return _client(key, secret, testnet=testnet)


def _call(fn, **kwargs):
    resp = fn(**kwargs)
    if resp.get("retCode") != 0:
        raise RuntimeError(resp.get("retMsg", "Bybit API error"))
    return resp["result"]


async def get_positions(symbol: str | None = None, api_key: str | None = None, api_secret: str | None = None, testnet: bool = False) -> list[dict]:
    def _run():
        params = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = symbol
        result = _call(_auth_client(api_key, api_secret, testnet).get_positions, **params)
        positions = []
        for p in result.get("list", []):
            size = float(p.get("size", 0))
            if size == 0:
                continue
            entry = float(p.get("avgPrice", 0))
            mark = float(p.get("markPrice", 0))
            pnl = float(p.get("unrealisedPnl", 0))
            positions.append({
                "symbol": p["symbol"],
                "side": p["side"],
                "size": size,
                "entry_price": entry,
                "mark_price": mark,
                "unrealised_pnl": round(pnl, 4),
                "leverage": p.get("leverage", "0"),
                "liq_price": p.get("liqPrice", ""),
                "tp": p.get("takeProfit", ""),
                "sl": p.get("stopLoss", ""),
            })
        return positions

    return await asyncio.to_thread(_run)


async def place_order(
    symbol: str,
    side: str,
    qty: str,
    tp: str | None = None,
    sl: str | None = None,
    api_key: str | None = None,
    api_secret: str | None = None,
    testnet: bool = False,
) -> dict:
    def _run():
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": qty,
            "timeInForce": "GTC",
        }
        if tp:
            params["takeProfit"] = tp
        if sl:
            params["stopLoss"] = sl
        result = _call(_auth_client(api_key, api_secret, testnet).place_order, **params)
        return {
            "order_id": result.get("orderId", ""),
            "order_link_id": result.get("orderLinkId", ""),
        }

    return await asyncio.to_thread(_run)


async def close_position(symbol: str, side: str, qty: str, api_key: str | None = None, api_secret: str | None = None, testnet: bool = False) -> dict:
    close_side = "Sell" if side == "Buy" else "Buy"
    return await place_order(symbol=symbol, side=close_side, qty=qty, api_key=api_key, api_secret=api_secret, testnet=testnet)


async def get_open_orders(symbol: str | None = None, api_key: str | None = None, api_secret: str | None = None, testnet: bool = False) -> list[dict]:
    def _run():
        params = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = symbol
        result = _call(_auth_client(api_key, api_secret, testnet).get_open_orders, **params)
        orders = []
        for o in result.get("list", []):
            orders.append({
                "order_id": o["orderId"],
                "symbol": o["symbol"],
                "side": o["side"],
                "order_type": o["orderType"],
                "qty": o.get("qty", "0"),
                "price": o.get("price", "0"),
                "status": o.get("orderStatus", ""),
                "created_at": o.get("createdTime", ""),
            })
        return orders

    return await asyncio.to_thread(_run)


async def get_wallet_balance(api_key: str | None = None, api_secret: str | None = None, testnet: bool = False) -> dict:
    def _run():
        result = _call(_auth_client(api_key, api_secret, testnet).get_wallet_balance, accountType="UNIFIED")
        acct = result.get("list", [{}])[0]
        return {
            "equity": acct.get("totalEquity", "0"),
            "available_balance": acct.get("totalAvailableBalance", "0"),
            "wallet_balance": acct.get("totalWalletBalance", "0"),
            "unrealised_pnl": acct.get("totalPerpUPL", "0"),
            "margin_used": acct.get("totalInitialMargin", "0"),
        }

    return await asyncio.to_thread(_run)


async def get_symbols() -> list[dict]:
    def _run():
        result = _call(_client().get_tickers, category="linear")
        symbols = []
        for t in result.get("list", []):
            if not t["symbol"].endswith("USDT"):
                continue
            symbols.append({
                "symbol": t["symbol"],
                "last_price": t.get("lastPrice", "0"),
                "change_pct": t.get("price24hPcnt", "0"),
                "turnover_24h": float(t.get("turnover24h", 0)),
            })
        symbols.sort(key=lambda s: s["turnover_24h"], reverse=True)
        return symbols

    return await asyncio.to_thread(_run)


async def get_klines(symbol: str, interval: str = "60", limit: int = 200) -> list[dict]:
    def _run():
        client = _client()
        all_rows = []
        remaining = min(limit, 1000)
        end_time = None
        while remaining > 0:
            batch = min(remaining, 200)
            params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": batch}
            if end_time:
                params["end"] = end_time
            result = _call(client.get_kline, **params)
            rows = result.get("list", [])
            if not rows:
                break
            all_rows.extend(rows)
            end_time = int(rows[-1][0]) - 1
            remaining -= len(rows)
            if len(rows) < batch:
                break

        seen = set()
        candles = []
        for r in reversed(all_rows):
            ts = int(r[0]) // 1000
            if ts in seen:
                continue
            seen.add(ts)
            candles.append({
                "time": ts,
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
            })
        return candles

    return await asyncio.to_thread(_run)


async def set_leverage(symbol: str, leverage: str, api_key: str | None = None, api_secret: str | None = None, testnet: bool = False) -> dict:
    def _run():
        result = _call(
            _auth_client(api_key, api_secret, testnet).set_leverage,
            category="linear",
            symbol=symbol,
            buyLeverage=leverage,
            sellLeverage=leverage,
        )
        return {"status": "ok"}

    return await asyncio.to_thread(_run)
