"""
Генератор синтетических/фейковых данных для маппинга в AI Business X-Ray.
Архетип: E-commerce / Розница (Retail).

Особенности:
- Генерирует данные заказов/продаж с типичными паттернами E-commerce:
  быстрый цикл сделки, статусы заказов, скидки, каналы продаж, когорты клиентов,
  повторные покупки (LTV), возвраты и отмены.
- Поддерживает различные варианты наименования колонок и форматов (для тестирования смарт-маппинга):
  1) Standard / Canonical (соответствует канонической модели: order_id, customer_name, amount, discount, status, created_at, etc.)
  2) 1C / MoySklad style (русскоязычные заголовки: "Номер заказа", "Контрагент", "Сумма с НДС", "Скидка %", "Статус отгрузки", "Дата")
  3) Wildberries / Ozon / Marketplace style (русскоязычные маркетплейсные поля: "ID отправления", "Покупатель", "Выручка", "Комиссия / Скидка", "Текущий статус", "Дата заказа")
  4) Messy / Google Sheets style (смешанные названия, разнородные форматы дат, телефоны, комментарии)
"""

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

fake_ru = Faker("ru_RU")

# Категории и товары для E-commerce
PRODUCTS = [
    ("Беспроводные наушники X-Sound Pro", "Электроника", 3500, 7500),
    ("Умные часы FitPulse Max", "Электроника", 4200, 11900),
    ("Пауэрбанк 20000 mAh FastCharge", "Электроника", 1800, 3900),
    ("Чехол для смартфона силиконовый", "Аксессуары", 300, 900),
    ("Кабель USB-C - Lightning нейлон 1.5м", "Аксессуары", 450, 1200),
    ("Защитное стекло Premium 9D", "Аксессуары", 250, 700),
    ("Худи оверсайз хлопок", "Одежда", 2800, 5900),
    ("Футболка базовая оверсайз", "Одежда", 900, 2200),
    ("Кроссовки городские демисезон", "Обувь", 3900, 8900),
    ("Рюкзак городской водонепроницаемый", "Аксессуары", 2400, 5500),
    ("Увлажнитель воздуха ультразвуковой", "Товары для дома", 1900, 4800),
    ("Светодиодная лампа с диммером", "Товары для дома", 1200, 2900),
    ("Термокружка вакуумная 500мл", "Товары для дома", 800, 1950),
    ("Набор органической косметики CareSet", "Красота и уход", 1500, 3700),
    ("Крем восстанавливающий SPF 50", "Красота и уход", 750, 1800),
]

PAYMENT_METHODS = ["СБП", "Банковская карта", "При получении", "Долями / Сплит", "Безналичный расчет (юрлицо)"]
DELIVERY_METHODS = ["Курьер", "СДЭК ПВЗ", "Яндекс Доставка", "Самовывоз из магазина", "Почта России"]
SALES_CHANNELS = ["Сайт (интернет-магазин)", "Wildberries", "Ozon", "Авито", "VK Маркет", "Розничный магазин (офлайн)"]
CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", "Краснодар", "Самара", "Ростов-на-Дону"]
MANAGERS = ["Анна Смирнова", "Дмитрий Ковалев", "Елена Васильева", "Максим Романов", "Ольга Кузнецова", "Онлайн-автоматизация"]

ORDER_STATUSES = [
    ("Доставлен и оплачен", 0.65),
    ("В обработке", 0.08),
    ("Передан в доставку", 0.10),
    ("Ожидает оплаты", 0.05),
    ("Возврат", 0.05),
    ("Отменен клиентом", 0.07),
]


def weighted_choice(choices):
    items, weights = zip(*choices)
    return random.choices(items, weights=weights, k=1)[0]


def generate_base_customers(num_customers=100):
    customers = []
    for cid in range(1, num_customers + 1):
        customers.append({
            "customer_id": f"CUST-{cid:04d}",
            "name": fake_ru.name(),
            "phone": fake_ru.phone_number(),
            "email": fake_ru.free_email(),
            "city": random.choice(CITIES),
            "created_at": fake_ru.date_time_between(start_date="-180d", end_date="-60d"),
        })
    return customers


