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


def filename_to_title(filename: str) -> str:
    stem = Path(filename or '').stem
    title = re.sub(r'[_-]+', ' ', stem).strip()
    return title[:48]


def clean_card_title(text: str) -> str:
    title = re.sub(r'\s+', ' ', (text or '').strip().strip('"«»“”'))
    if not title:
        return ''
    words = title.split()
    if len(words) > 6:
        title = ' '.join(words[:6])
    return title[:48]


def generate_llm_narrative(
    findings: List[Dict[str, Any]],
    default_headline: str,
    filename: str = '',
) -> Tuple[str, List[Dict[str, Any]], str]:
    """
    Calls OpenAI-compatible API to rewrite headline and action text for the findings.
    Adheres strictly to TZ §6.5:
    - Only rewrites 'headline' and 'action'.
    - Numbers and monetary impacts are preserved strictly from code.
    - Anonymized: no personal names, phones, or raw records sent.
    - Fallback to templates on timeout, parse error or network error.
    Also returns a short card_title for the scan list.
    """
    api_key = os.environ.get('OPENAI_API_KEY') or ''
    base_url = (os.environ.get('OPENAI_BASE_URL') or '').rstrip('/')
    model_name = os.environ.get('OPENAI_MODEL') or ''

    table_name = filename_to_title(filename)

    if not api_key or not base_url or not model_name:
        safe_print("[LLM NARRATOR] OPENAI_API_KEY, OPENAI_BASE_URL или OPENAI_MODEL не заданы, пропускаем генерацию.")
        return default_headline, findings, table_name

    if not findings:
        return default_headline, findings, table_name

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
        "Сформулируй главный вывод (headline), короткое имя карточки (card_title) "
        "и перепиши рекомендации (action) живым языком делового человека.\n"
        "ПРАВИЛА:\n"
        "1. НЕ меняй числа, проценты и денежные суммы, используй их ровно так, как передано.\n"
        "2. Headline — действие: что владельцу сделать прямо сейчас.\n"
        "3. card_title — короткое имя проверяемой таблицы для списка карточек: 2–5 слов. "
        "Отталкивайся от имени файла, как от названия выгрузки. Это не диагноз и не призыв. "
        "Примеры: ecommerce_moysklad_1c.csv → «Продажи МойСклад»; deals_bitrix.csv → «Сделки Битрикс».\n"
        "4. Верни строго JSON: {\"headline\": \"...\", \"card_title\": \"...\", \"actions\": {\"<metric_id>\": \"...\"}}"
    )

    user_prompt = (
        f"Имя файла таблицы: {filename or 'не указано'}\n"
        f"Черновик общего вывода: {default_headline}\n"
        f"Найденные проблемы и угрозы:\n{json.dumps(items_for_prompt, ensure_ascii=False, indent=2)}\n\n"
        "Перепиши headline, придумай card_title по имени таблицы и action для каждой метрики."
    )

    try:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        from engine.anonymizer import PIIAnonymizer
        anonymizer = PIIAnonymizer()

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": anonymizer.anonymize_text(user_prompt)}
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
            card_title = clean_card_title(parsed.get('card_title') or '')
            if not card_title:
                card_title = invent_card_title(findings, new_headline, filename)
            if not card_title:
                card_title = table_name

            updated_findings = []
            for f in findings:
                f_copy = dict(f)
                if f['metric_id'] in new_actions and isinstance(new_actions[f['metric_id']], str):
                    f_copy['action'] = new_actions[f['metric_id']]
                updated_findings.append(f_copy)

            return new_headline, updated_findings, card_title
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

    return default_headline, findings, table_name


def invent_card_title(findings: List[Dict[str, Any]], headline: str, filename: str = '') -> str:
    """Short list-card name from the scanned table. Separate from headline/action rewrite."""
    fallback = filename_to_title(filename)
    api_key = os.environ.get('OPENAI_API_KEY') or ''
    base_url = (os.environ.get('OPENAI_BASE_URL') or '').rstrip('/')
    model_name = os.environ.get('OPENAI_MODEL') or ''
    if not api_key or not base_url or not model_name:
        return fallback
    items = [
        {
            'metric_id': f.get('metric_id'),
            'verdict': f.get('verdict'),
            'value': f.get('value'),
            'unit': f.get('unit'),
            'money_impact': f.get('money_impact'),
        }
        for f in findings
        if f.get('verdict') in ('critical', 'watch', 'ok')
    ]
    from engine.anonymizer import PIIAnonymizer
    anonymizer = PIIAnonymizer()
    payload = {
        'model': model_name,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Придумай короткое имя проверяемой таблицы для списка карточек X-Ray. '
                    '2–5 слов, как название выгрузки, не диагноз и не призыв. '
                    'Отталкивайся от имени файла. Ответ — JSON: {"card_title": "..."}.'
                ),
            },
            {
                'role': 'user',
                'content': anonymizer.anonymize_text(
                    f'Файл: {filename or "не указан"}\n'
                    f'Headline: {headline}\n'
                    f'Метрики:\n{json.dumps(items, ensure_ascii=False)}'
                ),
            },
        ],
        'temperature': 0.4,
    }
    url = f'{base_url}/chat/completions'
    try:
        resp = requests.post(
            url,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=15,
        )
        if resp.status_code != 200:
            return fallback
        content = resp.json()['choices'][0]['message']['content']
        log_llm_interaction(
            title='ИМЯ КАРТОЧКИ СНИМКА',
            payload_data=payload,
            response_data=content,
            extra_info=f'URL: {url} | STATUS: {resp.status_code}',
        )
        parsed = json.loads(clean_json_text(content))
        return clean_card_title(parsed.get('card_title') or '') or fallback
    except Exception as error:
        logger.warning(f'LLM card_title fallback: {error}')
        return fallback
