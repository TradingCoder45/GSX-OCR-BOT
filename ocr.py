import os
import re
import time
import cv2
import mss
import numpy as np
import pytesseract

from mss.exception import ScreenShotError

from config import SEARCH_BOX, FIELDS, DEBUG, DEBUG_IMAGES, DEBUG_TIMING
from console import log, update_status

# --------------------------------------------------
# Image difference variables
# --------------------------------------------------
IMAGE_DIFF_MEAN_THRESHOLD = 0.1

_last_valid_box = None
_last_ocr_valid = False
IMAGE_DIFF_DEBUG = True

os.makedirs("debug", exist_ok=True)
sct = mss.mss()
_last_signal = None
_last_valid_signal = None

CLAHE = cv2.createCLAHE(
    clipLimit=2.5,
    tileGridSize=(8, 8),
)

# --------------------------------------------------
# Measure Time Elapsed in ms
# --------------------------------------------------

def _ms(start):
    return (time.perf_counter() - start) * 1000

# --------------------------------------------------
# Find Indicator Box
# --------------------------------------------------

def find_indicator_box(img):

    t0 = time.perf_counter()

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower = np.array([45, 80, 80], dtype=np.uint8)
    upper = np.array([95, 255, 255], dtype=np.uint8)

    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    best = None
    best_area = 0

    for cnt in contours:

        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h

        if area < 10000:
            continue

        if h < 180:
            continue

        if area > best_area:
            best = (x, y, w, h)
            best_area = area

    if DEBUG_TIMING:
        print(f"[OCR TIME] find_indicator_box: {_ms(t0):.1f} ms")

    return best

# --------------------------------------------------
# Preprocess Image
# --------------------------------------------------
  
