import os
import sys
import datetime
from pathlib import Path

# Base directory for logs: xray-business/logs
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'llm_debug.log'


def log_llm_interaction(title: str, payload_data: dict, response_data: str, extra_info: str = ""):
    """
    Appends structured LLM prompts and responses to logs/llm_debug.log with timestamps.
    Also prints safely to the terminal console.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 60

    log_entry = (
        f"\n{separator}\n"
        f"[{timestamp}] {title}\n"
        f"{separator}\n"
    )

    if extra_info:
        log_entry += f"{extra_info}\n\n"

    if payload_data:
        system_prompt = ""
        user_prompt = ""
        for m in payload_data.get('messages', []):
            if m.get('role') == 'system':
                system_prompt = m.get('content', '')
            elif m.get('role') == 'user':
                user_prompt = m.get('content', '')

        model = payload_data.get('model', 'unknown')
        log_entry += f"MODEL: {model}\n"
        if system_prompt:
            log_entry += f"\n--- СИСТЕМНЫЙ ПРОМПТ ---\n{system_prompt}\n"
        if user_prompt:
            log_entry += f"\n--- ПОЛЬЗОВАТЕЛЬСКИЙ ПРОМПТ ---\n{user_prompt}\n"

    if response_data:
        log_entry += f"\n--- ОТВЕТ НЕЙРОСЕТИ ---\n{response_data}\n"

    log_entry += f"{separator}\n"

    # 1. Write to log file (UTF-8)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[LOG ERROR] Не удалось записать в лог-файл: {e}", file=sys.stderr)

    # 2. Print to console safely
    try:
        print(log_entry)
    except Exception:
        clean = log_entry.encode('ascii', errors='backslashreplace').decode('ascii')
        print(clean)
