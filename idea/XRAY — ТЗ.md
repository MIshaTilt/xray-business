# X-Ray — техническое задание

Версия: 2.2  
Основание: `XRAY — расширенная концепция.md`  
Платформа: **мини-приложение MAX**. Бот существует только как кнопка запуска приложения.  
Бэкенд: **Django + Django REST Framework**

Смежные документы:

- `XRAY — расширенная концепция.md` — продуктовый смысл и обоснование. Где концепция описывает чат как канал продукта (демо, файл, заключение в ленте), **это ТЗ главнее**.
- `XRAY — идеи улучшений.md` — необязательные надстройки. В MVP этого ТЗ они **не входят**.

### Что изменилось в 2.0

Весь продукт живёт в мини-приложении. Бот не принимает файлы, не считает демо, не отдаёт шаблон и не присылает диагноз. Его единственная работа — открыть мини-приложение.

| Было в 1.0 | Стало в 2.0 |
|------------|-------------|
| Чат-бот + мини-приложение, два входа | Один вход: мини-приложение |
| Файл можно бросить в чат | Файл загружается только в мини-приложении |
| Демо и шаблон — кнопки бота | Демо и шаблон — действия на Home |
| «Прислать заключение в чат» | «Скопировать заключение» внутри мини-приложения |
| `start_param` открывает снимок или маппинг из чата | Бот не передаёт `start_param`. Старт всегда с Home |
| Модуль бота с командами и обработчиками файлов | Тонкий лаунчер: одно сообщение и кнопка `open_app` |

В 2.1 добавлена история сканов: список сессий и вход в любую без повторного расчёта (§4.4, §9.7).

В 2.2 закрыты дыры, без которых разработчик додумывает поведение: правила движка и пороги (§6.3–§6.5), разбор файла и маппинг (§6.6), единый формат ошибок и денег (§9.0), подпись initData и кнопка `open_app` (§8.3, §8.6).

---

## 1. Общие сведения

### 1.1. Название

**X-Ray** — рентген продаж малого бизнеса.

### 1.2. Назначение

Сервис принимает таблицу сделок пользователя (CSV/XLSX), приводит её к канонической схеме, считает 7 метрик архетипа «сделки / B2B / услуги» и выдаёт диагноз простым языком: где теряются деньги и что сделать на этой неделе.

### 1.3. Цель MVP

Один полный сценарий в мини-приложении MAX:

открыть приложение → загрузить файл (или открыть демо, или скачать шаблон) → подтвердить колонки → получить диагноз → увидеть список конкретных сделок → скопировать заключение.

### 1.4. Границы MVP

Входит:

- архетип «сделочный B2B / услуги»;
- 7 метрик с деградацией при нехватке колонок;
- эвристический маппинг колонок + ручное подтверждение;
- мини-приложение MAX со всеми экранами продукта;
- бот-лаунчер: одно приглашение и кнопка «Открыть X-Ray»;
- бэкенд Django, PostgreSQL, Docker Compose;
- синтетический демо-набор;
- скачивание шаблона таблицы из мини-приложения;
- копирование текста заключения в буфер;
- история сканов и повторное открытие любой сессии.

Не входит:

- продуктовый диалог в боте;
- команды бота кроме запуска приложения;
- приём файла в чат;
- отправка диагноза, демо или шаблона сообщением бота;
- интеграции amoCRM / Битрикс24 / 1С по API;
- архетипы e-commerce и подписок;
- LLM как обязательный путь (ключ опционален, без него система работает);
- роли директор / РОП / менеджер;
- прогнозирование и ML;
- отдельный сайт вне MAX.

### 1.5. Пользователь

Владелец или коммерческий директор компании 5–50 человек. Идентификация только через MAX (`user.id` из initData мини-приложения). Отдельной регистрации нет. События бота пользователя не создают и файлы не привязывают.

### 1.6. Роли поверхностей

| Поверхность | Делает | Не делает |
|-------------|--------|-----------|
| Бот | Показывает кнопку, которая открывает мини-приложение | Не считает, не хранит файлы, не показывает диагноз |
| Мини-приложение | Весь сценарий: файл, шаблон, демо, маппинг, диагноз, сделки, копирование заключения | Не зависит от сообщений в чате |

---

## 2. Термины

| Термин | Значение |
|--------|----------|
| Снимок (snapshot) | Результат одного рентгена конкретной выгрузки |
| Сессия | Тот же снимок в истории. Отдельной таблицы нет |
| Канон | Внутренняя схема сделки `Deal` |
| Маппинг | Соответствие колонок файла полям канона |
| Покрытие | Какие из 7 метрик можно посчитать на текущем маппинге |
| Вердикт | `ok` / `watch` / `critical` / `skipped` |
| initData | Строка MAX Bridge, подпись проверяется на сервере |
| Демо | Встроенный CSV, путь проверки для жюри, запускается из мини-приложения |
| Лаунчер | Бот, у которого нет продуктовой логики, только `open_app` |

---

## 3. Стек

| Слой | Технология |
|------|------------|
| Мини-приложение | React, TypeScript, Vite, MAX UI, MAX Bridge |
| Бэкенд | Python 3.12, **Django 5.1**, **Django REST Framework 3.15** |
| OpenAPI | **drf-spectacular** `>=0.27,<0.29` |
| БД | PostgreSQL 16 |
| Файлы | Django `FileField`, volume `/data/uploads` (`MEDIA_ROOT`) |
| WSGI | Gunicorn |
| Статика SPA | nginx |
| Контейнеры | Docker Compose: `web`, `api`, `worker`, `db` |
| Лаунчер | Один webhook-view в Django. Клиент `platform-api2.max.ru` умеет только отправить сообщение с кнопкой `open_app` |

Очередь на MVP: таблица снимков + процесс `python manage.py process_snapshots`. Redis и Celery не требуются.

---

## 4. Функциональные требования

### 4.1. Бот-лаунчер

**FR-1.** Единственная задача бота — открыть мини-приложение. Продуктовых веток в чате нет.

**FR-2.** На `bot_started`, на `/start` и на любое другое текстовое сообщение бот отправляет одно и то же приветствие (не длиннее 2 предложений) и одну кнопку «Открыть X-Ray» (`open_app`). `start_param` не передаётся.

**FR-3.** Вложение, неизвестная команда и callback не создают `Upload`, не запускают снимок и не присылают диагноз или шаблон. Ответ — то же приглашение из FR-2. На callback всегда `POST /answers`, чтобы кнопка не крутилась.

