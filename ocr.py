import os
import re

import cv2
import mss
import numpy as np
import pytesseract

from mss.exception import ScreenShotError

from config import SEARCH_BOX, FIELDS, DEBUG, DEBUG_IMAGES
from console import update_status

os.makedirs("debug", exist_ok=True)
sct = mss.mss()
_last_signal = None

def find_indicator_box(img):
    """
    Detect the GSX indicator box by its cyan/green border.

    Returns
    -------
    (x, y, w, h) relative to img
    or None.
    """

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

        # Reject tiny contours
        if area < 10000:
            continue

        # Box height is fairly constant
        if h < 180:
            continue

        if area > best_area:
            best = (x, y, w, h)
            best_area = area

    return best
    
def preprocess(img):
    """Prepare image for OCR."""

    img = cv2.resize(
        img,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8),
    )

    gray = clahe.apply(gray)
    gray = cv2.bitwise_not(gray)
    _, gray = cv2.threshold(
        gray,
        120,                 # Threshold
        255,                # Value assigned to pixels above threshold
        cv2.THRESH_BINARY,
    )

    return gray
    

def ocr_text(img, config):
    """OCR helper."""

    txt = pytesseract.image_to_string(
        img,
        config=config,
    )

    txt = txt.replace(",", ".")
    txt = txt.replace("|", "I")
    txt = txt.replace("O", "0")
    txt = txt.replace("o", "0")

    return txt.strip()


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

    # if DEBUG:
        # print("-" * 30)
        # for field in [
            # "Signal",
            # "Entry",
            # "StopLoss",
            # "TP1",
            # "TP2",
            # "TP3",
            # "TP4",
            # "BestPnL",
            # "State",
        # ]:
            # print(f"{field:<10}: {data.get(field, '<missing>')}")
        # print("-" * 30)
        
    if not all(field in data for field in price_fields):
        print("Fields Count Not Valid")
        return False

    entry = data["Entry"]
    for field in price_fields[1:]:

        if abs(data[field] - entry) > 300:
            print("Prices Diff > 300")
            return False

    if data.get("Signal") not in ("BUY", "SELL"):
        print("Signal Not Valid")
        return False

    if data.get("State") not in ("RUNNING", "WAITING", "CLOSED"):
        print("State Not Valid")
        return False

    return True


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

    # search = np.array(sct.grab(SEARCH_BOX))
    
    try:
        search = np.array(sct.grab(SEARCH_BOX))
    except ScreenShotError as e:
        log(f"Screenshot failed: {e}")
        return None
    
    search = cv2.cvtColor(search, cv2.COLOR_BGRA2BGR)

    rect = find_indicator_box(search)

    if rect is None:
        print("Indicator box not found.")
        return None

    x, y, w, h = rect

    box = search[y:y+h, x:x+w]

    if DEBUG_IMAGES:
        cv2.imwrite("debug/full_box.png", box)

    data = {}

    for field, (x, y, w, h) in FIELDS.items():

        crop = box[y:y+h, x:x+w]

        proc = preprocess(crop)

        if DEBUG_IMAGES:
            cv2.imwrite(f"debug/{field}.png", proc)

        # -------------------------
        # Signal
        # -------------------------

        if field == "Signal":

            global _last_signal

            # txt = ocr_text(
                # proc,
                # "--oem 1 --psm 7"
            # ).upper()
            
            txt = pytesseract.image_to_string(
                proc,
                config="--oem 3 --psm 7 "
            ).upper()

            txt = " ".join(txt.split())
            
            # if DEBUG:
                # print(f"{field} OCR: {repr(txt)}")

            # Common OCR fixes
            txt = txt.replace("5ELL", "SELL")
            txt = txt.replace("SELI", "SELL")
            txt = txt.replace("SELLL", "SELL")
            txt = txt.replace("$ELL", "SELL")
            txt = txt.replace("8UY", "BUY")

            if "BUY" in txt:
                data[field] = "BUY"
                _last_signal = "BUY"

            elif "SELL" in txt or "ELL" in txt:
                data[field] = "SELL"
                _last_signal = "SELL"

            else:
                # OCR occasionally misses the signal completely.
                # Reuse the previous one instead of invalidating
                # the whole reading.
                if _last_signal is not None:
                    data[field] = _last_signal

            continue

        # -------------------------
        # State
        # -------------------------

        if field == "State":

            txt = ocr_text(
                proc,
                "--oem 1 --psm 7 "
                "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            ).upper()

            m = re.search(
                r"RUNNING|WAITING|CLOSED",
                txt,
            )

            if m:
                data[field] = m.group()

            continue

        # -------------------------
        # BestPnL
        # -------------------------

        if field == "BestPnL":

            txt = ocr_text(
                proc,
                "--oem 1 --psm 7 "
                "-c tessedit_char_whitelist=0123456789.+-$",
            )

            m = re.search(
                r"[-+]?\d+\.\d+",
                txt,
            )

            if m:
                data[field] = float(m.group())

            continue

        # -------------------------
        # Prices
        # -------------------------
        
        txt = ocr_text(
            proc,
            "--oem 1 --psm 7 "
            "-c tessedit_char_whitelist=0123456789.",
        )

        m = re.search(
            r"\d+\.\d+",
            txt,
        )

        if m:
            data[field] = float(m.group())
            

    # if validate_signal(data):
        # print("VALID")
        # return data

    # print("INVALID")
    # return None
    
    valid = validate_signal(data)

    update_status(data, valid)

    if valid:
        return data

    return None