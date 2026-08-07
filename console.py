from collections import deque
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from pathlib import Path
from datetime import datetime

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def get_activity_log():
    """Today's activity log file."""
    return LOG_DIR / f"activity_{datetime.now():%Y-%m-%d}.log"


def get_signal_log():
    """Today's signal log file."""
    return LOG_DIR / f"signals_{datetime.now():%Y-%m-%d}.log"

console = Console()

_logs = deque(maxlen=15)

_current_data = {}
_current_valid = False

_live = None


def start():
    """Start the live dashboard."""

    global _live

    if _live is None:
        _live = Live(
            build_layout(),
            console=console,
            refresh_per_second=5,
            # screen=True,
        )
        _live.start()


def stop():
    """Stop the dashboard."""

    global _live

    if _live is not None:
        _live.stop()
        _live = None


def log(*args):

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    message = " ".join(str(a) for a in args)

    line = f"[{now}] {message}"

    _logs.appendleft(line)

    with open(get_activity_log(), "a", encoding="utf-8") as f:
        f.write(line + "\n")
        
def log_signal(signal, reason):
    """
    Save a newly detected signal.
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(get_signal_log(), "a", encoding="utf-8") as f:

        f.write("=" * 70 + "\n")
        f.write(f"{now}\n")
        f.write(f"Reason : {reason}\n")

        fields = [
            "Signal",
            "Entry",
            "StopLoss",
            "TP1",
            "TP2",
            "TP3",
            "TP4",
            "BestPnL",
            "State",
        ]

        for field in fields:
            f.write(f"{field:<10}: {signal.get(field)}\n")

        f.write("\n")


def update_status(data, valid):

    global _current_data
    global _current_valid

    _current_data.clear()
    _current_data.update(data)
    _current_valid = valid

    refresh()


def refresh():

    if _live is not None:
        _live.update(build_layout())


def build_layout():

    layout = Layout()

    layout.split_column(

        Layout(name="status", size=16),

        Layout(name="log"),
    )

    # ------------------------
    # Status table
    # ------------------------

    table = Table(show_header=False, expand=True)

    table.add_column(width=12)
    table.add_column()

    fields = [

        "Signal",
        "Entry",
        "StopLoss",
        "TP1",
        "TP2",
        "TP3",
        "TP4",
        "BestPnL",
        "State",
    ]

    for field in fields:

        table.add_row(
            field,
            str(_current_data.get(field, "<missing>")),
        )

    table.add_row(
        "Status",
        "VALID" if _current_valid else "INVALID",
    )

    layout["status"].update(
        Panel(
            table,
            title="OCR Trader",
        )
    )

    # ------------------------
    # Activity
    # ------------------------

    log_table = Table(show_header=False, expand=True)

    log_table.add_column()

    for line in _logs:

        log_table.add_row(line)

    layout["log"].update(
        Panel(
            log_table,
            title="Activity",
        )
    )

    return layout