from console import log, log_signal

class Strategy:

    def __init__(self, trade_manager):

        self.tm = trade_manager
        self.executed_signal = None
        self.last_state = None
        self.be_moved_for_signal = None

    # --------------------------------------------------

    def make_signature(self, signal):

        return (
            signal["Signal"],
            round(signal["Entry"], 2),
            round(signal["StopLoss"], 2),
        )
        
    # --------------------------------------------------
    # Detect TP2 closure
    # --------------------------------------------------

    def tp2_closed(self, signal):

        # TP2 must have been submitted previously.
        # If it was never submitted, it cannot be "closed".
        if 2 not in self.tm.submitted_limit:
            return False

        # TP2 position still open
        positions = self.tm.get_positions()

        for pos in positions:

            comment = pos.comment.upper()

            if "TP2" in comment:
                return False

        # TP2 may still be waiting as a pending LIMIT order
        if self.tm.limit_order_exists(2):
            return False

        # TP2 was submitted previously, but now there is
        # neither an open position nor a pending order.
        # Therefore TP2 has been closed/removed.
        return True

    # --------------------------------------------------

    def process(self, signal):

        state = signal["State"]
        # log(f"STATE={state} | LAST_STATE={self.last_state}")
        if state != self.last_state:
            log(f"STATE CHANGE: {self.last_state} -> {state}")

        # --------------------------------------------------
        # WAITING
        # --------------------------------------------------

        if state == "WAITING":

            if self.last_state != "WAITING":

                # log("State changed to WAITING.")
                log_signal(signal, "State -> WAITING")

                if self.tm.has_active_trade():

                    log("Closing positions and cancelling pending orders...")

                    if self.tm.clear_all_trades():
                        log("All trades cleared.")
                        
                # Always reset tracking when entering WAITING
                self.tm.reset_signal_tracking()

                # Also reset BE tracking
                self.be_moved_for_signal = None

            self.last_state = "WAITING"
            return
    
        # --------------------------------------------------
        # CLOSED
        # --------------------------------------------------

        if state == "CLOSED":
            return
            
        # We are RUNNING
        self.last_state = "RUNNING"

        # --------------------------------------------------
        # Only RUNNING continues
        # --------------------------------------------------

        signature = self.make_signature(signal)
        
        # --------------------------------------------------
        # Move TP3/TP4 to Break Even after TP2 closes
        # --------------------------------------------------

        if signature != self.be_moved_for_signal:

            if self.tp2_closed(signal):

                log("TP2 closed -> Moving TP3/TP4 to Break Even")

                self.tm.move_remaining_to_be(signal)

                self.be_moved_for_signal = signature

        # --------------------------------------------------
        # Existing trade (positions or pending)
        # --------------------------------------------------

        if self.tm.has_active_trade():

            if signature == self.executed_signal:

                # Same signal.
                # Retry any missing orders.
                self.tm.sync_signal(signal)

                return

            log("Signal changed.")
            log_signal(signal, "New Signature")

            if self.tm.clear_all_trades():

                self.tm.reset_signal_tracking()

                self.tm.sync_signal(signal)

                self.executed_signal = signature
                self.be_moved_for_signal = None

            return

        # --------------------------------------------------
        # No active trade
        # --------------------------------------------------

        if signature == self.executed_signal:

            # Same signal, but there may be orders that
            # previously failed and need another attempt.
            self.tm.sync_signal(signal)
            return

        log("Executing signal...")

        self.tm.sync_signal(signal)

        self.executed_signal = signature
        self.be_moved_for_signal = None