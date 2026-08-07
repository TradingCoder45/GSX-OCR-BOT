import MetaTrader5 as mt5
import time

from config import (
    SYMBOL,
    LOT,
    SLIPPAGE,
    MAGIC_ME,
    MAGIC_LIMIT,
)

from console import log


class TradeManager:

    def __init__(self):

        if not mt5.initialize():
            raise RuntimeError(
                f"MT5 initialization failed: {mt5.last_error()}"
            )

        info = mt5.symbol_info(SYMBOL)

        if info is None:
            raise RuntimeError(
                f"Symbol '{SYMBOL}' not found."
            )

        if not info.visible:
            mt5.symbol_select(SYMBOL, True)

        self.symbol = SYMBOL
        self.symbol_info = info
        
        # Orders waiting to be sent
        self.pending_execution = []

        # Current signal signature
        self.execution_signature = None
        
        # Already submitted for current signal
        self.submitted_me = set()
        self.submitted_limit = set()

        log("Connected to MT5")

    def shutdown(self):
        mt5.shutdown()
        
    # --------------------------------------------------
    # Reset execution state
    # --------------------------------------------------

    def reset_signal_tracking(self):

        log("RESETTING submitted sets")
        self.submitted_me.clear()
        self.submitted_limit.clear()

    # ==================================================
    # Positions
    # ==================================================

    def get_positions(self):

        positions = mt5.positions_get(symbol=self.symbol)

        if positions is None:
            return []

        return [
            p
            for p in positions
            if p.magic in (
                MAGIC_ME,
                MAGIC_LIMIT,
            )
        ]

    def position_exists(self):

        return len(self.get_positions()) > 0

    # ==================================================
    # Pending Orders
    # ==================================================

    def get_pending_orders(self):

        orders = mt5.orders_get(symbol=self.symbol)

        if orders is None:
            return []

        return [
            o
            for o in orders
            if o.magic in (
                MAGIC_ME,
                MAGIC_LIMIT,
            )
        ]

    def pending_exists(self):

        return len(self.get_pending_orders()) > 0

    def has_active_trade(self):

        return (
            self.position_exists()
            or
            self.pending_exists()
        )

    # ==================================================
    # Lot size
    # ==================================================

    def normalize_lot(self, lot):

        step = self.symbol_info.volume_step

        lot = round(lot / step) * step

        if lot < self.symbol_info.volume_min:
            lot = self.symbol_info.volume_min

        if lot > self.symbol_info.volume_max:
            lot = self.symbol_info.volume_max

        return lot
        
    # ==================================================
    # Execute ONE Market Order
    # ==================================================

    def place_market_order(
        self,
        signal,
        tp_index,
        tp,
    ):

        tick = mt5.symbol_info_tick(self.symbol)
        info = mt5.symbol_info(self.symbol)
        point = info.point
        min_distance = info.trade_stops_level * point
        SAFETY_POINTS = 20      # points
        safety = SAFETY_POINTS * point
        required_distance = min_distance + safety

        if tick is None:
            return False

        direction = signal["Signal"]

        lot = self.normalize_lot(LOT / 4)

        if direction == "BUY":
            price = tick.ask

            if price <= signal["StopLoss"]:
                return False
            
            # TP already reached?
            if (tp - price) < required_distance:
                # log(f"ME TP{tp_index} skipped (TP too close)")
                return "SKIPPED"
                
            order_type = mt5.ORDER_TYPE_BUY

        else:

            price = tick.bid

            if price >= signal["StopLoss"]:
                return False
                
            # TP already reached?
            if (price - tp) < required_distance:
                # log(f"ME TP{tp_index} skipped (TP too close)")
                return "SKIPPED"

            order_type = mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "deviation": SLIPPAGE,
            "magic": MAGIC_ME,
            "comment": f"ME TP{tp_index}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:

            log(f"ME TP{tp_index} failed ({result.retcode})")

            return False
        
        time.sleep(0.2)
        positions = self.get_positions()
        position = None

        for pos in positions:

            if pos.magic not in (MAGIC_ME, MAGIC_LIMIT):
                continue

            # Find the newest matching direction/volume.
            if pos.type == (
                mt5.POSITION_TYPE_BUY
                if direction == "BUY"
                else mt5.POSITION_TYPE_SELL
            ):
                position = pos

        if position is not None:

            self.move_sl(position.ticket, signal["StopLoss"])
            self.move_tp(position.ticket, tp)

        else:

            log(f"Couldn't locate ME TP{tp_index} to modify SL/TP.")

        # IMPORTANT:
        # The market order was already opened.
        return True
        
        
    # ==================================================
    # Execute ONE Limit Order
    # ==================================================

    def place_limit_order(
        self,
        signal,
        tp_index,
        tp,
    ):

        tick = mt5.symbol_info_tick(self.symbol)

        if tick is None:
            return False

        direction = signal["Signal"]
        entry = signal["Entry"]
        lot = self.normalize_lot(LOT / 4)
        info = mt5.symbol_info(self.symbol)
        point = info.point
        min_distance = info.trade_stops_level * point
        
        if direction == "BUY":

            current = tick.ask

            # Already below entry?
            # Don't place a limit anymore.
            if current <= entry:
                return False

            # Too close to entry?
            if (current - entry) < min_distance:
                return False

            order_type = mt5.ORDER_TYPE_BUY_LIMIT

        else:

            current = tick.bid

            if current >= entry:
                return False

            if (entry - current) < min_distance:
                return False

            order_type = mt5.ORDER_TYPE_SELL_LIMIT
            
        request = {

            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.symbol,
            "volume": lot,
            "type": order_type,
            "price": entry,
            "sl": signal["StopLoss"],
            "tp": tp,
            "magic": MAGIC_LIMIT,
            "comment": f"LIMIT TP{tp_index}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        
        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:

            if result.retcode != 10015:
                log(f"LIMIT TP{tp_index} failed ({result.retcode})")

            return False

        return True
        
    # ==================================================
    # Close All Positions
    # ==================================================

    def close_position(self):

        positions = self.get_positions()

        if not positions:
            return True

        tick = mt5.symbol_info_tick(self.symbol)

        if tick is None:
            log("Couldn't get market price.")
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
                "magic": pos.magic,
                "comment": "Close by OCR",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result.retcode == mt5.TRADE_RETCODE_DONE:

                log(
                    f"Closed position {pos.ticket}"
                )

            else:

                log(
                    f"Failed closing {pos.ticket}:",
                    result.retcode,
                )

                success = False

        return success

    # ==================================================
    # Cancel Pending Orders
    # ==================================================

    def cancel_pending_orders(self):

        orders = self.get_pending_orders()

        if not orders:
            return True

        success = True

        for order in orders:

            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order.ticket,
            }

            result = mt5.order_send(request)

            if result.retcode == mt5.TRADE_RETCODE_DONE:

                log(
                    f"Cancelled pending {order.ticket}"
                )

            else:

                log(
                    f"Failed cancelling {order.ticket}:",
                    result.retcode,
                )

                success = False

        return success

    # ==================================================
    # Clear Everything
    # ==================================================

    def clear_all_trades(self):

        ok1 = self.close_position()
        ok2 = self.cancel_pending_orders()

        return ok1 and ok2
        
    # --------------------------------------------------
    # Move Stop Loss
    # --------------------------------------------------

    def move_sl(self, ticket, new_sl):

        position = None

        for pos in self.get_positions():
            if pos.ticket == ticket:
                position = pos
                break

        if position is None:
            return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": new_sl,
            "tp": position.tp,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:

            log(
                f"Move SL failed ({ticket}) : {result.retcode}"
            )

            return False

        log(
            f"SL moved ({ticket}) -> {new_sl:.3f}"
        )

        return True
        
    # --------------------------------------------------
    # Move Take Profit
    # --------------------------------------------------        
    def move_tp(self, ticket, new_tp):

        position = None

        for pos in self.get_positions():

            if pos.ticket == ticket:

                position = pos
                break

        if position is None:
            return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": position.sl,
            "tp": new_tp,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:

            log(
                f"TP modify failed ({ticket})"
            )

            return False

        return True
        
    # --------------------------------------------------
    # Move TP3/TP4 to Break Even
    # --------------------------------------------------

    def move_remaining_to_be(self, signal):

        entry = signal["Entry"]

        moved = 0

        for pos in self.get_positions():

            comment = pos.comment.upper()

            if "TP3" not in comment and "TP4" not in comment:
                continue
                
            time.sleep(0.2)
            if self.move_sl(pos.ticket, entry):
                moved += 1

        log(f"Moved {moved} position(s) to Break Even.")

    # --------------------------------------------------
    # Move TP3/TP4 to Break Even
    # --------------------------------------------------
        
    def market_position_exists(self, tp_index):

        positions = self.get_positions()

        comment = f"ME TP{tp_index}"

        for pos in positions:

            if (
                pos.magic == MAGIC_ME
                and pos.comment == comment
            ):
                return True

        return False

    # --------------------------------------------------
    # 
    # --------------------------------------------------
    
    def limit_order_exists(self, tp_index):

        orders = mt5.orders_get(symbol=self.symbol)

        if orders is None:
            return False

        comment = f"LIMIT TP{tp_index}"

        for order in orders:

            if (
                order.magic == MAGIC_LIMIT
                and order.comment == comment
            ):
                return True

        return False

    # --------------------------------------------------
    # Cancel LIMIT orders when TP3 is reached
    # --------------------------------------------------

    def cancel_limits_if_tp3_reached(self, signal):

        orders = self.get_pending_orders()

        # No pending orders -> nothing to cancel
        limit_orders = [
            order
            for order in orders
            if order.magic == MAGIC_LIMIT
        ]

        if not limit_orders:
            return False

        tick = mt5.symbol_info_tick(self.symbol)

        if tick is None:
            return False

        direction = signal["Signal"]
        tp3 = signal["TP3"]

        if direction == "BUY":

            current_price = tick.bid

            if current_price < tp3:
                return False

        else:

            current_price = tick.ask

            if current_price > tp3:
                return False

        log(
            f"TP3 reached ({current_price:.3f}) "
            f"-> Cancelling LIMIT pending orders"
        )

        return self.cancel_pending_orders()
        
    # --------------------------------------------------
    # 
    # --------------------------------------------------
    
    def sync_signal(self, signal):

        # --------------------------------------------------
        # TP3 reached -> cancel remaining LIMIT orders
        # --------------------------------------------------

        if self.cancel_limits_if_tp3_reached(signal):

            self.submitted_limit.update({1, 2, 3, 4})
        
        tps = [
            signal["TP1"],
            signal["TP2"],
            signal["TP3"],
            signal["TP4"],
        ]

        # log(f"submitted_me={self.submitted_me}")
        # log(f"submitted_limit={self.submitted_limit}")
        for i, tp in enumerate(tps, start=1):
                    
            # -------------------------
            # Market Execution
            # -------------------------

            if i not in self.submitted_me:

                result = self.place_market_order(signal, i, tp)

                if result is True:

                    self.submitted_me.add(i)
                    log(f"ME TP{i} submitted")

                elif result == "SKIPPED":

                    self.submitted_me.add(i)
                    log(f"ME TP{i} skipped")

            # -------------------------
            # Limit Orders
            # -------------------------

            if i not in self.submitted_limit:

                if self.place_limit_order(signal, i, tp):

                    self.submitted_limit.add(i)
                    log(f"LIMIT TP{i} submitted")