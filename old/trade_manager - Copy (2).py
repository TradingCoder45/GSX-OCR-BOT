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

    def get_positions(self):

        positions = mt5.positions_get(symbol=self.symbol)

        if positions is None:
            return []

        return list(positions)

    def position_exists(self):

        return len(self.get_positions()) > 0

    def position_type(self):

        positions = self.get_positions()

        if not positions:
            return None

        if positions[0].type == mt5.POSITION_TYPE_BUY:
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

        # Four take profits
        tps = [
            signal["TP1"],
            signal["TP2"],
            signal["TP3"],
            signal["TP4"],
        ]

        symbol_info = mt5.symbol_info(self.symbol)

        lot = LOT / len(tps)

        # Round to broker volume step
        if symbol_info is not None:
            step = symbol_info.volume_step
            lot = round(lot / step) * step

            # Prevent volume below minimum
            if lot < symbol_info.volume_min:
                lot = symbol_info.volume_min

        success = True

        for i, tp in enumerate(tps, start=1):

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot,
                "type": order_type,
                "price": price,
                "sl": signal["StopLoss"],
                "tp": tp,
                "deviation": SLIPPAGE,
                "magic": MAGIC,
                "comment": f"OCR TP{i}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:

                print(
                    f"TP{i} open failed:",
                    result.retcode,
                )

                success = False

            else:

                print(
                    f"{direction} TP{i} opened successfully."
                )

        return success

    # --------------------------------------------------
    # Close All Positions
    # --------------------------------------------------

    def close_position(self):

        positions = self.get_positions()

        if not positions:
            return True

        tick = mt5.symbol_info_tick(self.symbol)

        if tick is None:
            print("Couldn't get market price.")
            return False

        success = True

        for pos in positions:

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
                    f"Close failed ({pos.ticket}):",
                    result.retcode,
                )

                success = False

            else:

                print(
                    f"Position {pos.ticket} closed."
                )

        return success