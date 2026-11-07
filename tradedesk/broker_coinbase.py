"""Coinbase Financial Markets (US perp-style futures) adapter, through the official SDK
`coinbase-advanced-py` (pip install coinbase-advanced-py).

Keys come only from environment variables COINBASE_API_KEY and COINBASE_API_SECRET.
Create the CDP key with view and trade scopes only, never transfer.

Nothing here is called unless the desk is in live mode, and live mode needs all three:
rules.live_enabled (set in the app), TRADEDESK_LIVE=1 on the PC, and a strategy at stage
small_live or above. `python -m tradedesk check-live` only reads (balance, positions) and previews.
"""
import os
import uuid

ORDERS = "/api/v3/brokerage/orders"


class LiveDisabled(Exception):
    pass


def _client():
    key, secret = os.environ.get("COINBASE_API_KEY"), os.environ.get("COINBASE_API_SECRET")
    if not key or not secret:
        raise LiveDisabled("COINBASE_API_KEY / COINBASE_API_SECRET are not set in the environment")
    try:
        from coinbase.rest import RESTClient
    except ImportError:
        raise LiveDisabled("install the official SDK: pip install coinbase-advanced-py")
    return RESTClient(api_key=key, api_secret=secret)


def _d(resp):
    return resp.to_dict() if hasattr(resp, "to_dict") else resp


class CoinbaseCFM:
    def __init__(self, client=None):
        self.c = client or _client()

    # ---- read-only
    def balance(self):
        return _d(self.c.get_futures_balance_summary())

    def positions(self):
        return _d(self.c.list_futures_positions())

    def open_orders(self, product_id):
        return _d(self.c.list_orders(product_ids=[product_id], order_status=["OPEN"]))

    def _body(self, product_id, side, contracts, stop, target, leverage):
        return {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": "BUY" if side == 1 else "SELL",
            "order_configuration": {"market_market_ioc": {"base_size": str(int(contracts))}},
            "leverage": "%.2f" % leverage,
            "margin_type": "ISOLATED",
            # the stop (and a take-profit) rest on the exchange from the moment of entry
            "attached_order_configuration": {"trigger_bracket_gtc": {
                "limit_price": _px(target), "stop_trigger_price": _px(stop)}},
        }

    def preview(self, product_id, side, contracts, stop, target, leverage):
        """Validates an order with Coinbase without placing it."""
        b = self._body(product_id, side, contracts, stop, target, leverage)
        b.pop("client_order_id")
        return _d(self.c.post(ORDERS + "/preview", data=b))

    # ---- trading (live mode only)
    def enter(self, product_id, side, contracts, stop, target, leverage):
        return _d(self.c.post(ORDERS, data=self._body(product_id, side, contracts, stop, target, leverage)))

    def close(self, product_id, contracts):
        r = _d(self.c.close_position(client_order_id=str(uuid.uuid4()), product_id=product_id,
                                     size=str(int(contracts))))
        self.cancel_all(product_id)
        return r

    def cancel_all(self, product_id):
        ids = [o["order_id"] for o in self.open_orders(product_id).get("orders", [])]
        return _d(self.c.cancel_orders(order_ids=ids)) if ids else {"results": []}


def _px(x):
    return ("%.8f" % x).rstrip("0").rstrip(".")


def far_target(entry, stop, side, r=10.0):
    """Bracket orders need a take-profit price. Strategies that exit on a signal get a far one
    (10R) so the stop still rests on the exchange; the desk closes on the signal."""
    return entry + side * r * abs(entry - stop)
