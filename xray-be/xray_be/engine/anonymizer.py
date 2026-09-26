"""
PII Anonymization & 152-ФЗ Compliance Engine for X-Ray.

Guarantees that no Personally Identifiable Information (PII) — customer names (ФИО),
phone numbers, or email addresses — is ever transmitted to external LLM providers
(Google Gemini, OpenAI, etc.).

Examples:
- +7 999 123-45-67 -> +7 999 ***-**-67
- 8 (999) 123-45-67 -> +7 999 ***-**-67
- ivanov@company.ru -> i***v@company.ru
- Иванов Иван Иванович -> Клиент #142
"""

import re
import json
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple


# Phone detection regex matching Russian & international mobile/landline formats
# Requires +7/8 prefix with 3xx/4xx/8xx/9xx code, or 10 digits starting with 9 (Russian mobile).
# Excludes hyphenated identifiers like ORD-202607-0076 or monetary numbers.
PHONE_REGEX = re.compile(
    r'(?<![a-zA-Z0-9_#№\-])(?:\+7|8)[\s\-\.]?\(?([3489][0-9]{2})\)?[\s\-\.]?([0-9]{3})[\s\-\.]?([0-9]{2})[\s\-\.]?([0-9]{2})(?![a-zA-Z0-9_\-])'
    r'|'
    r'(?<![a-zA-Z0-9_#№\-])\(?(9[0-9]{2})\)?[\s\-\.]?([0-9]{3})[\s\-\.]?([0-9]{2})[\s\-\.]?([0-9]{2})(?![a-zA-Z0-9_\-])'
)

# Email address detection regex
EMAIL_REGEX = re.compile(
    r'\b([A-Za-z0-9_.+-]+)@([A-Za-z0-9-]+\.[A-Za-z0-9-.]+)\b'
)

# Keywords indicating client/customer name columns
CLIENT_COL_KEYWORDS = {
    'client', 'клиент', 'клиенты', 'фио', 'покупатель', 'покупатели',
    'контрагент', 'контрагенты', 'заказчик', 'заказчики', 'получатель',
    'payer', 'customer', 'contact_name', 'fio', 'b2b_client', 'client_name',
    'имя_клиента', 'фио_клиента', 'клиент_фио', 'покупатель_фио'
}

# Keywords indicating contact (phone/email) columns
CONTACT_COL_KEYWORDS = {
    'contact', 'контакт', 'контакты', 'телефон', 'phone', 'тел', 'mobile',
    'email', 'почта', 'e-mail', 'mail', 'whatsapp', 'telegram', 'номер_телефона'
}

# Keywords indicating manager / employee columns (MUST NEVER BE MASKED!)
MANAGER_COL_KEYWORDS = {
    'manager', 'менеджер', 'менеджеры', 'сотрудник', 'сотрудники',
    'ответственный', 'ответственные', 'продавец', 'продавцы', 'курьер',
    'курьеры', 'оператор', 'операторы', 'автор', 'assigned_to', 'sales_rep',
    'rep', 'created_by', 'user_name', 'специалист', 'консультант',
    'имя_менеджера', 'фио_менеджера', 'менеджер_фио'
}

# Known non-client metric / analytical / business columns that should never be masked
SAFE_EXEMPT_COLUMNS = {
    'deal_id', 'id', 'status', 'status_raw', 'amount', 'list_price',
    'discount_pct', 'created_at', 'closed_at', 'first_contact_at',
    'status_changed_at', 'last_activity_at', 'source', 'product', 'item',
    'category', 'city', 'region', 'count', 'sum', 'avg', 'total',
    'quantity', 'qty', 'price', 'revenue', 'won_amt', 'lost_amt', 'stagnant_amt'
}

# Surnames / Patronymics endings for detecting Russian names in free text
PATRONYMIC_ENDINGS = ('ович', 'евич', 'ич', 'овна', 'евна', 'ична')
SURNAME_ENDINGS = ('ов', 'ова', 'ев', 'ева', 'ин', 'ина', 'ский', 'ская', 'ын', 'ына', 'их', 'ых')

# Non-name business words commonly capitalized in Russian reports that shouldn't be masked
NON_NAME_WORDS = {
    'отчет', 'сделки', 'сделка', 'продажи', 'продажа', 'выручка', 'заказ', 'заказы',
    'сумма', 'период', 'статус', 'воронка', 'конверсия', 'январь', 'февраль', 'март',
    'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
    'итог', 'итого', 'всего', 'бизнес', 'клиент', 'менеджер', 'канал', 'лид', 'лиды'
}