**FR-4.** В кабинете MAX у бота подключено это мини-приложение. Если платформа даёт кнопку меню бота, она открывает то же приложение, без параметра.

**FR-5.** Ник бота задаётся один раз и не меняется.

**FR-6.** В коде бота нет парсера, маппинга, метрик и текста диагноза.

### 4.2. Мини-приложение

**FR-7.** Экраны: Home, Mapping, StatusMap, Processing, Diagnosis, MetricDetail, MissingData.

**FR-8.** Home: загрузить файл, открыть демо, скачать шаблон, блок «История сканов» по §4.4.

**FR-9.** Mapping: превью 5 строк, селект «колонка файла → поле канона», счётчик «N из 7 метрик». Кнопка «Просветить» неактивна, пока не заданы `amount` и хотя бы одно из `status` | `created_at`.

**FR-10.** Processing: прогресс и статус снимка, опрос `GET /api/snapshots/{id}` раз в 1 с, пока `status` не `ready` или `failed`. Не больше 120 опросов подряд. Дальше текст «Расчёт ещё идёт» и кнопка «Проверить ещё», которая начинает отсчёт заново.

**FR-11.** Diagnosis: период, число сделок, сумма, вердикт одной фразой, до 3 карточек находок, свёрнутые списки «В норме» и «Мало данных», покрытие, кнопки «Скопировать заключение» и «Новый снимок». Карточки — только метрики `critical` и `watch` без `low_sample`, отбор по §6.3. Кнопки «Прислать в чат» нет.

**FR-12.** «Скопировать заключение» кладёт в буфер текст из уже загруженного диагноза: `headline`, затем каждое `action` с новой строки, затем строка покрытия «посчитано N из 7». Отдельный запрос к API и сообщение бота для этого не нужны. Если буфер недоступен — текст показывается на экране, чтобы его можно было выделить.

**FR-13.** MetricDetail: значение, порог человеческим языком, до 50 сделок-доказательств. На мобиле — карточки, на desktop/web — таблица.

**FR-14.** MissingData: список полей, которых не хватило, и какую метрику они открывают. Рядом ссылка «Скачать шаблон».

**FR-15.** Ошибки файла, пустой файл, нетаблица — сообщение на том же шаге, без перезапуска мини-приложения.

**FR-16.** `WebApp.ready()`, `expand()`, `BackButton` на внутренних экранах, `enableClosingConfirmation()` на Mapping после правок.

**FR-17.** Каждый запрос к API несёт заголовок `X-Max-Init-Data`. Клиент не доверяет `initDataUnsafe`.

**FR-18.** Интерфейс работает в мобильной и веб-версии MAX (`platform`: ios, android, desktop, web).

**FR-19.** Открытие приложения всегда начинается с Home. `start_param` в MVP не читается: бот его не задаёт, глубоких ссылок из чата нет. Прошлая сессия открывается только из истории на Home.

### 4.3. Данные и диагноз

**FR-20.** Принимаются CSV (UTF-8, utf-8-sig, cp1251; разделитель `;` или `,`) и Excel `.xlsx` / `.xls`. Лимит: 20 МБ, 20 000 строк. Единственный канал загрузки — форма мини-приложения.

**FR-21.** Парсер нормализует заголовки (trim, регистр, ё→е), деньги с пробелами и `₽`, даты `DD.MM.YYYY`, `YYYY-MM-DD`, Excel serial, `14 мая 2024`.

**FR-22.** Маппинг предлагается эвристикой по синонимам и типам значений. Пользователь подтверждает или правит.

**FR-23.** Неизвестные статусы → `other`, в ответе маппинга отдаётся топ сырых значений.

**FR-24.** Строки с пустой или отрицательной суммой отбрасываются в `quality.rejected` с причиной. Диагноз строится по принятым.

**FR-25.** Если поля метрики нет — метрика `skipped`, диагноз строится по остальным, пользователю пишется, какую колонку добавить.

**FR-26.** Движок детерминирован: одинаковые deals + одинаковые пороги → одинаковый снимок.

**FR-27.** Демо-набор синтетический, без реальных ФИО и телефонов. В README явно указано: используются подготовленные тестовые данные. Демо запускается только из мини-приложения (`GET /api/demo`).

**FR-28.** Шаблон `data/template.xlsx` скачивается из мини-приложения (`GET /api/template`). Это файл с каноническими заголовками и 2–3 примерными строками, не выгрузка пользователя.

**FR-29.** Пользователь может удалить снимок из истории и с экрана этой сессии. Каскадно удаляются deals, metric_results, diagnosis, файл upload, если на него нет других снимков. После удаления сессия пропадает из списка, `GET` по её id возвращает 404.

### 4.4. История сессий

**US-1.** Как владелец, я хочу видеть свои сканы и открывать любой из них, чтобы снова прочитать диагноз и сделки этой выгрузки без новой загрузки.

**FR-30.** Блок «История сканов» на Home есть только если у пользователя есть хотя бы одна сессия. Пустой ответ списка — блок скрыт, это не ошибка. Если в ответе есть `next_cursor`, под списком кнопка «Показать ещё».

**FR-31.** Строка сессии: дата создания, имя файла, источник `miniapp` или `demo`, статус. Для `ready` ещё период, headline, худший вердикт находок (`critical`, иначе `watch`, иначе `ok`) и «N из 7». Для `processing` и `failed` эти поля в API равны `null`. Сортировка: `created_at` по убыванию.

**FR-32.** Нажатие на строку открывает эту сессию и не запускает новый расчёт.

- `ready` — Diagnosis, дальше MetricDetail и MissingData того же `snapshot_id`.
- `processing` — Processing, опрос как в FR-10.
- `failed` — текст `error` и кнопка «Удалить».

**FR-33.** «Назад» из сессии возвращает на Home к тому же месту истории. Данные сессии берутся из сохранённого снимка.

**FR-34.** В истории только свои сессии, включая демо. Чужой id не отображается и не открывается.

**FR-35.** Экран StatusMap открывается после Mapping только если в ответе маппинга `unknown_statuses` не пуст. Для каждого сырого статуса — выбор канона или «оставить прочим». Кнопка «Дальше» сохраняет `status_map` тем же `PUT`, что и колонки. «Назад» возвращает на Mapping, выбор не теряется, пока мини-приложение открыто.

**FR-36.** «Просветить» сначала вызывает `PUT /api/uploads/{id}/mapping` с текущими селектами, затем `POST /api/snapshots`. Предложенный маппинг без этого `PUT` не считается подтверждённым.

**FR-37.** «Назад» с Mapping на Home не удаляет загрузку. `enableClosingConfirmation()` срабатывает только на закрытие мини-приложения, если на Mapping или StatusMap есть несохраненная правка.

