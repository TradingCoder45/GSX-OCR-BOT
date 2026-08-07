# GSX OCR Trading Bot

Python-based automated trading bot that reads trading signals from an on-screen TradingView indicator using OCR and executes trades through MetaTrader 5.

The bot is designed around a TradingView → OCR → Python strategy → MT5 execution workflow.

---

## Overview

The GSX OCR Bot continuously captures the signal panel displayed on the screen, extracts the trading information using OCR, validates the signal, and manages the corresponding MT5 trades.

The signal contains:

* Signal direction
* Entry price
* Stop Loss
* TP1
* TP2
* TP3
* TP4
* Best PnL
* Signal state

Only valid signals in the appropriate state are processed by the trading strategy.

---

## Architecture

```text
TradingView Indicator
        │
        ▼
   Screen Capture
        │
        ▼
      OCR
        │
        ▼
 Signal Validation
        │
        ▼
     Strategy
        │
        ▼
   Trade Manager
        │
        ▼
    MetaTrader 5
```

### Main components

| File               | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `main.py`          | Main application loop                    |
| `ocr.py`           | Screen capture, preprocessing and OCR    |
| `strategy.py`      | Signal state and trade-management logic  |
| `trade_manager.py` | MT5 connection, orders and positions     |
| `config.py`        | Bot configuration and trading parameters |

---

# Requirements

## Software

* Windows
* Python 3.x
* MetaTrader 5
* TradingView
* Tesseract OCR

## Python packages

Install the required packages with:

```bash
pip install MetaTrader5
pip install opencv-python
pip install mss
pip install numpy
pip install pytesseract
```

If a `requirements.txt` file is provided in the repository, install everything with:

```bash
pip install -r requirements.txt
```

---

# Tesseract OCR

The bot requires Tesseract OCR to be installed on Windows.

The Tesseract executable path is configured in the project configuration/code.

Example:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Make sure the path matches the actual installation location on the computer running the bot.

---

# MetaTrader 5

MetaTrader 5 must be installed and running on the machine where the Python bot is executed.

The MT5 terminal must:

1. Be logged into the desired trading account.
2. Have the required symbol available.
3. Allow algorithmic trading where required.
4. Remain running while the bot is active.

The Python `MetaTrader5` package communicates with the running MT5 terminal.

---

# Configuration

Trading and OCR settings are controlled through the project's configuration files.

Typical settings include:

* Trading symbol
* Lot size
* Magic numbers
* Slippage
* OCR/debug settings
* Screen/ROI coordinates

Before running the bot, verify that the configured symbol and trading parameters match the MT5 account.

---

# OCR Signal

The OCR system reads the signal panel from the screen.

A valid signal contains:

```text
Signal
Entry
StopLoss
TP1
TP2
TP3
TP4
BestPnL
State
```

Example:

```text
Signal    : BUY
Entry     : 4104.653
StopLoss  : 4107.933
TP1       : 4103.832
TP2       : 4102.684
TP3       : 4101.372
TP4       : 4099.731
BestPnL   : 1.975
State     : RUNNING
```

The OCR layer validates the extracted values before passing the signal to the strategy.

---

# Signal States

The indicator can report different states.

The bot uses the signal state to determine whether the signal should be processed.

The important states are:

```text
RUNNING
WAITING
CLOSED
```

Trading actions are primarily performed while the signal is `RUNNING`.

When the signal changes state, the strategy manages the existing orders/positions according to the current implementation.

---

# Trade Execution Logic

The bot uses four TP levels:

```text
TP1
TP2
TP3
TP4
```

Each TP is handled independently.

The current implementation uses the **LIMIT strategy** for these trades.

The previous dedicated ME order system remains in the source code for possible future use, but its submission from the active strategy has been disabled.

---

## LIMIT Strategy

There are two possible situations for each signal.

### BUY

If:

```text
Current Ask > Signal Entry
```

the market has not reached the entry yet.

The bot places a:

```text
BUY LIMIT
```

at the original signal Entry price.

Example:

```text
Signal Entry = 4104.653
Current Ask  = 4105.100
```

The bot places:

```text
BUY LIMIT @ 4104.653
```

The original signal SL and TP are used.

---

### BUY — Price Already Below Entry

If:

```text
Current Ask <= Signal Entry
```

the market has already moved through the desired entry price.

Waiting for a BUY LIMIT at the original entry would no longer provide the intended behavior.

The bot therefore executes the LIMIT-strategy order immediately at the current market price.

Example:

```text
Signal Entry = 4104.653
Current Ask  = 4104.200
```

The bot executes approximately:

```text
BUY @ 4104.200
```

This allows the strategy to benefit from the better available entry price.

The original signal values are retained:

```text
SL = Signal StopLoss
TP = Signal TP
```

---

## SELL

The logic is reversed for SELL signals.

If:

```text
Current Bid < Signal Entry
```

the bot places:

```text
SELL LIMIT @ Signal Entry
```

If:

```text
Current Bid >= Signal Entry
```

the bot executes the LIMIT-strategy order immediately at the current market price.

Example:

```text
Signal Entry = 4104.653
Current Bid  = 4105.100
```

The bot executes approximately:

```text
SELL @ 4105.100
```

Again, the original signal SL and TP values are retained.

---

# Order Identification

LIMIT-strategy trades use the LIMIT magic number and comments.

Examples:

