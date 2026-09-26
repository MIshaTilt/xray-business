import datetime
import os
import yaml
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple, Optional
from .normalizer import NormalizedDeal


def get_thresholds():
    p = os.path.join(os.path.dirname(__file__), 'thresholds.yaml')
    with open(p, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def calculate_metrics_and_findings(deals: List[NormalizedDeal], mapping: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str], List[str]]:
    """
    Computes all 7 metrics according to Section 6.2 - 6.4 of the TZ.
    Returns:
       findings: list of critical / watch items (up to 3 sorted by financial impact)
       all_metrics: dict of metric_id -> detailed MetricResult
       ok_list: list of metric_ids in ok state
       low_sample_list: list of metric_ids with low sample
    """
    cfg = get_thresholds()
    now = datetime.datetime.now()

    def has_f(f: str) -> bool:
        return bool(mapping.get(f))

    # Ready check per TZ (with support for dynamically derived fields during normalization)
    has_disc_data = any(d.discount_pct is not None or d.list_price is not None for d in deals)
    has_first_contact = any(d.created_at and d.first_contact_at for d in deals)
    has_closed = any(d.created_at and d.closed_at for d in deals)

    available_map = {
        'speed_to_lead': (has_f('created_at') and has_f('first_contact_at')) or has_first_contact,
        'stagnation': has_f('status') and (has_f('status_changed_at') or has_f('created_at')),
        'discount_leakage': has_f('amount') and (has_f('discount_pct') or has_f('list_price') or has_disc_data),
        'sales_cycle': (has_f('created_at') and has_f('closed_at')) or has_closed,
        'key_account_risk': has_f('client') and has_f('status'),
        'dormant': has_f('client') and (has_f('last_activity_at') or has_f('created_at')),
        'funnel_dropoff': has_f('status') and has_f('amount'),
    }

    all_metrics: Dict[str, Any] = {}
    ok_list: List[str] = []
    low_sample_list: List[str] = []
    candidates: List[Dict[str, Any]] = []

    # 1. speed_to_lead
    if not available_map['speed_to_lead']:
        all_metrics['speed_to_lead'] = {
            'metric_id': 'speed_to_lead',
            'available': False,
            'missing_fields': [f for f in ['created_at', 'first_contact_at'] if not has_f(f)],
            'verdict': 'skipped',
            'value': None,
            'unit': 'hours',
            'money_impact': None,
            'threshold_label': 'быстрее 30 минут',
            'action': 'Отвечайте новым заявкам быстрее 30 минут',
            'evidence': []
        }
    else:
        diffs = []
        evidence = []
        for d in deals:
            if d.created_at and d.first_contact_at and d.first_contact_at >= d.created_at:
                delta_mins = (d.first_contact_at - d.created_at).total_seconds() / 60.0
                diffs.append(delta_mins)
                evidence.append({
                    'deal_id': d.deal_id,
                    'client': d.client,
                    'amount': f"{d.amount:.2f}",
                    'status': d.status,
                    'manager': d.manager,
                    'contact': d.contact,
                })
        if len(diffs) < cfg.get('min_sample', 5):
            low_sample_list.append('speed_to_lead')
            verdict = 'ok'
            med_hours = 0.0
        else:
            diffs.sort()
            med_mins = diffs[len(diffs) // 2]
            med_hours = round(med_mins / 60.0, 2)
            if med_mins > cfg['speed_to_lead']['critical_minutes']:
                verdict = 'critical'
            elif med_mins > cfg['speed_to_lead']['watch_minutes']:
                verdict = 'watch'
            else:
                verdict = 'ok'

        res = {
            'metric_id': 'speed_to_lead',
            'available': True,
            'missing_fields': [],
            'verdict': verdict,
            'value': med_hours,
            'unit': 'hours',
            'money_impact': None,
            'threshold_label': 'быстрее 30 минут',
            'action': f"Медиана первого контакта {med_hours} ч. Ответьте новым заявкам быстрее 30 минут",
            'evidence': evidence[:50]
        }
        all_metrics['speed_to_lead'] = res
        if verdict in ['critical', 'watch'] and 'speed_to_lead' not in low_sample_list:
            candidates.append(res)
        elif verdict == 'ok':
            ok_list.append('speed_to_lead')

    # Calculate won cycle median for stagnation
    won_cycle_days = []
    for d in deals:
        if d.status == 'won' and d.created_at and d.closed_at and d.closed_at >= d.created_at:
            won_cycle_days.append((d.closed_at - d.created_at).total_seconds() / 86400.0)

    if len(won_cycle_days) >= cfg.get('min_sample', 5):
        won_cycle_days.sort()
        med_cycle = won_cycle_days[len(won_cycle_days) // 2]
        stagnation_thresh = max(1.0, round(med_cycle * cfg['stagnation']['cycle_multiplier'], 1))
    else:
        stagnation_thresh = float(cfg['stagnation']['fallback_days'])

    # 2. stagnation
    if not available_map['stagnation']:
        all_metrics['stagnation'] = {
            'metric_id': 'stagnation',
            'available': False,
            'missing_fields': [f for f in ['status'] if not has_f(f)],
            'verdict': 'skipped',
            'value': None,
            'unit': 'deals',
            'money_impact': None,
            'threshold_label': f"Зависшей считаем сделку старше {int(stagnation_thresh)} дней",
            'action': 'Разморозьте зависшие сделки',
            'evidence': []
        }
    else:
        stale_deals = []
        total_stale_amount = Decimal('0.00')
        for d in deals:
            if d.status not in ['won', 'lost']:
                ref_dt = d.status_changed_at or d.created_at
                if ref_dt:
                    days_open = (now - ref_dt).total_seconds() / 86400.0
                    if days_open > stagnation_thresh:
                        stale_deals.append({
                            'deal_id': d.deal_id,
                            'client': d.client,
                            'amount': f"{d.amount:.2f}",
                            'status': d.status,
                            'days_stale': int(days_open),
                            'manager': d.manager,
                            'contact': d.contact,
                        })
                        total_stale_amount += d.amount

        if len(stale_deals) > 0:
            verdict = 'critical'
            res = {
                'metric_id': 'stagnation',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': len(stale_deals),
                'unit': 'deals',
                'money_impact': f"{total_stale_amount:.2f}",
                'threshold_label': f"Зависшей считаем сделку старше {int(stagnation_thresh)} дней",
                'action': f"Разморозьте {len(stale_deals)} сделок старше {int(stagnation_thresh)} дней на {int(total_stale_amount):,} руб.".replace(',', ' '),
                'evidence': stale_deals[:50]
            }
            candidates.append(res)
        else:
            verdict = 'ok'
            ok_list.append('stagnation')
            res = {
                'metric_id': 'stagnation',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': 0,
                'unit': 'deals',
                'money_impact': None,
                'threshold_label': f"Зависшей считаем сделку старше {int(stagnation_thresh)} дней",
                'action': 'Зависших сделок не обнаружено',
                'evidence': []
            }
        all_metrics['stagnation'] = res

    # 3. discount_leakage
    if not available_map['discount_leakage']:
        all_metrics['discount_leakage'] = {
            'metric_id': 'discount_leakage',
            'available': False,
            'missing_fields': [f for f in ['discount_pct', 'list_price'] if not has_f(f)],
            'verdict': 'skipped',
            'value': None,
            'unit': 'pct',
            'money_impact': None,
            'threshold_label': 'скидка больше 10%',
            'action': 'Контролируйте скидки при закрытии сделок',
            'evidence': []
        }
    else:
        won_deals = [d for d in deals if d.status == 'won']
        if len(won_deals) < cfg.get('min_sample', 5):
            low_sample_list.append('discount_leakage')
            verdict = 'ok'
            res = {
                'metric_id': 'discount_leakage',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': None,
                'unit': 'pct',
                'money_impact': None,
                'threshold_label': 'скидка больше 10%',
                'action': 'Слишком мало закрытых сделок для оценки скидок',
                'evidence': []
            }
        else:
            leaked = []
            total_leak_money = Decimal('0.00')
            has_price_count = 0
            for d in won_deals:
                disc = d.discount_pct
                if disc is None and d.list_price and d.list_price > 0:
                    disc = ((d.list_price - d.amount) / d.list_price) * Decimal(100)

                if disc is not None and disc > cfg['discount']['leak_discount_pct']:
                    leaked.append(d)
                    if d.list_price and d.list_price > d.amount:
                        total_leak_money += (d.list_price - d.amount)
                        has_price_count += 1

            share = round((len(leaked) / len(won_deals)), 2)
            share_pct = round(share * 100, 1)
            if share > cfg['discount']['critical_share']:
                verdict = 'critical'
            elif share > cfg['discount']['watch_share']:
                verdict = 'watch'
            else:
                verdict = 'ok'

            money_str = f"{total_leak_money:.2f}" if has_price_count > 0 else None
            evidence = [{
                'deal_id': d.deal_id,
                'client': d.client,
                'amount': f"{d.amount:.2f}",
                'status': d.status,
                'manager': d.manager,
                'contact': d.contact
            } for d in leaked[:50]]

            res = {
                'metric_id': 'discount_leakage',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': share_pct,
                'unit': 'pct',
                'money_impact': money_str,
                'threshold_label': 'скидка больше 10%',
                'action': f"{share_pct}% выигранных сделок ушли со скидкой больше 10%",
                'evidence': evidence
            }
            if verdict in ['critical', 'watch']:
                candidates.append(res)
            else:
                ok_list.append('discount_leakage')
        all_metrics['discount_leakage'] = res

    # 4. sales_cycle
    if not available_map['sales_cycle']:
        all_metrics['sales_cycle'] = {
            'metric_id': 'sales_cycle',
            'available': False,
            'missing_fields': [f for f in ['created_at', 'closed_at'] if not has_f(f)],
            'verdict': 'skipped',
            'value': None,
            'unit': 'days',
            'money_impact': None,
            'threshold_label': 'цикл вырос',
            'action': 'Сокращайте длительность цикла сделки',
            'evidence': []
        }
    else:
        valid_won = [d for d in deals if d.status == 'won' and d.created_at and d.closed_at and d.closed_at >= d.created_at]
        if len(valid_won) < cfg.get('min_sample', 5):
            low_sample_list.append('sales_cycle')
            verdict = 'ok'
            res = {
                'metric_id': 'sales_cycle',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': None,
                'unit': 'days',
                'money_impact': None,
                'threshold_label': 'цикл вырос',
                'action': 'Недостаточно данных для анализа цикла',
                'evidence': []
            }
        else:
            valid_won.sort(key=lambda x: x.created_at)
            mid = len(valid_won) // 2
            half1 = [(d.closed_at - d.created_at).total_seconds() / 86400.0 for d in valid_won[:mid]]
            half2 = [(d.closed_at - d.created_at).total_seconds() / 86400.0 for d in valid_won[mid:]]
            half1.sort()
            half2.sort()
            m1 = half1[len(half1)//2] if half1 else 0
            m2 = half2[len(half2)//2] if half2 else 0

            all_days = [(d.closed_at - d.created_at).total_seconds() / 86400.0 for d in valid_won]
            all_days.sort()
            med_all = round(all_days[len(all_days)//2], 1)

            if len(half1) >= 5 and len(half2) >= 5 and m1 > 0:
                growth = (m2 - m1) / m1
                if growth > cfg['sales_cycle']['critical_growth']:
                    verdict = 'critical'
                elif growth > 0:
                    verdict = 'watch'
                else:
                    verdict = 'ok'
            else:
                verdict = 'ok'

            res = {
                'metric_id': 'sales_cycle',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': med_all,
                'unit': 'days',
                'money_impact': None,
                'threshold_label': 'цикл вырос',
                'action': f"Цикл сделки вырос до {med_all} дней",
                'evidence': [{
                    'deal_id': d.deal_id,
                    'client': d.client,
                    'amount': f"{d.amount:.2f}",
                    'status': d.status,
                    'manager': d.manager,
                    'contact': d.contact
                } for d in valid_won[-50:]]
            }
            if verdict in ['critical', 'watch']:
                candidates.append(res)
            else:
                ok_list.append('sales_cycle')
        all_metrics['sales_cycle'] = res

    # 5. key_account_risk
    if not available_map['key_account_risk']:
        all_metrics['key_account_risk'] = {
            'metric_id': 'key_account_risk',
            'available': False,
            'missing_fields': [f for f in ['client', 'status'] if not has_f(f)],
            'verdict': 'skipped',
            'value': None,
            'unit': 'pct',
            'money_impact': None,
            'threshold_label': 'два клиента больше 50%',
            'action': 'Диверсифицируйте клиентскую базу',
            'evidence': []
        }
    else:
        won_with_client = [d for d in deals if d.status == 'won' and d.client]
        client_totals: Dict[str, Decimal] = {}
        total_won_amount = Decimal('0.00')
        for d in won_with_client:
            client_totals[d.client] = client_totals.get(d.client, Decimal('0.00')) + d.amount
            total_won_amount += d.amount

        if len(client_totals) < 2 or len(won_with_client) < cfg.get('min_sample', 5):
            low_sample_list.append('key_account_risk')
            verdict = 'ok'
            res = {
                'metric_id': 'key_account_risk',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': None,
                'unit': 'pct',
                'money_impact': None,
                'threshold_label': 'два клиента больше 50%',
                'action': 'Мало клиентов для анализа концентрации',
                'evidence': []
            }
        else:
            sorted_clients = sorted(client_totals.items(), key=lambda x: x[1], reverse=True)
            top2_sum = sorted_clients[0][1] + sorted_clients[1][1]
            top2_share = float(top2_sum / total_won_amount) if total_won_amount > 0 else 0
            share_pct = round(top2_share * 100, 1)

            if top2_share > cfg['key_account']['critical_share']:
                verdict = 'critical'
            elif top2_share > cfg['key_account']['watch_share']:
                verdict = 'watch'
            else:
                verdict = 'ok'

            top_clients_names = {sorted_clients[0][0], sorted_clients[1][0]}
            evidence = [{
                'deal_id': d.deal_id,
                'client': d.client,
                'amount': f"{d.amount:.2f}",
                'status': d.status,
                'manager': d.manager,
                'contact': d.contact
            } for d in won_with_client if d.client in top_clients_names][:50]

            res = {
                'metric_id': 'key_account_risk',
                'available': True,
                'missing_fields': [],
                'verdict': verdict,
                'value': share_pct,
                'unit': 'pct',
                'money_impact': f"{top2_sum:.2f}",
                'threshold_label': 'два клиента больше 50%',
                'action': f"Два клиента дают {share_pct}% выручки",
                'evidence': evidence
            }
            if verdict in ['critical', 'watch']:
                candidates.append(res)
            else:
                ok_list.append('key_account_risk')
        all_metrics['key_account_risk'] = res

    # 6. dormant
    if not available_map['dormant']:
        all_metrics['dormant'] = {
            'metric_id': 'dormant',
            'available': False,
            'missing_fields': [f for f in ['client'] if not has_f(f)],
            'verdict': 'skipped',
            'value': None,
            'unit': 'deals',
            'money_impact': None,
            'threshold_label': 'дольше 45 дней',
            'action': 'Свяжитесь с забытыми клиентами',
            'evidence': []
        }
    else:
        won_clients = {d.client for d in deals if d.status == 'won' and d.client}
        dormant_candidates = [d for d in deals if d.client and d.client not in won_clients]
        dormant_map: Dict[str, NormalizedDeal] = {}
        for d in dormant_candidates:
            ref_dt = d.last_activity_at or d.created_at
            if ref_dt and (now - ref_dt).total_seconds() / 86400.0 > cfg['dormant']['days']:
                dormant_map[d.client] = d

        dormant_list = list(dormant_map.values())
        dormant_amount = sum((d.amount for d in dormant_list), Decimal('0.00'))

        crit_rub = Decimal(str(cfg['dormant']['critical_rub']))
        crit_count = cfg['dormant']['critical_count']

        if len(dormant_list) >= crit_count or dormant_amount >= crit_rub:
            verdict = 'critical'
        elif len(dormant_list) > 0:
            verdict = 'watch'
        else:
            verdict = 'ok'

        evidence = [{
            'deal_id': d.deal_id,
            'client': d.client,
            'amount': f"{d.amount:.2f}",
            'status': d.status,
            'manager': d.manager,
            'contact': d.contact
        } for d in dormant_list[:50]]

        res = {
            'metric_id': 'dormant',
            'available': True,
            'missing_fields': [],
            'verdict': verdict,
            'value': len(dormant_list),
            'unit': 'deals',
            'money_impact': f"{dormant_amount:.2f}" if dormant_amount > 0 else None,
            'threshold_label': 'дольше 45 дней',
            'action': f"{len(dormant_list)} клиентов молчат дольше 45 дней",
            'evidence': evidence
        }
        if verdict in ['critical', 'watch']:
            candidates.append(res)
        else:
            ok_list.append('dormant')
        all_metrics['dormant'] = res

    # 7. funnel_dropoff
    if not available_map['funnel_dropoff']:
        all_metrics['funnel_dropoff'] = {
            'metric_id': 'funnel_dropoff',
            'available': False,
            'missing_fields': [f for f in ['status', 'amount'] if not has_f(f)],
            'verdict': 'skipped',
            'value': None,
            'unit': 'rub',
            'money_impact': None,
            'threshold_label': 'этап теряет больше 40% суммы',
            'action': 'Устраните потери на ключевом этапе воронки',
            'evidence': []
        }
    else:
        stages = cfg['funnel']['stages']
        stage_amounts = {st: Decimal('0.00') for st in stages}
        for d in deals:
            if d.status in stages:
                idx = stages.index(d.status)
                for i in range(idx + 1):
                    stage_amounts[stages[i]] += d.amount

        max_loss = Decimal('0.00')
        max_stage = ''
        loss_share = 0.0
        for i in range(len(stages) - 1):
            curr_s = stages[i]
            next_s = stages[i + 1]
            curr_amt = stage_amounts[curr_s]
            next_amt = stage_amounts[next_s]
            if curr_amt > 0:
                loss = curr_amt - next_amt
                share = float(loss / curr_amt)
                if loss > max_loss:
                    max_loss = loss
                    max_stage = curr_s
                    loss_share = share

        if max_loss > 0 and len(deals) >= cfg.get('min_sample', 5):
            if loss_share > cfg['funnel']['critical_loss_share']:
                verdict = 'critical'
            elif loss_share > cfg['funnel']['watch_loss_share']:
                verdict = 'watch'
            else:
                verdict = 'ok'
        else:
            verdict = 'ok'
            if len(deals) < cfg.get('min_sample', 5):
                low_sample_list.append('funnel_dropoff')

        evidence = [{
            'deal_id': d.deal_id,
            'client': d.client,
            'amount': f"{d.amount:.2f}",
            'status': d.status,
            'manager': d.manager,
            'contact': d.contact
        } for d in deals if d.status == max_stage][:50]

        res = {
            'metric_id': 'funnel_dropoff',
            'available': True,
            'missing_fields': [],
            'verdict': verdict,
            'value': round(loss_share * 100, 1),
            'unit': 'pct',
            'money_impact': f"{max_loss:.2f}" if max_loss > 0 else None,
            'threshold_label': 'этап теряет больше 40% суммы',
            'action': f"На этапе «{max_stage}» теряется {int(max_loss):,} руб.".replace(',', ' '),
            'evidence': evidence
        }
        if verdict in ['critical', 'watch'] and 'funnel_dropoff' not in low_sample_list:
            candidates.append(res)
        else:
            ok_list.append('funnel_dropoff')
        all_metrics['funnel_dropoff'] = res

    # Sort candidates for top-3 findings per TZ §6.3:
    # 1. money_impact DESC (None at end)
    # 2. verdict critical before watch
    # 3. metric_id ASC
    def sort_key(item):
        mi = item['money_impact']
        val = Decimal(mi) if mi else Decimal('-1')
        v_rank = 0 if item['verdict'] == 'critical' else 1
        return (-val, v_rank, item['metric_id'])

    candidates.sort(key=sort_key)
    findings = candidates[:3]

    return findings, all_metrics, ok_list, low_sample_list
