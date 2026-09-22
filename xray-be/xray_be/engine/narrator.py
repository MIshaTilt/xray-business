import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import os
import re
import json
import logging
import requests
from typing import List, Dict, Any, Tuple
from pathlib import Path
from dotenv import load_dotenv
from .llm_logger import log_llm_interaction

logger = logging.getLogger(__name__)

# Load .env
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        clean_args = [
            str(a).encode('ascii', errors='backslashreplace').decode('ascii')
            for a in args
        ]
        print(*clean_args, **kwargs)


def clean_json_text(text: str) -> str:
    """Extract JSON object from markdown code blocks or raw text."""
    text = text.strip()
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match_raw = re.search(r'(\{.*\})', text, re.DOTALL)
    if match_raw:
        return match_raw.group(1).strip()
    return text


def generate_llm_narrative(findings: List[Dict[str, Any]], default_headline: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Calls OpenAI-compatible API to rewrite headline and action text for the findings.
    Adheres strictly to TZ §6.5:
    - Only rewrites 'headline' and 'action'.
    - Numbers and monetary impacts are preserved strictly from code.
    - Anonymized: no personal names, phones, or raw records sent.
    - Fallback to templates on timeout, parse error or network error.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = os.environ.get('OPENAI_BASE_URL', 'http://144.31.157.209:8317/v1').rstrip('/')

    if not api_key:
        safe_print("[LLM NARRATOR] OPENAI_API_KEY не задан, пропускаем генерацию.")
        return default_headline, findings

    if not findings:
        return default_headline, findings

    # Prepare safe payload for LLM without PII
    items_for_prompt = []
    for f in findings:
        items_for_prompt.append({
            'metric_id': f['metric_id'],
            'verdict': f['verdict'],
            'value': f['value'],
            'unit': f['unit'],
            'money_impact': f['money_impact'],
            'threshold_label': f['threshold_label'],
            'draft_action': f['action']
        })

    system_prompt = (
        "Ты — бизнес-аналитик сервиса рентгена продаж для малого бизнеса X-Ray. "
        "Твоя задача: сформулировать главный вывод (headline) и переписать рекомендации (action) "
        "живым, емким и убедительным языком делового человека.\n"
        "ПРАВИЛА:\n"
        "1. НЕ меняй числа, проценты и денежные суммы, используй их ровно так, как передано.\n"
        "2. Фокусируйся на конкретном действии: что владельцу сделать прямо сейчас.\n"
        "3. Верни результат строго в формате JSON: {\"headline\": \"...\", \"actions\": {\"<metric_id>\": \"...\"}}"
    )

    user_prompt = (
        f"Черновик общего вывода: {default_headline}\n"
        f"Найденные проблемы и угрозы:\n{json.dumps(items_for_prompt, ensure_ascii=False, indent=2)}\n\n"
        "Перепиши headline и action для каждой метрики."
    )

    try:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gemini-3.8-flash-high",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            res_data = resp.json()
            content = res_data['choices'][0]['message']['content']

            # Log interaction to file and console
            log_llm_interaction(
                title="ДИАГНОСТИКА: ПЕРЕПИСЫВАНИЕ ЗАКЛЮЧЕНИЯ И УГРОЗ",
                payload_data=payload,
                response_data=content,
                extra_info=f"URL: {url} | STATUS: {resp.status_code}"
            )

            cleaned = clean_json_text(content)
            parsed = json.loads(cleaned)

            new_headline = parsed.get('headline') or default_headline
            new_actions = parsed.get('actions') or {}

            updated_findings = []
            for f in findings:
                f_copy = dict(f)
                if f['metric_id'] in new_actions and isinstance(new_actions[f['metric_id']], str):
                    f_copy['action'] = new_actions[f['metric_id']]
                updated_findings.append(f_copy)

            return new_headline, updated_findings
        else:
            log_llm_interaction(
                title="ОШИБКА ОБРАЩЕНИЯ К НЕЙРОСЕТИ",
                payload_data=payload,
                response_data=resp.text,
                extra_info=f"URL: {url} | STATUS: {resp.status_code}"
            )

    except Exception as e:
        log_llm_interaction(
            title="ИСКЛЮЧЕНИЕ ПРИ ОБРАЩЕНИИ К НЕЙРОСЕТИ",
            payload_data=payload if 'payload' in locals() else {},
            response_data=str(e)
        )
        logger.warning(f"LLM narrative generation fallback to templates: {e}")

    return default_headline, findings