```text
LIMIT TP1
LIMIT TP2
LIMIT TP3
LIMIT TP4
```

This allows the bot and external reporting tools to distinguish these trades from other MT5 trades.

The previous ME order code and its associated magic number remain in the project but are not currently used for active order submission.

---

# Take Profit and Stop Loss

Each TP order uses its corresponding signal TP.

For example:

```text
LIMIT TP1 → Signal TP1
LIMIT TP2 → Signal TP2
LIMIT TP3 → Signal TP3
LIMIT TP4 → Signal TP4
```

The Stop Loss is the signal's original Stop Loss for all four TP trades.

Therefore, the four trades share the same SL but have different TP levels.

```text
             ┌── TP1
             ├── TP2
Entry ───────┼── TP3
             └── TP4
             │
             └── SL
```

When a market-executed LIMIT-strategy trade is opened because price has already passed the signal entry, the bot attempts to apply the original SL and TP to the newly opened position.

---

# Magic Numbers

Magic numbers are used to identify the bot's trades.

The project contains separate identifiers for the LIMIT and previous ME systems.

The active LIMIT strategy uses:

```text
MAGIC_LIMIT
```

The older ME system remains available in the code but is currently disabled from the active strategy.

---

# Duplicate Protection

The strategy tracks submitted TP orders so that the same signal does not continuously create duplicate trades.

The system uses the signal information and internal state to determine whether an order has already been submitted.

This prevents the main OCR loop from repeatedly opening the same TP orders while the signal remains active.

---

# Signal Changes

The strategy monitors changes in the signal.

A signal is identified using its relevant trading parameters, including:

* Direction
* Entry
* Stop Loss
* TP information

This allows the bot to distinguish a new trading signal from repeated OCR readings of the same signal.

OCR may read the same signal hundreds of times while it remains on screen. The strategy should therefore treat repeated identical readings as the same signal rather than as new trade opportunities.

---

# OCR Validation

The OCR layer performs validation before a signal reaches the trading strategy.

Validation includes checks such as:

* Required price fields are present.
* Signal direction is valid.
* Signal state is recognized.
* TP/SL values are within reasonable distance of Entry.
* OCR output is normalized where necessary.

OCR corrections can also handle common recognition errors involving:

* Decimal separators
* `O` / `0`
* `|` / `I`
* Other common OCR substitutions

Invalid OCR results are rejected rather than sent directly to MT5.

---

# Debugging

Debugging options are available in the project configuration.

When enabled, the OCR system can save processed images for inspection.

Typical debugging workflow:

```text
Screen Capture
      ↓
Detected Signal Box
      ↓
Individual OCR Fields
      ↓
OCR Text
      ↓
Validation Result
```

Debug images can help identify:

* Incorrect screen coordinates
* Indicator box detection problems
* OCR recognition errors
* Incorrect preprocessing
* Signal validation failures

---

# Running the Bot

Start MetaTrader 5 first and make sure the correct trading account is connected.

Then open a terminal in the project directory and run:

```bash
python main.py
```

The bot should establish the MT5 connection and begin reading the signal panel.

Typical startup output:

```text
Connected to MT5
```

The bot then continuously:

1. Captures the signal panel.
2. Runs OCR.
3. Validates the signal.
4. Passes valid signals to the strategy.
5. Checks existing orders/positions.
6. Submits the required TP orders.
7. Continues monitoring the signal.

---

# TradingView / Screen Requirements

Because this system uses screen OCR rather than a TradingView API, the TradingView signal panel must remain visible to the bot.

The screen layout and indicator location must remain compatible with the configured OCR detection area.

Changing the following may require updating OCR configuration:

* Monitor resolution
* Windows display scaling
* TradingView zoom
* Browser zoom
* Indicator position
* Indicator box size
* Chart layout

---

# Remote Desktop

The bot depends on screen capture, so the Windows session must remain in a state where the OCR process can actually capture the TradingView screen.

Locking the Windows session or using a remote desktop configuration that removes the graphical desktop can prevent OCR from seeing the signal panel.

A remote-access solution that maintains an active graphical session is preferable for unattended operation.

---

# Safety

This bot places real MT5 trades.

Before running it on a live account:

1. Test with a demo account.
2. Verify the symbol.
3. Verify lot size.
4. Verify SL and TP behavior.
5. Verify magic numbers.
6. Verify duplicate-order protection.
7. Verify the behavior when price is already beyond Entry.
8. Verify the behavior when the signal changes from `RUNNING` to `WAITING`.
9. Verify that pending orders are handled correctly.
10. Monitor the first live sessions carefully.

Never assume that a successful Python function call means a broker accepted the order. MT5 return codes must be checked.

---

# Project Status

The bot is under active development.

Current active execution model:

```text
OCR Signal
    ↓
Signal Validation
    ↓
Strategy
    ↓
LIMIT Strategy
    ├── Price has not reached Entry
    │       ↓
    │   Pending LIMIT Order
    │
    └── Price already passed Entry
            ↓
        Immediate Market Execution
        using LIMIT magic/comment
```

The dedicated ME order implementation remains in the source code but is currently disabled from the active strategy.

---

# Disclaimer

This software is provided for development and research purposes.

Automated trading involves substantial financial risk. The developer/user is responsible for testing, configuration, broker compatibility, execution behavior, and any resulting trading decisions or losses.

Use a demo account for testing before using real funds.
