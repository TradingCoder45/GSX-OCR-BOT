# import time

# from trade_manager import TradeManager
# from strategy import Strategy
# from ocr import read_signal
# from console import log


# tm = TradeManager()

# strategy = Strategy(tm)

# print("\n" * 30)

# while True:

    # signal = read_signal() 

    # if signal:

        # strategy.process(signal)

    # time.sleep(0.5)

import time

from trade_manager import TradeManager
from strategy import Strategy
from ocr import read_signal

from console import start, stop

tm = TradeManager()
strategy = Strategy(tm)

start()

try:

    while True:

        signal = read_signal()

        if signal is not None:
            strategy.process(signal)

        time.sleep(0.5)

except KeyboardInterrupt:

    print("\nStopping bot...")

finally:

    stop()
    tm.shutdown()