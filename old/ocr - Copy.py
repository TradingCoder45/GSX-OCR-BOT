import os
import re

import cv2
import mss
import numpy as np
import pytesseract

from config import BOX, FIELDS, DEBUG


os.makedirs("debug", exist_ok=True)
sct = mss.mss()
_last_signal = None


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
    # gray = cv2.bitwise_not(gray)

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

    if DEBUG:
        print(data["Signal"])
        print(data["Entry"])
        print(data["StopLoss"])
        print(data["TP1"])
        print(data["TP2"])
        print(data["TP3"])
        print(data["TP4"])
        print(data["State"])
        
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

    # with mss.mss() as sct:

    box = np.array(sct.grab(BOX))
    box = cv2.cvtColor(box, cv2.COLOR_BGRA2BGR)

    if DEBUG:
        cv2.imwrite("debug/full_box.png", box)

    data = {}

    for field, (x, y, w, h) in FIELDS.items():

        crop = box[y:y+h, x:x+w]

        proc = preprocess(crop)

        if DEBUG:
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
            "--oem 1 --psm 8 "
            "-c tessedit_char_whitelist=0123456789.",
        )

        m = re.search(
            r"\d+\.\d+",
            txt,
        )

        if m:
            data[field] = float(m.group())
                  

    # if validate_signal(data):
        # return data

    # return None
    
    print("-" * 60)
    print(data)

    if validate_signal(data):
        print("VALID")
        return data

    print("INVALID")
    return None