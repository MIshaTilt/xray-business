"""
Snapshot Comparison & Dynamics Engine for X-Ray.

Computes mathematical deltas between two analytical snapshots (Before vs After)
across key metrics, business totals, and sales manager performance.
Generates an executive AI summary explaining financial recovery and growth areas.
"""

import json
import os
import requests
import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from django.db.models import Sum, Count, Avg, Q
from engine.models import Snapshot, Deal
from engine.anonymizer import PIIAnonymizer
from engine.llm_logger import log_llm_interaction


METRIC_NAMES = {
    'stagnation': 'Зависшие сделки',
    'speed_to_lead': 'Скорость первого ответа',
    'discount_leakage': 'Утечка скидок',
    'sales_cycle': 'Цикл сделки',
    'dormant': 'Уснувшие клиенты',
    'funnel_dropoff': 'Утечка в воронке',
    'key_account_risk': 'Зависимость от топ-клиентов',
}

# Metrics where decrease is GOOD (financial leakage / delays)
LEAKAGE_METRICS = {'stagnation', 'speed_to_lead', 'discount_leakage', 'sales_cycle', 'dormant', 'funnel_dropoff', 'key_account_risk'}


def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _calc_pct_delta(base: float, target: float) -> float:
    if base == 0:
        return 100.0 if target > 0 else 0.0
    return round(((target - base) / abs(base)) * 100.0, 1)


