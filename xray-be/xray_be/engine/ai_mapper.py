import json
import os
import requests
from typing import List, Dict, Any, Optional
from engine.llm_logger import log_llm_interaction
from engine.models import record_llm_usage


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

    from engine.anonymizer import PIIAnonymizer
    anonymizer = PIIAnonymizer()
    clean_sample_rows = anonymizer.anonymize_records(sample_rows[:15])

    column_samples = {}
    for col in unmapped_columns:
        samples = []
        for r in clean_sample_rows:
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
            usage = resp.json().get("usage") or {}
            record_llm_usage(
                operation="ai_column_mapping",
                model=model_name,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0)
            )
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


def ai_smart_status_mapping(
    raw_statuses: List[str],
    sample_rows: Optional[List[Dict[str, Any]]] = None,
    current_status_map: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Uses rule-based heuristics first. If any statuses are ambiguous or mapped to 'other',
    uses LLM (gemini-3.8-flash-high) to classify them into canonical CRM stages:
    'new', 'in_progress', 'proposal', 'negotiation', 'won', 'lost', 'other'.
    """
    from engine.mapping import map_status

    status_map = dict(current_status_map or {})
    unresolved = []

    for st in raw_statuses:
        st_clean = str(st).strip()
        if not st_clean:
            continue
        if st_clean not in status_map:
            canon = map_status(st_clean)
            status_map[st_clean] = canon
            if canon == 'other':
                unresolved.append(st_clean)

    if not unresolved:
        return status_map

    # Query LLM to resolve ambiguous / custom statuses
    from pathlib import Path
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / '.env'
    if env_file.exists():
        load_dotenv(env_file)

    base_url = os.environ.get("OPENAI_BASE_URL", "http://144.31.157.209:8317/v1").rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model_name = os.environ.get("OPENAI_MODEL", "gemini-3.8-flash-high")

    system_prompt = (
        "Ты — специализированная нейросеть-эксперт по воронкам продаж и статусам заказов/сделок в CRM и e-commerce.\n"
        "Твоя задача: сопоставить текстовые статусы заказов или этапы сделок с каноническими стадиями воронки продаж.\n"
        "Канонические стадии:\n"
        "- 'new': новый лид, входящая заявка, первичный контакт, оформлен заказ, не разобрана\n"
        "- 'in_progress': сделка в работе, квалификация, обработка, сборка, комплектация, передано в доставку, в пути, отгружен, думает\n"
        "- 'proposal': выставлен счет, отправлено КП, ожидает оплаты, согласование коммерческих условий\n"
        "- 'negotiation': активные переговоры, торг, согласование договора\n"
        "- 'won': успешное завершение сделки, оплачено, доставлен и оплачен, выполнен, закрыт с победой\n"
        "- 'lost': отказ клиента, отменен, возврат, проиграна конкуренту, нецелевой лид, брак, спам\n"
        "- 'other': только если статус вообще не имеет отношения к воронке продаж или состоянию заказа\n\n"
        "Правила:\n"
        "1. Верни результат СТРОГО в формате валидного JSON без разметки: {\"<raw_status>\": \"<canonical_stage>\"}.\n"
        "2. Значение canonical_stage может быть ТОЛЬКО одним из: ['new', 'in_progress', 'proposal', 'negotiation', 'won', 'lost', 'other']."
    )

    user_prompt = {
        "unresolved_statuses": unresolved,
        "valid_canonical_stages": ["new", "in_progress", "proposal", "negotiation", "won", "lost", "other"]
    }

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
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]
            if content.startswith("json"):
                content = content[4:].strip()

            ai_statuses = json.loads(content)
            usage = resp.json().get("usage") or {}
            record_llm_usage(
                operation="ai_status_mapping",
                model=model_name,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0)
            )
            valid_stages = {"new", "in_progress", "proposal", "negotiation", "won", "lost", "other"}

            for raw_st, canon_stage in ai_statuses.items():
                if raw_st in status_map and canon_stage in valid_stages:
                    status_map[raw_st] = canon_stage

            log_llm_interaction(
                title="AI-НОРМАЛИЗАТОР СТАТУСОВ: УСПЕХ",
                payload_data=payload,
                response_data=ai_statuses,
                extra_info="STATUS: 200"
            )
    except Exception as e:
        log_llm_interaction(
            title="AI-НОРМАЛИЗАТОР СТАТУСОВ: ОШИБКА",
            payload_data=payload if "payload" in locals() else {},
            response_data=str(e)
        )
        print(f"[AI STATUS MAPPING ERROR]: {e}")

    return status_map
