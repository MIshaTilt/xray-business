"""
Automated unit tests for 152-ФЗ PII Anonymization & Privacy Compliance.
"""
import os
import sys
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath('xray_be'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xray_be.settings')

import django
django.setup()

from engine.anonymizer import (
    PIIAnonymizer,
    mask_phone,
    mask_email,
    is_client_column_name,
    is_contact_column_name,
    is_russian_full_name
)
from engine.tools import execute_tool_call
from engine.models import Snapshot, Deal


def test_phone_masking():
    cases = [
        ('+7 999 123-45-67', '+7 999 ***-**-67'),
        ('8 (999) 123-45-67', '+7 999 ***-**-67'),
        ('89991234567', '+7 999 ***-**-67'),
        ('+79991234567', '+7 999 ***-**-67'),
        ('+7 (926) 000-11-22', '+7 926 ***-**-22'),
        ('тел. +7-999-123-45-67 звонить с 10', 'тел. +7 999 ***-**-67 звонить с 10'),
    ]
    for inp, expected in cases:
        out = mask_phone(inp)
        assert out == expected, f"Expected {expected}, got {out}"
    print("✓ Phone masking tests passed!")


def test_email_masking():
    cases = [
        ('ivanov@company.ru', 'i***v@company.ru'),
        ('alexander.petrov@mail.ru', 'a***v@mail.ru'),
        ('client@gmail.com', 'c***t@gmail.com'),
        ('a@b.com', '***@b.com'),
        ('напиши на test@example.com скорее', 'напиши на t***t@example.com скорее'),
    ]
    for inp, expected in cases:
        out = mask_email(inp)
        assert out == expected, f"Expected {expected}, got {out}"
    print("✓ Email masking tests passed!")


def test_client_name_pseudonymization():
    anon = PIIAnonymizer(start_id=142)

    # First client gets #142 (matching user example)
    p1 = anon.get_pseudonym("Иванов Иван Иванович")
    assert p1 == "Клиент #142", f"Expected 'Клиент #142', got '{p1}'"

    # Same client receives identical pseudonym (consistency)
    p1_again = anon.get_pseudonym("Иванов Иван Иванович")
    assert p1_again == "Клиент #142", f"Expected 'Клиент #142', got '{p1_again}'"

    # Second client gets a new stable pseudonym
    p2 = anon.get_pseudonym("Петров Алексей")
    assert p2 != p1, f"Expected different pseudonym for second client, got {p2}"
    assert p2.startswith("Клиент #"), f"Expected pseudonym to start with 'Клиент #', got {p2}"

    # Text anonymization
    text = "Сделка по клиенту Иванов Иван Иванович на сумму 250 000 руб."
    anon_text = anon.anonymize_text(text)
    assert "Клиент #142" in anon_text, f"Expected 'Клиент #142' in text, got {anon_text}"
    assert "Иванов Иван Иванович" not in anon_text, f"Leaked real name in {anon_text}"

    print("✓ Client name pseudonymization tests passed!")


def test_record_and_messages_anonymization():
    anon = PIIAnonymizer(start_id=142)

    records = [
        {
            "client": "Иванов Иван Иванович",
            "contact": "+7 999 123-45-67",
            "amount": 150000,
            "status": "won"
        },
        {
            "client": "Сидорова Анна",
            "contact": "sidorova@mail.ru",
            "amount": 80000,
            "status": "in_progress"
        }
    ]

    cleaned_records = anon.anonymize_records(records)
    assert cleaned_records[0]["client"] == "Клиент #142"
    assert cleaned_records[0]["contact"] == "+7 999 ***-**-67"
    assert cleaned_records[1]["contact"] == "s***a@mail.ru"

    # Chat messages payload anonymization
    messages = [
        {"role": "system", "content": "You are a sales consultant."},
        {"role": "user", "content": "Покажи контакты клиента Иванов Иван Иванович (+7 999 123-45-67)"},
        {
            "role": "tool",
            "name": "execute_sql_query",
            "content": json.dumps({"rows": records}, ensure_ascii=False)
        }
    ]

    sanitized = anon.anonymize_messages(messages)
    # User message sanitized
    assert "+7 999 ***-**-67" in sanitized[1]["content"]
    assert "Клиент #142" in sanitized[1]["content"]
    assert "Иванов" not in sanitized[1]["content"]

    # Tool message JSON sanitized
    tool_json = json.loads(sanitized[2]["content"])
    assert tool_json["rows"][0]["client"] == "Клиент #142"
    assert tool_json["rows"][0]["contact"] == "+7 999 ***-**-67"

    print("✓ Records and messages anonymization tests passed!")


def test_tool_execution_anonymization():
    snap = Snapshot.objects.first()
    if not snap:
        print("Skipping DB tool test (no snapshot in DB)")
        return

    # Check that execute_tool_call anonymizes rows
    res = execute_tool_call("execute_sql_query", {"query": "SELECT client, contact, amount FROM deals LIMIT 5"}, str(snap.id))
    data = json.loads(res)
    if "rows" in data and data["rows"]:
        for r in data["rows"]:
            c = r.get("client")
            if c:
                assert c.startswith("Клиент #") or not c, f"Expected masked client name, got {c}"
            contact = r.get("contact")
            if contact and ("+7" in contact or "8" in contact):
                assert "***-**-" in contact or "***" in contact, f"Expected masked phone, got {contact}"

    print("✓ Tool execution output anonymization tests passed!")


if __name__ == '__main__':
    test_phone_masking()
    test_email_masking()
    test_client_name_pseudonymization()
    test_record_and_messages_anonymization()
    test_tool_execution_anonymization()
    print("\n🎉 ALL 152-ФЗ PII ANONYMIZATION TESTS PASSED SUCCESSFULLY!")