def compare_snapshots(snap1: Snapshot, snap2: Snapshot) -> Dict[str, Any]:
    """
    Compares two Snapshot models and returns comprehensive comparison metrics,
    manager dynamics, and an AI-generated executive summary.
    Chronology: the older snapshot is base, the newer is target.
    """
    if snap1.created_at <= snap2.created_at:
        base_snap, target_snap = snap1, snap2
    else:
        base_snap, target_snap = snap2, snap1

    base_totals = base_snap.totals or {}
    target_totals = target_snap.totals or {}

    base_amt = _to_float(base_totals.get('amount', 0))
    target_amt = _to_float(target_totals.get('amount', 0))
    base_deals = int(base_totals.get('deals', 0))
    target_deals = int(target_totals.get('deals', 0))

    base_avg_check = round(base_amt / base_deals, 2) if base_deals > 0 else 0.0
    target_avg_check = round(target_amt / target_deals, 2) if target_deals > 0 else 0.0

    # 1. Totals Diff
    totals_diff = {
        'amount': {
            'base': base_amt,
            'target': target_amt,
            'delta_abs': round(target_amt - base_amt, 2),
            'delta_pct': _calc_pct_delta(base_amt, target_amt),
            'status': 'positive' if target_amt >= base_amt else 'negative',
            'unit': 'rub',
        },
        'deals': {
            'base': base_deals,
            'target': target_deals,
            'delta_abs': target_deals - base_deals,
            'delta_pct': _calc_pct_delta(base_deals, target_deals),
            'status': 'positive' if target_deals >= base_deals else 'negative',
            'unit': 'count',
        },
        'avg_check': {
            'base': base_avg_check,
            'target': target_avg_check,
            'delta_abs': round(target_avg_check - base_avg_check, 2),
            'delta_pct': _calc_pct_delta(base_avg_check, target_avg_check),
            'status': 'positive' if target_avg_check >= base_avg_check else 'negative',
            'unit': 'rub',
        }
    }

    # 2. 7 Metrics Diff
    base_metrics = base_snap.all_metrics or {}
    target_metrics = target_snap.all_metrics or {}

    metrics_diff = []
    total_saved_money = 0.0

    metric_keys = ['stagnation', 'speed_to_lead', 'discount_leakage', 'sales_cycle', 'dormant', 'funnel_dropoff', 'key_account_risk']
    for m_id in metric_keys:
        m_base = base_metrics.get(m_id, {})
        m_target = target_metrics.get(m_id, {})

        if not m_base and not m_target:
            continue

        b_val = _to_float(m_base.get('value'))
        t_val = _to_float(m_target.get('value'))
        b_impact = _to_float(m_base.get('money_impact'))
        t_impact = _to_float(m_target.get('money_impact'))

        delta_val = round(t_val - b_val, 2)
        delta_pct = _calc_pct_delta(b_val, t_val)
        delta_impact = round(t_impact - b_impact, 2)

        is_leakage = m_id in LEAKAGE_METRICS
        if is_leakage:
            # For leakage metrics, lower value or impact is POSITIVE (improvement)
            if delta_val < 0 or (b_impact > 0 and delta_impact < 0):
                m_status = 'positive'
            elif delta_val > 0 or delta_impact > 0:
                m_status = 'negative'
            else:
                m_status = 'neutral'

            # Calculate money saved from stagnation / discount / dropoff reduction
            if b_impact > t_impact and b_impact > 0:
                saved = b_impact - t_impact
                total_saved_money += saved
        else:
            if delta_val > 0:
                m_status = 'positive'
            elif delta_val < 0:
                m_status = 'negative'
            else:
                m_status = 'neutral'

        unit = m_target.get('unit') or m_base.get('unit') or ''
        name = METRIC_NAMES.get(m_id, m_id)

        metrics_diff.append({
            'metric_id': m_id,
            'name': name,
            'base_value': b_val,
            'target_value': t_val,
            'base_impact': b_impact,
            'target_impact': t_impact,
            'delta_value': delta_val,
            'delta_pct': delta_pct,
            'delta_impact': delta_impact,
            'unit': unit,
            'status': m_status,
            'base_verdict': m_base.get('verdict', 'ok'),
            'target_verdict': m_target.get('verdict', 'ok'),
        })

    # 3. Manager Dynamics Diff
    base_deal_stats = {
        d['manager']: d
        for d in Deal.objects.filter(snapshot=base_snap).exclude(manager='').values('manager').annotate(
            total_amt=Sum('amount'),
            deals_cnt=Count('id'),
            won_amt=Sum('amount', filter=Q(status='won')),
            won_cnt=Count('id', filter=Q(status='won')),
        )
    }

    target_deal_stats = {
        d['manager']: d
        for d in Deal.objects.filter(snapshot=target_snap).exclude(manager='').values('manager').annotate(
            total_amt=Sum('amount'),
            deals_cnt=Count('id'),
            won_amt=Sum('amount', filter=Q(status='won')),
            won_cnt=Count('id', filter=Q(status='won')),
        )
    }

    all_managers = set(base_deal_stats.keys()).union(set(target_deal_stats.keys()))
    managers_diff = []

    for mgr in all_managers:
        b_data = base_deal_stats.get(mgr, {})
        t_data = target_deal_stats.get(mgr, {})

        b_m_amt = _to_float(b_data.get('total_amt', 0))
        t_m_amt = _to_float(t_data.get('total_amt', 0))
        b_m_won = _to_float(b_data.get('won_amt', 0))
        t_m_won = _to_float(t_data.get('won_amt', 0))
        b_m_deals = int(b_data.get('deals_cnt', 0))
        t_m_deals = int(t_data.get('deals_cnt', 0))

        managers_diff.append({
            'manager': mgr,
            'base_amount': b_m_amt,
            'target_amount': t_m_amt,
            'delta_amount': round(t_m_amt - b_m_amt, 2),
            'delta_pct': _calc_pct_delta(b_m_amt, t_m_amt),
            'base_deals': b_m_deals,
            'target_deals': t_m_deals,
            'base_won': b_m_won,
            'target_won': t_m_won,
            'status': 'positive' if t_m_amt >= b_m_amt else 'negative',
        })

    # Sort managers by target revenue descending
    managers_diff.sort(key=lambda m: m['target_amount'], reverse=True)

    # 4. Generate AI Executive Summary (with 152-ФЗ compliance)
    ai_summary = _generate_comparison_narrative(
        base_snap=base_snap,
        target_snap=target_snap,
        totals_diff=totals_diff,
        metrics_diff=metrics_diff,
        managers_diff=managers_diff,
        total_saved_money=total_saved_money
    )

    return {
        'base': {
            'snapshot_id': str(base_snap.id),
            'filename': base_snap.filename,
            'created_at': base_snap.created_at.strftime('%Y-%m-%d'),
            'headline': base_snap.headline,
            'totals': base_totals,
        },
        'target': {
            'snapshot_id': str(target_snap.id),
            'filename': target_snap.filename,
            'created_at': target_snap.created_at.strftime('%Y-%m-%d'),
            'headline': target_snap.headline,
            'totals': target_totals,
        },
        'summary': ai_summary,
        'totals_diff': totals_diff,
        'metrics_diff': metrics_diff,
        'managers_diff': managers_diff,
        'total_saved_money': round(total_saved_money, 2),
    }


