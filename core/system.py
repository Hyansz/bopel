"""System info helpers — CPU, RAM, Python version, time."""

import os
import platform
import sys
from datetime import datetime

import psutil


def python_version() -> str:
    return platform.python_version()


def os_info() -> str:
    return f"{platform.system()} {platform.release()}"


def cpu_percent() -> float:
    return psutil.cpu_percent(interval=0.1)


def ram_percent() -> float:
    return psutil.virtual_memory().percent


def ram_used_gb() -> float:
    return psutil.virtual_memory().used / (1024 ** 3)


def ram_total_gb() -> float:
    return psutil.virtual_memory().total / (1024 ** 3)


def current_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def terminal_name() -> str:
    term = os.environ.get("TERM_PROGRAM", "")
    if term:
        return term
    if os.environ.get("WT_SESSION"):
        return "Windows Terminal"
    return os.environ.get("COMSPEC", "cmd.exe")
