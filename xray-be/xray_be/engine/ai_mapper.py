import json
import os
import requests
from typing import List, Dict, Any, Optional
from engine.llm_logger import log_llm_interaction


def ai_smart_column_mapping(
    columns: List[str],
    sample_rows: List[Dict[str, Any]],
    current_mapping: Dict[str, str]
) -> Dict[str, str]:
    """
    Uses LLM (gemini-3.8-flash-high) to identify unmapped columns by analyzing
    header names and sample values.
    Fills in missing canonical fields like 'amount', 'status', 'created_at', 'client', etc.
    """
    canonical_descriptions = {
        "amount": "Итоговая сумма сделки или выручка (число/деньги в рублях, например: '185 000 руб.'). Внимание: не путай с номером заказа / ID.",
        "deal_id": "Номер или идентификатор заказа/заявки (например: 'ORD-8801', '101', '#542')",
        "status": "Статус или этап сделки в воронке (например: 'Успешно завершено', 'Застряло / Думает', 'Слив / Отказ')",
        "created_at": "Дата и время создания или залива сделки / заказа",
        "closed_at": "Дата закрытия, завершения или оплаты сделки",
        "client": "Имя заказчика, название компании или контрагента",
        "manager": "Ответственный сотрудник, продавец или менеджер сделки (кто ведет сделку)",
        "contact": "Телефон или email контактного лица",
        "source": "Источник лида, рекламный канал или площадка",
        "first_contact_at": "Дата/время первого ответа или отклика с клиентом",
        "status_changed_at": "Дата/время последней смены статуса сделки",
        "last_activity_at": "Дата/время последнего действия или коммуникации",
        "list_price": "Базовая цена без скидки / официальный прайс",
        "discount_pct": "Процент предоставленной скидки"
    }

    # Find missing fields
    missing_fields = {k: v for k, v in canonical_descriptions.items() if k not in current_mapping}
    if not missing_fields:
        return current_mapping

    # Prepare unmapped columns and their sample values (up to 3 non-empty values per column)
    used_columns = set(current_mapping.values())
    unmapped_columns = [c for c in columns if c not in used_columns]
    if not unmapped_columns:
        return current_mapping

    column_samples = {}
    for col in unmapped_columns:
        samples = []
        for r in sample_rows[:15]:
            v = r.get(col)
            if v is not None and str(v).strip() != "":
                samples.append(str(v).strip())
                if len(samples) >= 3:
                    break
        column_samples[col] = samples

    system_prompt = (
        "Ты — специализированная нейросеть-нормализатор структуры таблиц продаж и CRM.\n"
        "Твоя задача: сопоставить неизвестные колонки из пользовательского файла с каноническими полями системы.\n"
        "Правила:\n"
        "1. Сопоставляй только тогда, когда уверен по смыслу названия или типу примеров значений.\n"
        "2. Одна колонка может быть сопоставлена максимум с одним каноническим полем.\n"
        "3. Верни результат СТРОГО в формате JSON без разметки: {\"<canonical_field>\": \"<original_column_name>\"}.\n"
        "4. Если для поля нет подходящей колонки, не включай его в JSON."
    )

    user_prompt = {
        "needed_canonical_fields": missing_fields,
        "available_unmapped_columns_with_samples": column_samples
    }

    from pathlib import Path
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / '.env'
    if env_file.exists():
        load_dotenv(env_file)

    base_url = os.environ.get("OPENAI_BASE_URL", "http://144.31.157.209:8317/v1").rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model_name = os.environ.get("OPENAI_MODEL", "gemini-3.8-flash-high")

    target_url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False, indent=2)}
        ],
        "temperature": 0.0
    }

    try:
        resp = requests.post(target_url, headers=headers, json=payload, timeout=12)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            # Clean possible markdown fences
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

            ai_mapping = json.loads(cleaned)
            log_llm_interaction(
                title="AI-НОРМАЛИЗАТОР КОЛОНОК: УСПЕХ",
                payload_data=payload,
                response_data=ai_mapping,
                extra_info=f"STATUS: 200"
            )

            # Merge validated suggestions into current_mapping
            assigned_now = set(current_mapping.values())
            updated_mapping = dict(current_mapping)

            for canon_k, orig_col in ai_mapping.items():
                if canon_k in missing_fields and orig_col in unmapped_columns and orig_col not in assigned_now:
                    updated_mapping[canon_k] = orig_col
                    assigned_now.add(orig_col)

            return updated_mapping
    except Exception as e:
        log_llm_interaction(
            title="AI-НОРМАЛИЗАТОР КОЛОНОК: ОШИБКА",
            payload_data=payload if "payload" in locals() else {},
            response_data=str(e)
        )
        print(f"[AI MAPPING FALLBACK ERROR]: {e}")

    return current_mapping