**FR-38.** Любая ошибка API показывается текстом `message` из §9.0. Код `code` в интерфейс не выводится.

---

## 5. Основной сценарий (приёмка)

1. Пользователь открывает бота и видит одно приветствие и кнопку «Открыть X-Ray». Других кнопок нет.
2. Нажимает кнопку → открывается мини-приложение на Home.
3. С Home скачивает шаблон и убеждается, что пришёл xlsx.
4. На Home нажимает «Демо» → открывается готовый Diagnosis, без сообщения в чат.
5. Возвращается на Home и загружает `data/demo_deals.csv`.
6. Mapping предлагает сумму, статус, дату, клиента.
7. Нажимает «Просветить».
8. Diagnosis содержит вердикт, 3 карточки, покрытие.
9. MetricDetail по зависшим сделкам — непустой список.
10. «Скопировать заключение» — в буфере есть headline и действия. В чат бота ничего не уходит.
11. Повтор шагов 5–8 с файлом без колонки менеджера: диагноз есть, метрики, завязанные только на менеджера, skipped, есть подсказка.
12. Сообщение боту текстом или файлом не создаёт снимок и отвечает той же кнопкой «Открыть X-Ray».
13. На Home в истории есть демо и снимок из файла. Открыть более ранний — на экране его диагноз, не диагноз последнего. «Назад» возвращает к списку. Удаление убирает строку, повторное открытие даёт 404.

Ожидаемые числа демо-набора фиксируются в README при появлении файла и не меняются без смены `engine_version`.

---

## 6. Каноническая схема и метрики

### 6.1. Поля Deal

| Поле | Тип | Обязательность после нормализации |
|------|-----|-----------------------------------|
| `deal_id` | string | да (id строки или хэш) |
| `client` | string | нет |
| `contact` | string | нет |
| `manager` | string | нет |
| `amount` | decimal | да, иначе строка rejected |
| `list_price` | decimal | нет |
| `discount_pct` | decimal | нет |
| `status_raw` | string | нет |
| `status` | enum | да, default `other` |
| `created_at` | datetime | нет |
| `first_contact_at` | datetime | нет |
| `status_changed_at` | datetime | нет |
| `last_activity_at` | datetime | нет |
| `closed_at` | datetime | нет |
| `source` | string | нет |
| `extra` | object | нет |

Статусы: `new` | `in_progress` | `proposal` | `negotiation` | `won` | `lost` | `other`.

Словарь сырых значений — как в концепции, §7.

### 6.2. Метрики

Пороги хранятся в `engine/thresholds.yaml`, в снимке пишется `engine_version`.

| id | Формула | skipped если нет | watch | critical |
|----|---------|------------------|-------|----------|
| `speed_to_lead` | медиана `first_contact_at - created_at` | обоих полей | > 30 мин | > 2 ч |
| `stagnation` | открытые, время на статусе > 1,5× медианы цикла `won`; эффект = сумма | `status` + дата | — | есть такие сделки; в MVP все такие — critical |
| `discount_leakage` | доля `won` с `discount_pct > 10%`; маржа `(list_price - amount)` если прайс есть | `amount` + скидка или прайс | доля > 10% | доля > 20% |
| `sales_cycle` | медиана `closed_at - created_at` по `won`; сравнение половин периода | дат закрытия/создания | цикл растёт | рост > 30% |
| `key_account_risk` | доля суммы `won` у top-2 `client` | `client` + won | top-2 > 50% | top-2 > 65% |
| `dormant` | клиенты без `won`, тишина > 45 дней (`last_activity_at` или `created_at`) | `client` + дата | есть такие | сумма или число выше порога yaml |
| `funnel_dropoff` | этап с максимальной потерей суммы | `status` + `amount` | этап > 40% суммы | этап > 55% |

Каждая метрика отдаёт: `available`, `missing_fields`, `value`, `unit` (`hours`|`days`|`pct`|`rub`), `verdict`, `money_impact`, `evidence` (до 50), `threshold_label`, шаблон `action`.

Narrator без LLM склеивает шаблоны §6.5. LLM, если задан `LLM_API_KEY`, переписывает только `headline` и `action` по §6.5. Числа не меняет. Текст показывается в мини-приложении и копируется оттуда. В чат он не отправляется.

### 6.3. Правила расчёта

Часовой пояс всех дат и «сейчас» — `Europe/Moscow`. Дата без времени — 00:00 этого пояса. Сравнение и вычитание — в этом поясе. Деньги: `Decimal`, округление `ROUND_HALF_UP`, в JSON строка с двумя знаками (`"4200000.00"`). Проценты, часы и дни — JSON-число с двумя знаками. Счётчики — целые.

`deal_id`: если колонка сопоставлена и значение после trim непустое — оно, обрезка до 64 символов. Иначе первые 32 hex-символа SHA-256 от строки `{номер строки данных}|{amount}|{client}|{created_at ISO-8601 или пусто}`. Повтор `deal_id` в одном файле: первая строка остаётся, остальные — `quality.rejected` с причиной `duplicate_deal_id`. Снимок из-за повтора не падает.

Сумма пустая, нечисло или `<= 0` — строка в `rejected`. Причины: `empty_amount`, `bad_amount`, `non_positive`.

Открытая сделка: `status` не `won` и не `lost`. `other` — открытая.

`low_sample`: для `speed_to_lead`, `sales_cycle`, `discount_leakage`, `key_account_risk`, `funnel_dropoff` меньше 5 годных наблюдений. Вердикт тогда `ok`, в три карточки метрика не попадает, она в списке «Мало данных». `stagnation` и `dormant` срабатывают с одной сделки.

Наблюдение с отрицательной длительностью (контакт раньше заявки, закрытие раньше создания) в медиану не входит.