def generate_ecommerce_orders(
    count=500,
    num_customers=120,
    days_back=90,
    anomaly_discounts=False,
    anomaly_returns=False
):
    """
    Генерирует связный набор данных розничных продаж / интернет-магазина.
    Поддерживает инъекцию проблем бизнеса (для рентгена):
    - Слишком большие скидки (Discount leakage)
    - Всплеск возвратов/отмен
    """
    customers = generate_base_customers(num_customers)
    orders = []

    now = datetime.now()
    start_date = now - timedelta(days=days_back)

    for i in range(1, count + 1):
        # 40% заказов - повторные клиенты (LTV / Retention)
        if random.random() < 0.40:
            cust = random.choice(customers)
        else:
            cust = {
                "customer_id": f"CUST-NEW-{i:04d}",
                "name": fake_ru.name(),
                "phone": fake_ru.phone_number(),
                "email": fake_ru.free_email(),
                "city": random.choice(CITIES),
                "created_at": None,
            }

        product, category, min_price, max_price = random.choice(PRODUCTS)
        qty = random.choices([1, 2, 3, 4, 5], weights=[0.70, 0.18, 0.07, 0.03, 0.02])[0]
        base_unit_price = round(random.uniform(min_price, max_price) / 50) * 50
        gross_amount = base_unit_price * qty

        # Скидки: если активирована аномалия - скидки доходят до 40-50% без причины
        if anomaly_discounts and random.random() < 0.4:
            discount_pct = random.choice([20, 25, 30, 40, 50])
        else:
            discount_pct = random.choices([0, 3, 5, 10, 15], weights=[0.45, 0.20, 0.20, 0.10, 0.05])[0]

        discount_amount = round(gross_amount * (discount_pct / 100))
        final_amount = gross_amount - discount_amount

        # Время заказа
        order_time = fake_ru.date_time_between(start_date=start_date, end_date=now)

        # Время первого ответа/обработки (Speed to lead)
        # 15% заказов с задержкой более 40 минут
        if random.random() < 0.2:
            response_minutes = random.randint(45, 240)
        else:
            response_minutes = random.randint(2, 25)
        first_contact_time = order_time + timedelta(minutes=response_minutes)

        channel = random.choice(SALES_CHANNELS)
        manager = random.choice(MANAGERS) if channel not in ["Wildberries", "Ozon"] else "Онлайн-автоматизация"

        status = weighted_choice(ORDER_STATUSES)
        if anomaly_returns and random.random() < 0.25:
            status = random.choice(["Возврат", "Отменен клиентом"])

        orders.append({
            "order_id": f"ORD-{order_time.strftime('%Y%m')}-{i:04d}",
            "order_date": order_time,
            "first_contact_date": first_contact_time,
            "response_minutes": response_minutes,
            "customer_id": cust["customer_id"],
            "customer_name": cust["name"],
            "customer_phone": cust["phone"],
            "customer_email": cust["email"],
            "customer_city": cust["city"],
            "product_name": product,
            "product_category": category,
            "quantity": qty,
            "unit_price": base_unit_price,
            "gross_amount": gross_amount,
            "discount_pct": discount_pct,
            "discount_amount": discount_amount,
            "net_amount": final_amount,
            "status": status,
            "payment_method": random.choice(PAYMENT_METHODS),
            "delivery_method": random.choice(DELIVERY_METHODS),
            "sales_channel": channel,
            "manager": manager,
        })

    # Сортируем по дате
    orders.sort(key=lambda x: x["order_date"])
    return orders


