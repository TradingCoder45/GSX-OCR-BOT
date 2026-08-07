import MetaTrader5 as mt5

from config import SYMBOL, LOT, MAGIC, SLIPPAGE


class TradeManager:

    def __init__(self):

        if not mt5.initialize():
            raise RuntimeError(
                f"MT5 initialization failed: {mt5.last_error()}"
            )

        info = mt5.symbol_info(SYMBOL)

        if info is None:
            raise RuntimeError(f"Symbol '{SYMBOL}' not found.")

        if not info.visible:
            mt5.symbol_select(SYMBOL, True)

        self.symbol = SYMBOL

        print("Connected to MT5")

    def shutdown(self):
        mt5.shutdown()

    # --------------------------------------------------
    # Position helpers
    # --------------------------------------------------

    def get_position(self):

        positions = mt5.positions_get(symbol=self.symbol)

        if positions is None:
            return None

        if len(positions) == 0:
            return None

        return positions[0]

    def position_exists(self):

        return self.get_position() is not None

    def position_type(self):

        pos = self.get_position()

        if pos is None:
            return None

        if pos.type == mt5.POSITION_TYPE_BUY:
            return "BUY"

        return "SELL"

    # --------------------------------------------------
    # Open Trade
    # --------------------------------------------------

    def open_trade(self, signal):

        tick = mt5.symbol_info_tick(self.symbol)

        if tick is None:
            print("Couldn't get market price.")
            return False

        direction = signal["Signal"]

        if direction == "BUY":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": LOT,
            "type": order_type,
            "price": price,
            "sl": signal["StopLoss"],
            "tp": signal["TP1"],
            "deviation": SLIPPAGE,
            "magic": MAGIC,
            "comment": "OCR Trader",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:

            print(
                "Open failed:",
                result.retcode,
            )

            return False

        print(
            f"{direction} opened successfully."
        )

        return True

    # --------------------------------------------------
    # Close Trade
    # --------------------------------------------------

    def close_position(self):

        pos = self.get_position()

        if pos is None:
            return True

        tick = mt5.symbol_info_tick(self.symbol)

        if tick is None:
            return False

        if pos.type == mt5.POSITION_TYPE_BUY:

            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        else:

            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "position": pos.ticket,
            "volume": pos.volume,
            "type": order_type,
            "price": price,
            "deviation": SLIPPAGE,
            "magic": MAGIC,
            "comment": "Close by OCR",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:

            print(
                "Close failed:",
                result.retcode,
            )

            return False

        print("Position closed.")

        return True