| id | Годное наблюдение | Вердикт |
|----|-------------------|---------|
| `speed_to_lead` | оба времени есть, контакт не раньше заявки. Значение — медиана минут | `watch` > 30 мин, `critical` > 120 мин |
| `stagnation` | открытая сделка. Возраст — от `status_changed_at`, иначе от `created_at`, до «сейчас». Порог — 1,5× медианы дней цикла `won` (закрытие не раньше создания). Меньше 5 таких `won` — порог `fallback_days` | есть хотя бы одна старше порога → `critical`, сумма таких сделок в `money_impact`. Иначе `ok` |
| `discount_leakage` | `won`. Если колонка скидки сопоставлена — берётся она. Иначе при `list_price > 0` скидка считается `(list_price - amount) / list_price * 100`. Колонка важнее расчёта | доля со скидкой > 10%: `watch` > 10%, `critical` > 20%. `money_impact` — сумма `max(list_price - amount, 0)` только где прайс есть, иначе `null` |
| `sales_cycle` | `won`, оба края есть, закрытие не раньше создания. Значение — медиана дней. Половины периода — по `created_at` относительно середины `period_from`…`period_to` | обе половины имеют ≥ 5 сделок и рост медианы > 0 → `watch`; рост > 30% → `critical`. Иначе `ok`. Медиана первой половины 0 — роста нет, `ok` |
| `key_account_risk` | `won` с непустым `client`. Пустой клиент не группируется | доля суммы top-2: `watch` > 50%, `critical` > 65%. Меньше двух клиентов — `low_sample` |
| `dormant` | непустой `client` без единой `won`. Тишина — от более позднего из `last_activity_at` и `created_at` | есть такие старше 45 дней → `watch`. Число ≥ 5 или сумма их открытых сделок ≥ порога yaml → `critical` |
| `funnel_dropoff` | этапы по порядку yaml, `lost` и `other` в цепочку не входят. Дошёл до этапа = статус этого этапа или любого следующего, включая `won`. Потеря этапа = сумма дошедших минус сумма дошедших до следующего | этап с максимальной потерей. Доля потери от дошедших: `watch` > 40%, `critical` > 55%. Ноль дошедших — этап пропускается |

`skipped` только когда нет нужных колонок (§6.2), не когда мало строк.

Три карточки: кандидаты `critical` и `watch` с `low_sample = false`. Сортировка: `money_impact` по убыванию, пустой эффект в конце, затем `critical` раньше `watch`, затем `metric_id` по алфавиту. Берутся первые 3.

`progress`: `0` снимок создан, `30` строки нормализованы, `70` метрики записаны, `100` вместе со `ready`. При `failed` прогресс не откатывается.

### 6.4. `engine/thresholds.yaml`

Файл в репозитории, версия в каждом снимке — поле `engine_version` отсюда.

```yaml
engine_version: "1"
timezone: Europe/Moscow
min_sample: 5
speed_to_lead:
  watch_minutes: 30
  critical_minutes: 120
stagnation:
  cycle_multiplier: 1.5
  fallback_days: 21
discount:
  watch_share: 0.10
  critical_share: 0.20
  leak_discount_pct: 10
sales_cycle:
  critical_growth: 0.30
key_account:
  watch_share: 0.50
  critical_share: 0.65
dormant:
  days: 45
  critical_count: 5
  critical_rub: "500000.00"
funnel:
  watch_loss_share: 0.40
  critical_loss_share: 0.55
  stages: [new, in_progress, proposal, negotiation, won]
```

Смена числа в этом файле меняет `engine_version`. Старый снимок не пересчитывается.

### 6.5. Тексты

Шаблоны, подстановки в фигурных скобках. Деньги в тексте — рубли с пробелом тысяч, без копеек, если копейки `.00`.

| metric_id | action |
|-----------|--------|
| `speed_to_lead` | Медиана первого контакта {value} ч. Ответьте новым заявкам быстрее 30 минут |
| `stagnation` | Разморозьте {value} сделок старше {threshold_days} дней на {money} |
| `discount_leakage` | {share}% выигранных сделок ушли со скидкой больше 10% |
| `sales_cycle` | Цикл сделки вырос до {value} дней |
| `key_account_risk` | Два клиента дают {share}% выручки |
| `dormant` | {value} клиентов молчат дольше 45 дней |
| `funnel_dropoff` | На этапе «{stage}» теряется {money} |

`headline`: есть карточка — её `action`. Карточек нет — «По этому файлу критичных утечек не видно.»

`threshold_label` для зависших: «Зависшей считаем сделку старше {threshold_days} дней». Для остальных метрик — одно предложение из порога yaml («быстрее 30 минут», «скидка больше 10%», «дольше 45 дней», «два клиента больше 50%», «этап теряет больше 40% суммы», «цикл вырос»).

LLM, только при непустом `LLM_API_KEY`. Один запрос на снимок, таймаут 8 с. В запрос: `metric_id`, `verdict`, `value`, `unit`, `money_impact`, `threshold_label`, черновики `headline` и `action`. Без имён, телефонов, названий клиентов и сырых строк. Модель может заменить только строки `headline` и `action`. Если в ответе другое число, не JSON, не 200 или таймаут — остаются шаблоны.

### 6.6. Разбор файла и маппинг

Первая непустая строка — заголовки. Пустые строки над ней пропускаются. Нет ни одной непустой строки — `not_a_table`.

Excel: скрытые листы игнорируются. Берётся лист, у которого больше заголовков совпало со словарём синонимов. Ничья — первый лист в книге. Файл с паролем — `encrypted`.

Повтор заголовка получает суффикс ` (2)`, ` (3)` по порядку слева направо.

CSV: кодировка по очереди utf-8-sig, utf-8, cp1251. Ни одна не подошла — `bad_encoding`. Разделитель — тот из `;` и `,`, которого больше в строке заголовков. Поровну — `;`.

Лимит проверяется до полного разбора сделок: размер файла больше 20 × 1024 × 1024 байт — `file_too_large`. Строк данных больше 20 000 — `too_many_rows`.

Деньги: убрать пробелы, неразрывные пробелы, `₽`, `руб`, `р`. Запятая или точка — десятичный знак. Если есть и запятая, и точка, последний из них — десятичный знак. Суффикс `млн` умножает на 1 000 000, `тыс` — на 1 000.

Даты: `DD.MM.YYYY`, `DD.MM.YY`, `YYYY-MM-DD`, `YYYY-MM-DD HH:MM`, Excel serial, `14 мая 2024`. Месяцы: января, февраля, марта, апреля, мая, июня, июля, августа, сентября, октября, ноября, декабря и краткие формы янв, фев, мар, апр, май, июн, июл, авг, сен, окт, ноя, дек. Неразобранная дата в сопоставленной колонке — пустое поле и warning `bad_dates`, строка не отбрасывается, если сумма годная.

Синоним колонки: trim, нижний регистр, ё→е, схлопнуть пробелы. Совпадение только точное, со списком ниже. Одна колонка — одно поле. Если претендуют двое, побеждает поле, которое выше в списке. Сервер на повтор отвечает `duplicate_column`.

