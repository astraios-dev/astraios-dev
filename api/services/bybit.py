import asyncio
from pybit.unified_trading import HTTP
from api.config import settings


def _client() -> HTTP:
    client = HTTP(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
    )
    if settings.bybit_proxy:
        client.client.proxies = {
            "http": settings.bybit_proxy,
            "https": settings.bybit_proxy,
        }
    return client


def _call(fn, **kwargs):
    resp = fn(**kwargs)
    if resp.get("retCode") != 0:
        raise RuntimeError(resp.get("retMsg", "Bybit API error"))
    return resp["result"]


async def get_positions(symbol: str | None = None) -> list[dict]:
    def _run():
        params = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = symbol
        result = _call(_client().get_positions, **params)
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
        result = _call(_client().place_order, **params)
        return {
            "order_id": result.get("orderId", ""),
            "order_link_id": result.get("orderLinkId", ""),
        }

    return await asyncio.to_thread(_run)


async def close_position(symbol: str, side: str, qty: str) -> dict:
    close_side = "Sell" if side == "Buy" else "Buy"
    return await place_order(symbol=symbol, side=close_side, qty=qty)


async def get_open_orders(symbol: str | None = None) -> list[dict]:
    def _run():
        params = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = symbol
        result = _call(_client().get_open_orders, **params)
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


async def get_wallet_balance() -> dict:
    def _run():
        result = _call(_client().get_wallet_balance, accountType="UNIFIED")
        acct = result.get("list", [{}])[0]
        return {
            "equity": acct.get("totalEquity", "0"),
            "available_balance": acct.get("totalAvailableBalance", "0"),
            "wallet_balance": acct.get("totalWalletBalance", "0"),
            "unrealised_pnl": acct.get("totalPerpUPL", "0"),
            "margin_used": acct.get("totalInitialMargin", "0"),
        }

    return await asyncio.to_thread(_run)


async def set_leverage(symbol: str, leverage: str) -> dict:
    def _run():
        result = _call(
            _client().set_leverage,
            category="linear",
            symbol=symbol,
            buyLeverage=leverage,
            sellLeverage=leverage,
        )
        return {"status": "ok"}

    return await asyncio.to_thread(_run)
