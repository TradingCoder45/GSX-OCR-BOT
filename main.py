import time

from trade_manager import TradeManager
from strategy import Strategy
from ocr import read_signal

from console import start, stop
from config import DEBUG_TIMING

tm = TradeManager()
strategy = Strategy(tm)

start()

try:

    while True:

        t0 = time.perf_counter()

        signal = read_signal()
        
        t1 = time.perf_counter()

        if signal is not None:
            strategy.process(signal)
        
        t2 = time.perf_counter()

        if DEBUG_TIMING:
            print(
                f"OCR: {(t1-t0)*1000:.1f} ms | "
                f"Strategy: {(t2-t1)*1000:.1f} ms | "
                f"Total: {(t2-t0)*1000:.1f} ms"
            )
        
        time.sleep(0.1)

except KeyboardInterrupt:

    print("\nStopping bot...")

finally:

    stop()
    tm.shutdown()