| Поле | Синонимы |
|------|----------|
| `amount` | сумма, бюджет, цена, цена со скидкой, итого, сумма сделки, amount, price |
| `status` | статус, этап, стадия, воронка, status |
| `created_at` | дата, дата создания, создано, дата заявки, created, created_at |
| `client` | клиент, компания, контрагент, заказчик, client |
| `contact` | телефон, контакт, email, почта, phone |
| `manager` | менеджер, ответственный, владелец, manager |
| `list_price` | прайс, цена без скидки, list_price |
| `discount_pct` | скидка, скидка %, discount |
| `first_contact_at` | дата первого контакта, первый звонок, first_contact |
| `status_changed_at` | дата смены статуса, на этапе с, status_changed |
| `last_activity_at` | дата последней активности, последний контакт, last_activity |
| `closed_at` | дата закрытия, дата оплаты, closed, closed_at |
| `source` | канал, источник, source |
| `deal_id` | id, номер, номер сделки, deal_id |

Если колонка не занята и ≥ 80% непустых значений в первых 20 строках — даты, она занимает первое свободное поле дат в порядке `created_at`, `closed_at`, `first_contact_at`, `status_changed_at`, `last_activity_at`. Так же деньги занимают `amount`, а если он занят — `list_price`.

Статус. Сравнение после той же нормализации, что у заголовков, и только на равенство целиком, не на вхождение.

| Канон | Сырые значения |
|-------|----------------|
| `new` | новая, не разобрана, входящая, лид |
| `in_progress` | в работе, квалификация, думает, созвон |
| `proposal` | кп отправлено, коммерческое, счёт выставлен, счет выставлен |
| `negotiation` | согласование, торг, пинать в пятницу |
| `won` | успешно, оплачено, закрыто, выиграна |
| `lost` | отказ, проиграна, нецелевой |

Сначала `status_map` пользователя (ключ — сырое значение как в файле, после trim, без смены регистра). Затем словарь. Иначе `other`. В ответ маппинга — до 10 таких значений, самые частые: `unknown_statuses: [{ "raw", "count" }]`.

`data/template.xlsx`: одна строка заголовков «Клиент», «Телефон», «Менеджер», «Сумма», «Прайс», «Скидка %», «Статус», «Дата создания», «Дата первого контакта», «Дата смены статуса», «Дата последней активности», «Дата закрытия», «Канал» и две синтетические строки.

---

## 7. Frontend — требования к реализации

1. SPA в `apps/web`, сборка Vite, раздача nginx по HTTPS.
2. Состояние экранов внутри приложения. Публичных URL и разбора `start_param` нет. Стек экранов: Home и переходы вперёд, назад — `BackButton`.
3. Модули: `bridge`, `api`, `screens/*`, `widgets/*`, `domain/metrics.ts`, `domain/mapping.ts`.
4. Загрузка файла: `<input accept=".csv,.xlsx,.xls">`. Парсинг Excel на клиенте запрещён. Второго канала «файл из чата» нет.
5. Перед отправкой показывать имя, размер, тип.
6. На Mapping после правок — confirmation на закрытие.
7. Тема MAX UI, mobile-first, на desktop/web карточки диагноза в две колонки.
8. Home: загрузить файл, демо, скачать шаблон, история по §4.4. Вход в сессию хранит `snapshot_id` в состоянии приложения. Отдельного URL у сессии нет.
9. Скачивание шаблона — §9.10: на телефоне `WebApp.downloadFile` по короткой ссылке, в вебе `fetch` с `X-Max-Init-Data`.
10. Копирование заключения — `navigator.clipboard` из данных экрана Diagnosis. Вызов Bot API с клиента запрещён: токен бота на фронт не попадает.

---

## 8. Backend — Django

### 8.1. Структура проекта

```text
apps/api/
  manage.py
  config/
    __init__.py
    settings.py
    urls.py
    wsgi.py
    asgi.py
  users/
    models.py          # MaxUser
    authentication.py  # MaxInitDataAuthentication
    permissions.py
  ingest/
    models.py          # Upload
    parsers.py         # CSV/XLSX → RawTable
    mapping.py         # эвристики, синонимы, статусы
    normalizer.py      # RawTable + mapping → Deal[]
    views.py
  snapshots/
    models.py          # Snapshot, Deal, MetricResult, Diagnosis
    views.py
    serializers.py
    tasks.py           # обработка очереди
    management/commands/process_snapshots.py
  engine/
    thresholds.yaml
    metrics.py         # чистые функции, без Django ORM
    narrator.py
  launcher/
    views.py           # webhook: только приглашение открыть приложение
    client.py          # send_message с одной кнопкой open_app
  demo/
    loader.py          # читает data/demo_deals.csv
```

Движок `engine/` не импортирует Django. Тесты метрик — без БД.

Каталога `bot/` с хендлерами команд, файлов и демо нет. Лаунчер не импортирует `engine`, `ingest` и `snapshots`.

### 8.2. Настройки Django (обязательные)