def mask_phone(text: str) -> str:
    """
    Masks phone numbers in a string, preserving operator prefix and last 2 digits:
    +7 999 123-45-67 -> +7 999 ***-**-67
    8 (999) 123-45-67 -> +7 999 ***-**-67
    89991234567 -> +7 999 ***-**-67
    """
    if not text or not isinstance(text, str):
        return text

    def _replace_phone(m):
        raw_digits = re.sub(r'\D', '', m.group(0))
        if len(raw_digits) == 11:
            code = raw_digits[1:4]
        else:
            code = raw_digits[:3]
        last2 = raw_digits[-2:]
        return f"+7 {code} ***-**-{last2}"

    return PHONE_REGEX.sub(_replace_phone, text)


def mask_email(text: str) -> str:
    """
    Masks email addresses:
    ivanov@company.ru -> i***v@company.ru
    alexander.petrov@mail.ru -> a***v@mail.ru
    """
    if not text or not isinstance(text, str):
        return text

    def _replace_email(m):
        user = m.group(1)
        domain = m.group(2)
        if len(user) <= 2:
            masked_user = "***"
        else:
            masked_user = f"{user[0]}***{user[-1]}"
        return f"{masked_user}@{domain}"

    return EMAIL_REGEX.sub(_replace_email, text)


def mask_contact_value(val: str) -> str:
    """
    Masks a dedicated contact column value (phone, email, or both).
    Handles standard Russian phones, international, and synthetic dataset phones.
    """
    if not val:
        return val
    s = str(val).strip()
    if not s:
        return s

    if '@' in s:
        return mask_email(s)

    digits = re.sub(r'\D', '', s)
    if len(digits) in (10, 11):
        if len(digits) == 11:
            code = digits[1:4]
        else:
            code = digits[:3]
        last2 = digits[-2:]
        return f"+7 {code} ***-**-{last2}"

    return mask_phone(mask_email(s))



def is_manager_column_name(col_name: str) -> bool:
    """Checks if a column name represents a manager/employee/rep."""
    if not col_name:
        return False
    clean = re.sub(r'[^a-zA-Zа-яА-ЯёЁ_]', '', col_name.strip().lower())
    if clean in MANAGER_COL_KEYWORDS:
        return True
    for kw in MANAGER_COL_KEYWORDS:
        if kw in clean:
            return True
    return False


def is_safe_exempt_column_name(col_name: str) -> bool:
    """Checks if a column name represents standard non-client data (metrics, dates, statuses)."""
    if not col_name:
        return False
    clean = re.sub(r'[^a-zA-Zа-яА-ЯёЁ_]', '', col_name.strip().lower())
    if clean in SAFE_EXEMPT_COLUMNS:
        return True
    for kw in SAFE_EXEMPT_COLUMNS:
        if kw == clean:
            return True
    return False


def is_client_column_name(col_name: str) -> bool:
    """Checks if a column name represents a client/customer name."""
    if not col_name:
        return False
    clean = re.sub(r'[^a-zA-Zа-яА-ЯёЁ_]', '', col_name.strip().lower())
    # Managers must never be classified as clients!
    if is_manager_column_name(clean):
        return False
    if clean in CLIENT_COL_KEYWORDS:
        return True
    for kw in CLIENT_COL_KEYWORDS:
        if kw in clean:
            return True
    return False


def is_contact_column_name(col_name: str) -> bool:
    """Checks if a column name represents contact information (phone/email)."""
    if not col_name:
        return False
    clean = re.sub(r'[^a-zA-Zа-яА-ЯёЁ_]', '', col_name.strip().lower())
    if clean in CONTACT_COL_KEYWORDS:
        return True
    for kw in CONTACT_COL_KEYWORDS:
        if kw in clean:
            return True
    return False


def is_russian_full_name(words: List[str]) -> bool:
    """Heuristic to check if 2 or 3 capitalized Cyrillic words represent a person's name."""
    if not words or len(words) not in (2, 3):
        return False
    for w in words:
        if not re.match(r'^[А-ЯЁ][а-яё]+$', w):
            return False
        if w.lower() in NON_NAME_WORDS:
            return False

    w_lower = [w.lower() for w in words]
    if len(words) == 3:
        # e.g. Иванов Иван Иванович or Иван Иванович Иванов
        if w_lower[2].endswith(PATRONYMIC_ENDINGS) or w_lower[1].endswith(PATRONYMIC_ENDINGS):
            return True
        if w_lower[0].endswith(SURNAME_ENDINGS) or w_lower[2].endswith(SURNAME_ENDINGS):
            return True
    elif len(words) == 2:
        # e.g. Иванов Иван or Иван Иванов
        if w_lower[0].endswith(SURNAME_ENDINGS) or w_lower[1].endswith(SURNAME_ENDINGS):
            return True

    return False


