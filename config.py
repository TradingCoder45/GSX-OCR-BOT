import pytesseract

# ----------------------------
# MT5
# ----------------------------

SYMBOL = "XAUUSD"

LOT = 0.01
SLIPPAGE = 20

MAGIC_ME = 100100
MAGIC_LIMIT = 100200

# ----------------------------
# OCR
# ----------------------------

BOX = {
    "left": 1043,
    "top": 401,
    "width": 190,
    "height": 242
}

SEARCH_BOX = {
    "left": 1015,
    "top": 375,
    "width": 250,
    "height": 300,
}

FIELDS = {
    "Signal":    (73,   2, 117, 26),
    "Entry":     (73,  29, 117, 26),
    "StopLoss":  (73,  56, 117, 26),
    "TP1":       (73,  83, 117, 26),
    "TP2":       (73, 110, 117, 26),
    "TP3":       (73, 137, 117, 26),
    "TP4":       (73, 164, 117, 26),
    # "BestPnL":   (73, 191, 117, 26),
    "State":     (73, 218, 117, 26),
}

# ----------------------------
# Trading session times
# ----------------------------

TRADING_START_TIME = "01:10"
DAILY_CLOSE_TIME = "23:55"

# ----------------------------

DEBUG = True
DEBUG_IMAGES = True
DEBUG_TIMING = False

# ----------------------------

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)