- `DEBUG` только при `APP_ENV=local`.
- `DJANGO_SECRET_KEY`, `MAX_BOT_TOKEN`, `MAX_WEBHOOK_SECRET`, `DATABASE_URL` — из env.
- `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` из `PUBLIC_WEB_URL`.
- `MEDIA_ROOT=/data/uploads`, раздача файлов наружу **запрещена** (только через бизнес-API).
- DRF:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "users.authentication.MaxInitDataAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
```

- Вебхук лаунчера в `urls.py` вынесен из DRF auth: `path("webhook/max", ...)`.
- `APPEND_SLASH=False`. Все пути в §9 без хвостового слэша. Так зафиксировано в OpenAPI.

### 8.3. Аутентификация

Класс `MaxInitDataAuthentication`. Заголовок `X-Max-Init-Data` — это строка `window.WebApp.initData` как есть, не весь URL. Алгоритм — [документация MAX](https://dev.max.ru/docs/webapps/validation):

1. Разбить строку по `&` на пары `key=value`. Ключ `hash` ровно один раз, иначе 401.
2. URL-decode значений. `hash` вынуть и в строку подписи не включать.
3. Остальные пары отсортировать по ключу, `a` → `z`, склеить `key=value` через `\n` (байт `0x0A`). Это `launch_params`.
4. `secret_key = HMAC-SHA256`, ключ — байты `WebAppData`, сообщение — байты `MAX_BOT_TOKEN`.
5. Подпись — hex от `HMAC-SHA256`, ключ `secret_key`, сообщение `launch_params`. Сравнение с `hash` через `hmac.compare_digest`.
6. `auth_date` — unix-секунды. Старше 24 часов или больше чем на 60 секунд в будущем — 401.
7. Из JSON-поля `user` взять `id` (целое) и `first_name`. Нет `id` — 401.
8. `MaxUser.objects.get_or_create(max_user_id=...)`.

Хакатонный обход: если `APP_ENV=hackathon` и заголовок `X-Debug-Token == DEBUG_TOKEN`, принять `X-Debug-User` как `max_user_id`. В `production` ветка отсутствует. Описано в README. Обход не действует на вебхук.

Вебхук проверяет заголовок `X-Max-Bot-Api-Secret` на равенство `MAX_WEBHOOK_SECRET`. Без совпадения — 401. CSRF для этого view отключён (`csrf_exempt`). Вебхук не создаёт `MaxUser` и не пишет файлы.

### 8.4. Модели Django

```python
class MaxUser(models.Model):
    max_user_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Upload(models.Model):
    class Source(models.TextChoices):
        MINIAPP = "miniapp"
        DEMO = "demo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(MaxUser, on_delete=models.CASCADE)
    file = models.FileField(upload_to="uploads/%Y/%m/")
    filename = models.CharField(max_length=255)
    mime = models.CharField(max_length=127, blank=True)
    size_bytes = models.PositiveIntegerField()
    source = models.CharField(max_length=16, choices=Source.choices)
    columns = models.JSONField(default=list)
    sample_rows = models.JSONField(default=list)
    suggested_mapping = models.JSONField(default=dict)
    mapping = models.JSONField(null=True, blank=True)
    status_map = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Snapshot(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing"
        READY = "ready"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(MaxUser, on_delete=models.CASCADE)
    upload = models.ForeignKey(Upload, on_delete=models.CASCADE)
    archetype = models.CharField(max_length=32, default="deals")
    engine_version = models.CharField(max_length=32)
    period_from = models.DateField(null=True)
    period_to = models.DateField(null=True)
    mapping = models.JSONField(default=dict)
    mapping_hash = models.CharField(max_length=64)
    quality = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default="processing")
    progress = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    locked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at", "-id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["upload", "mapping_hash", "engine_version"],
                condition=models.Q(status__in=["processing", "ready"]),
                name="uniq_active_snapshot",
            ),
        ]

class Deal(models.Model):
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="deals")
    deal_id = models.CharField(max_length=64)
    client = models.CharField(max_length=255, blank=True)
    contact = models.CharField(max_length=255, blank=True)
    manager = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    list_price = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    discount_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    status_raw = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField(null=True)
    first_contact_at = models.DateTimeField(null=True)
    status_changed_at = models.DateTimeField(null=True)
    last_activity_at = models.DateTimeField(null=True)
    closed_at = models.DateTimeField(null=True)
    source = models.CharField(max_length=255, blank=True)
    extra = models.JSONField(default=dict)

    class Meta:
        unique_together = ("snapshot", "deal_id")

class MetricResult(models.Model):
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="metrics")
    metric_id = models.CharField(max_length=64)
    payload = models.JSONField()

    class Meta:
        unique_together = ("snapshot", "metric_id")

class Diagnosis(models.Model):
    snapshot = models.OneToOneField(Snapshot, on_delete=models.CASCADE, related_name="diagnosis")
    headline = models.TextField()
    body = models.TextField()
    findings = models.JSONField()
    coverage = models.JSONField()
    totals = models.JSONField()
```

Все выборки снимков и файлов фильтруются `user=request.user`. Чужой UUID → 404, не 403.

Источник `chat` у `Upload` удалён. Загрузка из мини-приложения пишет `source=miniapp`, демо — `source=demo`.

### 8.5. Обработка снимка

1. `POST /api/snapshots` создаёт `Snapshot(status=processing, progress=0)` и возвращает 200 с id. Код 202 не используется.
2. `mapping_hash` — SHA-256 канонического JSON `{mapping, status_map}` с ключами по алфавиту и без пробелов.
3. Повтор с тем же `upload_id`, `mapping_hash` и `engine_version`: если есть снимок `processing` или `ready`, вернуть его и `created: false`. Если прошлый только `failed` — создать новый. Гонку закрывает уникальный индекс; второй запрос ловит конфликт и возвращает победителя.
4. Воркер крутится до SIGTERM. Пустая очередь — сон 1 с. Берёт `status=processing` и (`locked_at` пуст или старше 15 минут) через `SELECT … FOR UPDATE SKIP LOCKED`, сразу пишет `locked_at`.
5. Шаги: normalize (`progress=30`) → engine и narrator (`progress=70`) → записать Deal / MetricResult / Diagnosis → `ready`, `progress=100`, `locked_at` пустой.
6. Исключение → `failed`, текст в `error` без traceback наружу (traceback только в лог).
7. HTTP-запрос **не** считает Excel синхронно, кроме `GET /api/demo`, где датасет маленький и ответ сразу `ready`.
8. Расчёт не запускается из вебхука.

### 8.6. Клиент лаунчера

Модуль `launcher/client.py`:

- база `https://platform-api2.max.ru`;
- заголовок `Authorization: <MAX_BOT_TOKEN>` (без query-токена);
- `POST /messages?user_id={user_id из Update}`;
- на `message_callback` сначала `POST /answers` с `callback_id` этого события и телом `{"notification": ""}`;
- отправки файлов нет;
- таймаут 10 с, ретраи на 429/503 (не больше 3).

Тело сообщения одно на все события:

```json
{
  "text": "X-Ray показывает, где в продажах теряются деньги. Откройте приложение и загрузите таблицу сделок.",
  "attachments": [
    {
      "type": "inline_keyboard",
      "payload": {
        "buttons": [
          [
            {
              "type": "open_app",
              "text": "Открыть X-Ray",
              "web_app": "<username бота>"
            }
          ]
        ]
      }
    }
  ]
}
```

Поля `payload` и `contact_id` у кнопки нет: `start_param` не передаётся. `web_app` — ник бота из кабинета MAX.

### 8.7. Зависимости Python (минимум)

```text
Django>=5.1,<5.2
djangorestframework>=3.15
drf-spectacular>=0.27
psycopg[binary]>=3.2
gunicorn>=23.0
openpyxl>=3.1
xlrd>=2.0
pandas>=2.2
python-dotenv>=1.0
httpx>=0.27
```

Версии пишутся в `requirements.txt` с пиннами после первой успешной сборки.

---

## 9. HTTP API

Префикс: `/api`  
Auth: `X-Max-Init-Data`, кроме вебхука лаунчера, схемы и `GET /api/template-file/{token}`.

Метода `POST /api/snapshots/{id}/share-to-chat` нет.

### 9.0. Ошибки и деньги

