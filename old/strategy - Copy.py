class Strategy:

    def __init__(self, trade_manager):
        self.tm = trade_manager
        self.executed_signal = None

    def make_signature(self, signal):
        return (
            signal["Signal"],
            round(signal["Entry"], 3),
            round(signal["StopLoss"], 3),
            round(signal["TP1"], 3),
        )

    def process(self, signal):

        # Ignore non-running signals
        if signal["State"] != "RUNNING":
            return

        signature = self.make_signature(signal)
        print("Current :", signature)
        print("Previous:", self.executed_signal)

        # Position already exists
        if self.tm.position_exists():

            # Same signal → do nothing
            if signature == self.executed_signal:
                return

            print("Signal changed.")

            if self.tm.close_position():

                if self.tm.open_trade(signal):
                    self.executed_signal = signature

            return

        # No position

        # Already traded this signal
        if signature == self.executed_signal:
            return

        print("Opening trade...")

        if self.tm.open_trade(signal):
            self.executed_signal = signature