def export_canonical(orders, output_path: Path):
    """
    Экспорт в стандартный/канонический формат (английские поля в snake_case).
    """
    fieldnames = [
        "order_id",
        "order_date",
        "first_response_time",
        "response_delay_minutes",
        "customer_id",
        "customer_name",
        "phone",
        "email",
        "city",
        "channel",
        "manager",
        "product_name",
        "category",
        "quantity",
        "unit_price",
        "discount_amount",
        "total_amount",
        "status",
        "payment_type",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for o in orders:
            writer.writerow({
                "order_id": o["order_id"],
                "order_date": o["order_date"].strftime("%Y-%m-%d %H:%M:%S"),
                "first_response_time": o["first_contact_date"].strftime("%Y-%m-%d %H:%M:%S"),
                "response_delay_minutes": o["response_minutes"],
                "customer_id": o["customer_id"],
                "customer_name": o["customer_name"],
                "phone": o["customer_phone"],
                "email": o["customer_email"],
                "city": o["customer_city"],
                "channel": o["sales_channel"],
                "manager": o["manager"],
                "product_name": o["product_name"],
                "category": o["product_category"],
                "quantity": o["quantity"],
                "unit_price": o["unit_price"],
                "discount_amount": o["discount_amount"],
                "total_amount": o["net_amount"],
                "status": o["status"],
                "payment_type": o["payment_method"],
            })


def export_moysklad_1c(orders, output_path: Path):
    """
    Экспорт в стиле выгрузки из МойСклад / 1С (русские заголовки, разделители, формат цен).
    Идеально для тестирования авто-маппинга полей.
    """
    fieldnames = [
        "Номер заказа",
        "Дата и время создания",
        "Контрагент (Покупатель)",
        "Телефон покупателя",
        "Email",
        "Город доставки",
        "Товар / Номенклатура",
        "Группа товаров",
        "Кол-во",
        "Цена без скидки (руб.)",
        "Скидка клиента (руб)",
        "Сумма документа (Итого)",
        "Статус заказа",
        "Способ оплаты",
        "Канал сбыта",
        "Ответственный менеджер",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for o in orders:
            writer.writerow({
                "Номер заказа": o["order_id"].replace("ORD-", "MS-"),
                "Дата и время создания": o["order_date"].strftime("%d.%m.%Y %H:%M"),
                "Контрагент (Покупатель)": o["customer_name"],
                "Телефон покупателя": o["customer_phone"],
                "Email": o["customer_email"],
                "Город доставки": o["customer_city"],
                "Товар / Номенклатура": o["product_name"],
                "Группа товаров": o["product_category"],
                "Кол-во": o["quantity"],
                "Цена без скидки (руб.)": f"{o['unit_price']:.2f}".replace(".", ","),
                "Скидка клиента (руб)": f"{o['discount_amount']:.2f}".replace(".", ","),
                "Сумма документа (Итого)": f"{o['net_amount']:.2f}".replace(".", ","),
                "Статус заказа": o["status"],
                "Способ оплаты": o["payment_method"],
                "Канал сбыта": o["sales_channel"],
                "Ответственный менеджер": o["manager"],
            })


def export_marketplace_style(orders, output_path: Path):
    """
    Экспорт в стиле отчета маркетплейсов (Wildberries / Ozon).
    Проверяет сценарий маппинга специфических колонок e-commerce.
    """
    fieldnames = [
        "ID отправления",
        "Дата оформления",
        "Клиент",
        "Телефон",
        "Наименование артикула",
        "Категория каталога",
        "Количество штук",
        "Розничная цена",
        "Скидка продавца, руб.",
        "К перечислению (Выручка)",
        "Текущее состояние",
        "Склад / Канал",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for o in orders:
            writer.writerow({
                "ID отправления": o["order_id"].replace("ORD-", "WB-"),
                "Дата оформления": o["order_date"].strftime("%Y-%m-%d"),
                "Клиент": o["customer_name"],
                "Телефон": o["customer_phone"],
                "Наименование артикула": o["product_name"],
                "Категория каталога": o["product_category"],
                "Количество штук": o["quantity"],
                "Розничная цена": o["unit_price"],
                "Скидка продавца, руб.": o["discount_amount"],
                "К перечислению (Выручка)": o["net_amount"],
                "Текущее состояние": o["status"],
                "Склад / Канал": o["sales_channel"],
            })


def export_messy_table(orders, output_path: Path):
    """
    Экспорт в виде «грязной» таблицы предпринимателя (разные форматы дат, пустые ячейки,
    нестандартные заголовки вроде "Чек", "Кто купил", "Когда", "Сколько уступили").
    """
    fieldnames = [
        "Код",
        "Когда",
        "Кто купил",
        "Контакт",
        "Что заказали",
        "Шт",
        "Прайс",
        "Скинули",
        "ИТОГО к оплате",
        "Стадия",
        "Точка продажи",
    ]

    date_formats = [
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for o in orders:
            dt_fmt = random.choice(date_formats)
            contact = o["customer_phone"] if random.random() > 0.3 else o["customer_email"]
            # Иногда пропускаем скидку или телефон
            discount = o["discount_amount"] if o["discount_amount"] > 0 else ""
            
            writer.writerow({
                "Код": o["order_id"],
                "Когда": o["order_date"].strftime(dt_fmt),
                "Кто купил": o["customer_name"] if random.random() > 0.05 else "",
                "Контакт": contact,
                "Что заказали": o["product_name"],
                "Шт": o["quantity"],
                "Прайс": o["gross_amount"],
                "Скинули": discount,
                "ИТОГО к оплате": o["net_amount"],
                "Стадия": o["status"],
                "Точка продажи": o["sales_channel"],
            })


def main():
    parser = argparse.ArgumentParser(description="Генератор тестовых данных E-commerce/Розница для маппинга.")
    parser.add_argument("--count", type=int, default=300, help="Количество записей (заказов)")
    parser.add_argument("--output-dir", type=str, default="./data", help="Папка для сохранения CSV файлов")
    parser.add_argument("--anomaly-discounts", action="store_true", help="Внедрить проблему утечки маржи через скидки")
    parser.add_argument("--anomaly-returns", action="store_true", help="Внедрить проблему высокого процента возвратов/отмен")
    parser.add_argument("--format", type=str, default="all", choices=["all", "canonical", "moysklad", "marketplace", "messy"],
                        help="Формат выгрузки для тестирования смарт-маппинга")

    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Генерация {args.count} заказов (E-commerce / Розница)...")
    orders = generate_ecommerce_orders(
        count=args.count,
        num_customers=max(20, args.count // 3),
        days_back=90,
        anomaly_discounts=args.anomaly_discounts,
        anomaly_returns=args.anomaly_returns,
    )

    if args.format in ["all", "canonical"]:
        p = out_dir / "ecommerce_canonical.csv"
        export_canonical(orders, p)
        print(f"  -> Сохранен канонический файл: {p}")

    if args.format in ["all", "moysklad"]:
        p = out_dir / "ecommerce_moysklad_1c.csv"
        export_moysklad_1c(orders, p)
        print(f"  -> Сохранен файл в стиле МойСклад/1С (разделитель ';', кириллица): {p}")

    if args.format in ["all", "marketplace"]:
        p = out_dir / "ecommerce_marketplace.csv"
        export_marketplace_style(orders, p)
        print(f"  -> Сохранен файл маркетплейса (WB/Ozon): {p}")

    if args.format in ["all", "messy"]:
        p = out_dir / "ecommerce_messy_user_table.csv"
        export_messy_table(orders, p)
        print(f"  -> Сохранен файл 'грязной' таблицы пользователя: {p}")

    print("Генерация успешно завершена.")


if __name__ == "__main__":
    main()