Тело любой ошибки API:

```json
{ "code": "file_too_large", "message": "Файл больше 20 МБ. Выгрузите последние 90 дней." }
```

`message` на русском, его показывает мини-приложение. Коды загрузки: `not_a_table`, `no_header`, `bad_encoding`, `encrypted`, `file_too_large`, `too_many_rows`, `duplicate_column`, `mapping_incomplete`. Общие: `unauthorized` (401), `not_found` (404), `not_ready` (409), `rate_limited` (429, поле `retry_after` в секундах).

Деньги в JSON — строки с двумя знаками. Не числа.

Лимит NFR-8: 20 успешных `POST /api/uploads` на пользователя за скользящие 60 минут. Демо и шаблон не считаются. Окно считается от времени самых ранних из этих 20.

### 9.1. `POST /api/uploads`

`multipart/form-data`, поле `file`. Источник всегда `miniapp`.

Успех 201:

```json
{
  "upload_id": "uuid",
  "filename": "deals.csv",
  "columns": ["Клиент", "Бюджет", "Статус", "Дата"],
  "sample_rows": [{ "...": "до 5 строк" }],
  "suggested_mapping": {
    "amount": "Бюджет",
    "client": "Клиент",
    "status": "Статус",
    "created_at": "Дата"
  },
  "coverage": {
    "available": ["stagnation", "funnel_dropoff", "key_account_risk"],
    "skipped": ["speed_to_lead"]
  }
}
```

`sample_rows` — не больше 5. Если предложен статус, в том же ответе есть `unknown_statuses`. Ошибки — §9.0, статус 400 или 401.

### 9.2. `PUT /api/uploads/{id}/mapping`

```json
{
  "mapping": { "amount": "Бюджет", "status": "Статус" },
  "status_map": { "Пинать в пятницу": "negotiation" }
}
```

Успех 200: `coverage`, `warnings[]` (например, `bad_dates`), `unknown_statuses`. Этот вызов и есть подтверждение маппинга. Одна колонка на два поля — 400 `duplicate_column`. Нет `amount` или нет ни `status`, ни `created_at` — 400 `mapping_incomplete`.

### 9.3. `POST /api/snapshots`

```json
{ "upload_id": "uuid" }
```

Успех 200: `{ "snapshot_id": "uuid", "status": "processing", "created": true }`. Повтор по §8.5 возвращает тот же id и `created: false`. 400 `mapping_incomplete`, если `PUT` маппинга ещё не было.

### 9.4. `GET /api/snapshots/{id}`

```json
{ "snapshot_id": "uuid", "status": "processing", "progress": 40, "error": "" }
```

### 9.5. `GET /api/snapshots/{id}/diagnosis`

Только при `ready`, иначе 409.

```json
{
  "headline": "…",
  "body": "…",
  "findings": [
    {
      "metric_id": "stagnation",
      "verdict": "critical",
      "value": 12,
      "unit": "deals",
      "money_impact": "4200000.00",
      "action": "Разморозьте 12 сделок старше 21 дня на 4,2 млн",
      "threshold_label": "Зависшей считаем сделку, которая стоит на этапе дольше 21 дня"
    }
  ],
  "coverage": { "available": ["…"], "skipped": ["…"] },
  "period": { "from": "2026-01-01", "to": "2026-03-31" },
  "totals": { "deals": 84, "amount": "12400000.00", "accepted": 80, "rejected": 4 },
  "quality": { "reasons": [{ "code": "non_positive", "count": 4 }] },
  "ok": ["sales_cycle"],
  "low_sample": ["key_account_risk"]
}
```

Этого JSON достаточно, чтобы мини-приложение собрало текст для буфера (FR-12).

### 9.6. `GET /api/snapshots/{id}/metrics/{metric_id}`

`{ "result": {…MetricResult}, "evidence": [ { "deal_id", "client", "amount", "status", "days_stale", "manager", "contact" } ] }`

### 9.7. `GET /api/snapshots`

История сессий текущего пользователя. Новые сверху.

Query: `limit` (по умолчанию 20, максимум 50), `cursor`. Сортировка: `created_at` по убыванию, при равенстве `id` по убыванию. Курсор — urlsafe-base64 без padding от JSON `{"created_at":"<ISO>","id":"<uuid>"}`. Клиент строку не разбирает. Без курсора — первая страница.

Успех 200:

```json
{
  "items": [
    {
      "snapshot_id": "uuid",
      "status": "ready",
      "created_at": "2026-03-31T12:00:00Z",
      "filename": "deals.csv",
      "source": "miniapp",
      "period": { "from": "2026-01-01", "to": "2026-03-31" },
      "headline": "…",
      "verdict": "critical",
      "coverage_ready": 5,
      "coverage_total": 7
    }
  ],
  "next_cursor": null
}
```

Для `processing` и `failed` поля `period`, `headline`, `verdict`, `coverage_ready`, `coverage_total` равны `null`. `verdict` для `ready` считается по FR-31, в БД не хранится. `next_cursor` есть, пока страница не последняя.

Вход в сессию — уже описанные методы, нового ресурса нет:

| Шаг | Метод |
|-----|--------|
| Список | `GET /api/snapshots` |
| Статус выбранной | `GET /api/snapshots/{id}` |
| Диагноз `ready` | `GET /api/snapshots/{id}/diagnosis` |
| Сделки метрики | `GET /api/snapshots/{id}/metrics/{metric_id}` |
| Удаление | `DELETE /api/snapshots/{id}` |

Чужой или неизвестный id на этих методах — 404. `ready`-диагноз отдаётся сохранённым, без пересчёта.

### 9.8. `DELETE /api/snapshots/{id}`

204. Каскад по FR-29.

### 9.9. `GET /api/demo`

Один демо-снимок на пользователя и `engine_version`. Если такой `ready` уже есть — вернуть его. Если `processing` — вернуть его id и статус. Если его удалили, он `failed` или сменилась `engine_version` — посчитать заново в этом запросе и вернуть `ready`. Старые демо-снимки других версий из истории не удаляются. 200: тело диагноза §9.5 плюс `snapshot_id`.

### 9.10. `GET /api/template`

Отдаёт `data/template.xlsx`.  
200, `Content-Type` для xlsx, `Content-Disposition: attachment; filename="xray-template.xlsx"`.  
401 без initData. Файл не зависит от пользователя и не пишется в `Upload`.

