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
    "left": 850,
    "top": 250,
    "width": 500,
    "height": 500,
}

FIELDS = {
    "Signal":    (73,   2, 117, 26),
    "Entry":     (73,  29, 117, 26),
    "StopLoss":  (73,  56, 117, 26),
    "TP1":       (73,  83, 117, 26),
    "TP2":       (73, 110, 117, 26),
    "TP3":       (73, 137, 117, 26),
    "TP4":       (73, 164, 117, 26),
    "BestPnL":   (73, 191, 117, 26),
    "State":     (73, 218, 117, 26),
}

DEBUG = True
DEBUG_IMAGES = False

# ----------------------------

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)