class PIIAnonymizer:
    """
    Context-aware PII Anonymizer compliant with Russian Federal Law 152-ФЗ.
    Provides consistent pseudonymization: the same customer name is always mapped
    to the same pseudonym (e.g. 'Иванов Иван Иванович' -> 'Клиент #142').
    """

    def __init__(self, prefix: str = "Клиент #", start_id: int = 142):
        self.prefix = prefix
        self.start_id = start_id
        self._name_to_pseudo: Dict[str, str] = {}
        self._pseudo_to_name: Dict[str, str] = {}
        self._used_ids: Set[int] = set()
        self._exempt_names: Set[str] = set()

    def register_exempt_name(self, name: Any):
        """
        Registers a name (e.g. manager, salesperson, employee) that must NEVER be masked or pseudonymized.
        """
        if not name:
            return
        s = str(name).strip()
        if not s:
            return
        norm = re.sub(r'\s+', ' ', s.lower())
        self._exempt_names.add(norm)
        for w in norm.split():
            if len(w) >= 3 and w not in NON_NAME_WORDS:
                self._exempt_names.add(w)

    def get_pseudonym(self, name: Any) -> str:
        """
        Returns a consistent pseudonym for a client name.
        Example: 'Иванов Иван Иванович' -> 'Клиент #142'
        """
        if name is None:
            return ""
        name_str = str(name).strip()
        if not name_str:
            return ""

        # Already anonymized
        if name_str.startswith(self.prefix) or name_str.startswith("Клиент #") or name_str.startswith("Client #"):
            return name_str

        norm_key = re.sub(r'\s+', ' ', name_str.lower())
        if norm_key in self._exempt_names:
            return name_str

        if norm_key in self._name_to_pseudo:
            return self._name_to_pseudo[norm_key]

        # Generate a stable 3-digit ID (starting with 142 or hash-based fallback)
        if len(self._used_ids) == 0:
            target_id = self.start_id
        else:
            # Deterministic hash ID based on normalized name
            h = int(hashlib.md5(norm_key.encode('utf-8')).hexdigest()[:6], 16)
            target_id = 101 + (h % 898)
            while target_id in self._used_ids:
                target_id = (target_id + 1) if target_id < 999 else 101

        self._used_ids.add(target_id)
        pseudo = f"{self.prefix}{target_id}"
        self._name_to_pseudo[norm_key] = pseudo
        self._pseudo_to_name[pseudo] = name_str
        return pseudo

    def register_client(self, name: str) -> str:
        """Pre-registers a known client name to ensure consistent pseudonym mapping."""
        return self.get_pseudonym(name)

    def _is_exempt_word(self, word: str) -> bool:
        """Checks if a word matches any exempt manager name stem (handling grammatical cases)."""
        w_low = word.lower()
        if w_low in self._exempt_names:
            return True
        for ex in self._exempt_names:
            if len(ex) < 4:
                continue
            stem_len = max(3, len(ex) - 2)
            if len(w_low) >= stem_len and ex[:stem_len] == w_low[:stem_len]:
                return True
        return False

    def anonymize_text(self, text: str) -> str:
        """
        Masks phones, emails, registered client names, and Russian names in arbitrary text.
        Exempts registered manager names.
        """
        if not text or not isinstance(text, str):
            return text

        # 1. Mask phones
        res = mask_phone(text)

        # 2. Mask emails
        res = mask_email(res)

        # 3. Replace already known registered client names
        # Sort by length descending to match longest names first
        sorted_names = sorted(self._name_to_pseudo.keys(), key=len, reverse=True)
        for norm_name in sorted_names:
            if len(norm_name) < 3 or norm_name in self._exempt_names or self._is_exempt_word(norm_name):
                continue
            pseudo = self._name_to_pseudo[norm_name]
            # Word boundary regex with case insensitivity
            pattern = re.compile(rf'(?<!\w){re.escape(norm_name)}(?!\w)', re.IGNORECASE)
            res = pattern.sub(pseudo, res)

        # 4. Detect Russian full names in free text (2 or 3 capitalized words)
        def _check_name_match(m):
            phrase = m.group(0)
            norm_phrase = re.sub(r'\s+', ' ', phrase.lower())
            if norm_phrase in self._exempt_names:
                return phrase

            words = phrase.split()
            # If any word matches an exempt manager's name stem, NEVER mask!
            if any(self._is_exempt_word(w) for w in words):
                return phrase

            if is_russian_full_name(words):
                return self.get_pseudonym(phrase)
            return phrase

        # Match 2 or 3 capitalized Cyrillic words
        res = re.sub(r'\b[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2}\b', _check_name_match, res)

        # Match "ИП <Фамилия>"
        def _check_ip_match(m):
            ip_str = m.group(0)
            norm_ip = re.sub(r'\s+', ' ', ip_str.lower())
            if norm_ip in self._exempt_names:
                return ip_str
            return self.get_pseudonym(ip_str)

        res = re.sub(r'\bИП\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ]\.?\s*[А-ЯЁ]\.?)?\b', _check_ip_match, res)

        return res

    def anonymize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymizes a single record/row dict (e.g. from deals table or sample rows).
        Explicitly preserves manager/employee names.
        """
        if not isinstance(record, dict):
            return record

        cleaned = {}
        for k, v in record.items():
            if v is None:
                cleaned[k] = v
                continue

            k_str = str(k)

            # 1. EXPLICIT EXEMPTION: Managers / Employees must NEVER be masked!
            if is_manager_column_name(k_str):
                cleaned[k] = v
                continue

            # 2. Client / Customer columns -> mask as 'Клиент #XXX'
            if is_client_column_name(k_str):
                cleaned[k] = self.get_pseudonym(v)
            # 3. Contact info (phone/email) columns -> mask phone & email
            elif is_contact_column_name(k_str):
                cleaned[k] = mask_contact_value(str(v))
            # 4. Known safe analytical columns (deal_id, status, amount, won_amt, product, source, date)
            elif is_safe_exempt_column_name(k_str):
                cleaned[k] = v
            # 5. Free-form text fields (e.g. comments, notes)
            elif isinstance(v, str):
                cleaned[k] = self.anonymize_text(v)
            elif isinstance(v, dict):
                cleaned[k] = self.anonymize_record(v)
            elif isinstance(v, list):
                cleaned[k] = [self.anonymize_record(item) if isinstance(item, dict) else item for item in v]
            else:
                cleaned[k] = v

        return cleaned

    def anonymize_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Anonymizes a list of dictionary rows."""
        if not records or not isinstance(records, list):
            return records
        return [self.anonymize_record(r) for r in records]

    def anonymize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Anonymizes a full list of OpenAI/Gemini chat messages before upstream API calls.
        Sanitizes text content, and deserializes/sanitizes tool results (e.g. SQL data).
        """
        if not messages or not isinstance(messages, list):
            return messages

        sanitized_messages = []
        for msg in messages:
            if not isinstance(msg, dict):
                sanitized_messages.append(msg)
                continue

            m_copy = dict(msg)
            role = m_copy.get("role")
            content = m_copy.get("content")

            if content and isinstance(content, str):
                # If tool message containing JSON database output
                if role == "tool":
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "rows" in parsed and isinstance(parsed["rows"], list):
                            parsed["rows"] = self.anonymize_records(parsed["rows"])
                            m_copy["content"] = json.dumps(parsed, ensure_ascii=False)
                        else:
                            m_copy["content"] = self.anonymize_text(content)
                    except Exception:
                        m_copy["content"] = self.anonymize_text(content)
                else:
                    m_copy["content"] = self.anonymize_text(content)

            # Sanitize tool calls arguments if present
            if "tool_calls" in m_copy and isinstance(m_copy["tool_calls"], list):
                tool_calls_clean = []
                for tc in m_copy["tool_calls"]:
                    tc_copy = json.loads(json.dumps(tc))
                    fn = tc_copy.get("function", {})
                    args_str = fn.get("arguments")
                    if args_str and isinstance(args_str, str):
                        try:
                            parsed_args = json.loads(args_str)
                            if isinstance(parsed_args, dict) and "query" in parsed_args:
                                # Keep SQL query syntax, but mask literal phones or emails if injected
                                parsed_args["query"] = mask_phone(mask_email(parsed_args["query"]))
                                fn["arguments"] = json.dumps(parsed_args, ensure_ascii=False)
                        except Exception:
                            pass
                    tool_calls_clean.append(tc_copy)
                m_copy["tool_calls"] = tool_calls_clean

            sanitized_messages.append(m_copy)

        return sanitized_messages

    def deanonymize_text(self, text: str) -> str:
        """
        Reverses pseudonymization if needed (restores 'Клиент #142' -> 'Иванов Иван Иванович').
        """
        if not text or not isinstance(text, str):
            return text
        res = text
        for pseudo, real_name in self._pseudo_to_name.items():
            res = res.replace(pseudo, real_name)
        return res


# Global default anonymizer instance
default_anonymizer = PIIAnonymizer()