На телефоне MAX не скачивает файл по обычной ссылке. Клиент делает `POST /api/template-link` (тот же заголовок initData) и получает `{ "url", "expires_in": 60 }`. `url` ведёт на `GET /api/template-file/{token}` без заголовка. Токен — HMAC от `user id` и времени истечения на `DJANGO_SECRET_KEY`. Просроченный токен — 401. Дальше `WebApp.downloadFile(url, "xray-template.xlsx")`. В веб-версии, если метода нет, клиент скачивает `GET /api/template` через `fetch` и сохраняет blob.

### 9.11. `POST /webhook/max`

Тело — объект Update MAX. 200 быстро. Подписка: `bot_started`, `message_created`, `message_callback`.

На любое из этих событий лаунчер отправляет одно и то же сообщение FR-2. Ветка по типу вложения, тексту команды и payload callback не нужна, кроме `answer_callback` на `message_callback`.

### 9.12. Документация API

- `GET /api/schema/` — OpenAPI 3.1 (spectacular).
- Файл `docs/openapi.yaml` кладётся в репозиторий при сдаче.
- При сдаче с собственным API — `DATA-API.yaml`: демо, диагноз, покрытие полей, шаблон. Метода отправки в чат в спецификации нет.

---

## 10. Вебхук лаунчера

| Событие | Действие |
|---------|----------|
| `bot_started` | Приветствие + одна кнопка `open_app` |
| `message_created`, любой текст, включая `/start` | То же сообщение |
| `message_created` с файлом | Файл игнорируется. То же сообщение. `Upload` не создаётся |
| `message_callback`, любой payload | `POST /answers`, затем то же сообщение |

Отдельных callback `demo` и `template` нет. Если они придут со старой клавиатуры — обрабатываются последней строкой таблицы, без расчёта.

---

## 11. Нефункциональные требования

**NFR-1.** `docker compose up --build` поднимает web, api, worker, db. Сборка ≤ 5 минут без учёта pull базовых образов.

**NFR-2.** Демо-снимок считается < 5 с на 500 строках.

**NFR-3.** Повторное прохождение основного сценария даёт тот же диагноз на том же файле.

**NFR-4.** Ошибка пользователя не роняет gunicorn. После 400/409 можно продолжить в мини-приложении.

**NFR-5.** Секреты не в git. `.env.example` без значений.

**NFR-6.** Логи: `upload_id`, число строк, имена колонок. Тело файла и телефоны не логировать. Вебхук логирует тип события, не тело файла.

**NFR-7.** Мини-приложение и API только HTTPS снаружи (требование MAX). В compose внутри сети HTTP.

**NFR-8.** Лимит: не больше 20 загрузок на пользователя в час, иначе 429.

**NFR-9.** Юнит-тесты `engine/` на 7 метрик, ноль и отрицательную сумму, меньше 5 выигранных сделок, повтор `deal_id`, разбор даты и синонима колонки. Минимум один API-тест демо и один тест лаунчера: файл в вебхуке не создаёт `Upload` (pytest-django). Подпись initData проверяется тестом на фиксированной строке и заранее посчитанном hex.

**NFR-10.** Падение Bot API не ломает мини-приложение. Диагноз, демо и шаблон доступны при открытом приложении, даже если отправка приветствия в чат вернула ошибку.

---

## 12. Docker и окружение

Сервисы compose:

- `db` — postgres:16-alpine, volume;
- `api` — gunicorn `config.wsgi:application`, порт 8000;
- `worker` — `python manage.py process_snapshots`;
- `web` — nginx, SPA + `proxy_pass /api` и `/webhook/max` на api. `client_max_body_size 21m;`, иначе файл отсечётся раньше лимита приложения.

Переменные:

```text
DJANGO_SECRET_KEY=
APP_ENV=hackathon
DEBUG_TOKEN=
MAX_BOT_TOKEN=
MAX_WEBHOOK_SECRET=
MAX_WEBHOOK_URL=https://<host>/webhook/max
PUBLIC_WEB_URL=https://<host>
DATABASE_URL=postgresql://xray:xray@db:5432/xray
LLM_API_KEY=
LLM_BASE_URL=
```

`MAX_BOT_TOKEN` нужен лаунчеру, чтобы отправить кнопку `open_app`, и кабинету MAX, чтобы привязать мини-приложение. Токен не участвует в расчёте снимка.

Порты снаружи: 443/80 на web. Postgres наружу не публиковать.

---

## 13. Безопасность и данные

1. Токен бота и ключи — только env. На фронт токен не попадает.
2. initData на каждый запрос `/api/*`, кроме `GET /api/template-file/{token}` и вебхука. Шаблон и демо с заголовком.
3. Объект чужого пользователя недоступен.
4. `MEDIA_ROOT` не монтировать в nginx как статику.
5. Тестовые данные — синтетика, пометка в README и презентации.
6. Удаление снимка — FR-29.
7. Перед LLM (если включён) — только агрегаты и анонимные `deal #N`.
8. Бот не получает содержимое снимка и не может отправить его в диалог. Утечки диагноза через чат в этой версии нет.

---

## 14. Критерии приёмки

Система принята, если:

1. Сценарий §5 проходит в MAX: бот только открывает приложение, дальше всё происходит в мини-приложении.
2. Файл, демо, шаблон, маппинг, диагноз и список сделок не требуют сообщения в чат.
3. Файл без части колонок даёт диагноз, а не 500.
4. Сообщение или файл в чат бота не создаёт `Upload` и не меняет снимки.
5. `docker compose up --build` воспроизводит стенд по README.
6. В репозитории нет секретов.
7. OpenAPI описывает методы §9 и не содержит `share-to-chat`.
8. Движок покрыт тестами на фиксированном CSV.
9. US-1: два своих снимка открываются по отдельности, чужой id в истории и по прямому запросу недоступен.
10. Нулевая сумма не роняет снимок. Повтор того же маппинга возвращает уже готовый снимок, а не второй.

---

## 15. Порядок реализации

1. Django-проект, модели, миграции, docker-compose с Postgres.
2. `engine/thresholds.yaml`, движок и тесты §6.3 на `data/demo_deals.csv`.
3. ingest + mapping + DRF uploads/snapshots/template.
4. Воркер `process_snapshots`.
5. Мини-приложение: Home (файл, демо, шаблон, история) → вход в сессию по `snapshot_id` → Diagnosis → MetricDetail → копирование заключения.
6. Лаунчер: webhook на любое событие отвечает одной кнопкой `open_app`. Проверить, что файл в чат не сохраняется.
7. Ошибки, лимиты, удаление снимка, README, OpenAPI.

Не начинать с визуала дашборда до зелёных тестов движка. Не реализовывать демо в чате, приём файла в чат и отправку диагноза ботом.

---