def preprocess(img):

    img = cv2.resize(
        img,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gray = CLAHE.apply(gray)

    gray = cv2.bitwise_not(gray)

    _, gray = cv2.threshold(
        gray,
        120,
        255,
        cv2.THRESH_BINARY,
    )

    return gray

# --------------------------------------------------
# Measure search-box image difference
# --------------------------------------------------
    
def measure_image_difference(current_box, previous_box):

    if previous_box is None:
        return True

    diff = cv2.absdiff(current_box, previous_box)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    mean_diff = float(np.mean(gray_diff))

    return mean_diff > IMAGE_DIFF_MEAN_THRESHOLD
    
# --------------------------------------------------
# Prices OCR
# --------------------------------------------------

def combined_price_ocr(preprocessed_fields):

    t0 = time.perf_counter()

    price_fields = [
        "Entry",
        "StopLoss",
        "TP1",
        "TP2",
        "TP3",
        "TP4",
    ]

    images = [
        preprocessed_fields[field]
        for field in price_fields
    ]

    gap = 20

    width = max(img.shape[1] for img in images)

    height = sum(img.shape[0] for img in images)
    height += gap * (len(images) - 1)

    combined = np.zeros(
        (height, width),
        dtype=np.uint8,
    )

    y = 0

    for img in images:

        h, w = img.shape

        combined[y:y+h, :w] = img

        y += h + gap

    config = (
        "--oem 1 --psm 6 "
        "-c tessedit_char_whitelist=0123456789."
    )

    text = pytesseract.image_to_string(
        combined,
        config=config,
    )

    elapsed = (time.perf_counter() - t0) * 1000

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    values = {}

    for field, line in zip(price_fields, lines):

        line = line.replace(",", ".")
        line = line.replace("|", "I")
        line = line.replace("O", "0")
        line = line.replace("o", "0")

        m = re.search(
            r"\d+\.\d+",
            line,
        )

        if m:
            values[field] = float(m.group())

    if DEBUG_TIMING:
        print(
            f"[OCR TIME] Combined prices: "
            f"{elapsed:.1f} ms"
        )

    return values

# --------------------------------------------------
# Text OCR
# --------------------------------------------------

def combined_text_ocr(preprocessed_fields):

    t0 = time.perf_counter()

    text_fields = [
        "Signal",
        "State",
    ]

    images = [
        preprocessed_fields[field]
        for field in text_fields
    ]

    gap = 20

    width = max(img.shape[1] for img in images)

    height = sum(img.shape[0] for img in images)
    height += gap * (len(images) - 1)

    combined = np.zeros(
        (height, width),
        dtype=np.uint8,
    )

    y = 0

    for img in images:

        h, w = img.shape

        combined[y:y+h, :w] = img

        y += h + gap

    config = (
        "--oem 1 --psm 6 "
        "-c tessedit_char_whitelist=ABEGILNRSTUWY"
    )

    text = pytesseract.image_to_string(
        combined,
        config=config,
    )

    elapsed = (time.perf_counter() - t0) * 1000

    lines = [
        line.strip().upper()
        for line in text.splitlines()
        if line.strip()
    ]

    signal = None
    state = None

    for line in lines:

        if "BUY" in line:
            signal = "BUY"

        elif "SELL" in line:
            signal = "SELL"

        elif "RUNNING" in line:
            state = "RUNNING"

        elif "WAITING" in line:
            state = "WAITING"

    if DEBUG_TIMING:
        print(
            f"[OCR TIME] Combined text: "
            f"{elapsed:.1f} ms"
        )

    return signal, state

# --------------------------------------------------
# Signal Fields Count Check
# --------------------------------------------------
  
def is_complete_signal(data):

    required_fields = [
        "Signal",
        "Entry",
        "StopLoss",
        "TP1",
        "TP2",
        "TP3",
        "TP4",
        "State",
    ]

    return all(
        data.get(field) is not None
        for field in required_fields
    )

# --------------------------------------------------
# Valid Signal Check
# --------------------------------------------------

def validate_signal(data):
    """Validate OCR output."""

    price_fields = [
        "Entry",
        "StopLoss",
        "TP1",
        "TP2",
        "TP3",
        "TP4",
    ]
        
    if not all(field in data for field in price_fields):
        if DEBUG:
            log("Fields Count Not Valid")
        return False

    entry = data["Entry"]
    for field in price_fields[1:]:

        if abs(data[field] - entry) > 30:
            if DEBUG:
                log("Prices Diff > 30")
            return False

    if data.get("Signal") not in ("BUY", "SELL"):
        if DEBUG:
            log("Signal Not Valid")
        return False

    if data.get("State") not in ("RUNNING", "WAITING"):
        if DEBUG:
            log("State Not Valid")
        return False

    return True

# --------------------------------------------------
# Red Signal
# --------------------------------------------------

def read_signal():
    """
    Reads the TradingView indicator once.

    Returns
    -------
    dict
        Parsed signal

    None
        If OCR is invalid
    """

    global _last_valid_signal, _last_valid_box, _last_ocr_valid
    
    try:
        search = np.array(sct.grab(SEARCH_BOX))
        
        if DEBUG_IMAGES:
            cv2.imwrite("debug/search_box.png", search)
            
    except ScreenShotError as e:
        if DEBUG:
            log(f"Screenshot failed: {e}")
        return None
    
    search = cv2.cvtColor(search, cv2.COLOR_BGRA2BGR)

    rect = find_indicator_box(search)

    if rect is None:
        if DEBUG:
            log("Indicator box not found.")
        return None

    x, y, w, h = rect

    box = search[y:y+h, x:x+w]
    
    if DEBUG_IMAGES:
        cv2.imwrite("debug/full_box.png", box)  
        
    # --------------------------------------------------
    # Image difference check
    # --------------------------------------------------

    image_changed = measure_image_difference(
        box,
        _last_valid_box
    )

    # --------------------------------------------------
    # Skip OCR only when:
    #
    # 1. Previous OCR result was valid
    # 2. Previous valid signal exists
    # 3. Previous valid box exists
    # 4. Current box has not changed
    # --------------------------------------------------

    if (
        not image_changed
        and _last_ocr_valid
        and _last_valid_signal is not None
        and _last_valid_box is not None
    ):

        if DEBUG:
            log("[IMAGE DIFF] No change + previous valid signal -> skipping OCR")

        return _last_valid_signal.copy()

    data = {}
    preprocessed_fields = {}
    
    for field, (x, y, w, h) in FIELDS.items():

        field_start = time.perf_counter()
        
        crop = box[y:y+h, x:x+w]
        proc = preprocess(crop)
        preprocessed_fields[field] = proc

        if DEBUG_IMAGES:
            cv2.imwrite(f"debug/{field}.png", proc)

    signal, state = combined_text_ocr(preprocessed_fields)

    if signal is not None:
        data["Signal"] = signal

    if state is not None:
        data["State"] = state

    # --------------------------------------------------
    # Combined price OCR
    # --------------------------------------------------

    combined_prices = combined_price_ocr(preprocessed_fields)

    for field in (
        "Entry",
        "StopLoss",
        "TP1",
        "TP2",
        "TP3",
        "TP4",
    ):

        value = combined_prices.get(field)

        if value is not None:
            data[field] = value
        
    valid = validate_signal(data)
    update_status(data, valid)

    if not valid:
        _last_ocr_valid = False
        return None

    if not is_complete_signal(data):
        _last_ocr_valid = False
        return None

    _last_valid_signal = data.copy()
    _last_valid_box = box.copy()
    _last_ocr_valid = True

    return data
    
# --------------------------------------------------