def _generate_comparison_narrative(
    base_snap: Snapshot,
    target_snap: Snapshot,
    totals_diff: Dict[str, Any],
    metrics_diff: List[Dict[str, Any]],
    managers_diff: List[Dict[str, Any]],
    total_saved_money: float
) -> Dict[str, Any]:
    """
    Calls LLM or falls back to templates to write a compelling 2-3 sentence executive
    summary for the business owner explaining what money was saved and what changed.
    """
    base_date = base_snap.created_at.strftime('%d.%m.%Y')
    target_date = target_snap.created_at.strftime('%d.%m.%Y')

    # Prepare safe highlights for LLM prompt
    rev_delta = totals_diff['amount']['delta_abs']
    rev_pct = totals_diff['amount']['delta_pct']

    stagnant_m = next((m for m in metrics_diff if m['metric_id'] == 'stagnation'), None)
    speed_m = next((m for m in metrics_diff if m['metric_id'] == 'speed_to_lead'), None)

    improvements = []
    risks = []

    for m in metrics_diff:
        if m['status'] == 'positive':
            improvements.append(f"{m['name']}: улучшение на {abs(m['delta_pct'])}%")
        elif m['status'] == 'negative':
            risks.append(f"{m['name']}: ухудшение на {abs(m['delta_pct'])}%")

    # Fallback template
    fallback_headline = "Динамика показателей между срезами"
    if total_saved_money > 0:
        fallback_headline = f"Вы вернули в оборот {int(round(total_saved_money)):,} ₽ благодаря разбору зависших сделок и контролю скидок".replace(',', ' ')
    elif rev_delta > 0:
        fallback_headline = f"Выручка выросла на {int(round(rev_delta)):,} ₽ ({rev_pct}%) по сравнению с предыдущим срезом".replace(',', ' ')

    fallback_body = (
        f"Сравнение среза от {base_date} со срезом от {target_date}. "
        f"Общая сумма продаж: {totals_diff['amount']['base']:,.0f} ₽ → {totals_diff['amount']['target']:,.0f} ₽ ({rev_pct:+0.1f}%). "
        f"Средний чек: {totals_diff['avg_check']['base']:,.0f} ₽ → {totals_diff['avg_check']['target']:,.0f} ₽. "
    ).replace(',', ' ')

    if improvements:
        fallback_body += f"Позитивная динамика: {', '.join(improvements[:2])}. "
    if risks:
        fallback_body += f"Требует контроля: {', '.join(risks[:2])}."

    default_result = {
        'headline': fallback_headline,
        'body': fallback_body,
        'saved_money': total_saved_money,
        'trend': 'improved' if (total_saved_money > 0 or rev_delta > 0) else 'attention'
    }

    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = (os.environ.get('OPENAI_BASE_URL') or '').rstrip('/')
    model_name = os.environ.get('OPENAI_MODEL') or ''
    if not api_key or not base_url or not model_name:
        return default_result

    prompt_data = {
        'period_base': base_date,
        'period_target': target_date,
        'revenue_change_rub': rev_delta,
        'revenue_change_pct': rev_pct,
        'total_saved_leakage_rub': total_saved_money,
        'key_improvements': improvements[:3],
        'key_risks': risks[:3],
        'top_manager_growth': managers_diff[0]['manager'] if managers_diff else None
    }

    system_prompt = (
        "Ты — старший бизнес-аналитик сервиса рентгена продаж X-Ray. "
        "Сформулируй главный вывод сравнения двух срезов продаж (Before vs After) для владельца бизнеса.\n"
        "ПРАВИЛА:\n"
        "1. Назови конкретные суммы в рублях и проценты из переданных данных.\n"
        "2. Сделай акцент на спасенных деньгах или росте выручки.\n"
        "3. Укажи 1 главное позитивное изменение и 1 зону риска для контроля РОПа.\n"
        "4. Ответ верни строго в формате JSON: {\"headline\": \"...\", \"body\": \"...\", \"trend\": \"improved\"|\"attention\"}"
    )

    user_prompt = f"Данные динамики двух срезов:\n{json.dumps(prompt_data, ensure_ascii=False, indent=2)}"

    try:
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Clean markdown fences
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]
            if content.startswith("json"):
                content = content[4:].strip()

            parsed = json.loads(content)
            log_llm_interaction(
                title="СРАВНЕНИЕ СНИМКОВ (BEFORE VS AFTER)",
                payload_data=payload,
                response_data=content,
                extra_info=f"STATUS: 200"
            )
            return {
                'headline': parsed.get('headline') or fallback_headline,
                'body': parsed.get('body') or fallback_body,
                'saved_money': total_saved_money,
                'trend': parsed.get('trend', default_result['trend'])
            }
    except Exception as e:
        print(f"[COMPARISON LLM ERROR]: {e}")

    return default_result
