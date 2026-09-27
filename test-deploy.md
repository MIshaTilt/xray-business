# Руководство: Запуск проекта X-Ray с порт-форвардингом на VPS

Данная инструкция описывает, как поднять локальное окружение разработки (Django + Vite) и пробросить его через обратный SSH-туннель на production-сервер VPS с настроенным доменным именем и валидным SSL-сертификатом (**https://xray-business-bot.online**).

Такая схема позволяет тестировать веб-приложение непосредственно внутри **MAX MiniApp** и мобильных WebView с поддержкой мгновенной горячей перезагрузки (HMR) и подключением к живому локальному коду бэкенда и LLM.

---

## 1. Архитектура связки

```
               [ Пользователь / MAX MiniApp ]
                            │ (HTTPS:443)
                            ▼
           [ VPS Сервер (IP: 87.120.165.142) ]
              Nginx: xray-business-bot.online
              ├── /api, /admin, /static ──► http://127.0.0.1:8000
              └── / (SPA + Vite HMR)   ──► http://127.0.0.1:5173
                            │
               ▲▲▲ SSH Reverse Tunnel (-R) ▲▲▲
                            │
              [ Ваша локальная машина (Windows) ]
              ├── Django Backend (127.0.0.1:8000)
              └── Vite Frontend  (127.0.0.1:5173)
```

* **Nginx на VPS:** принимает внешний защищенный HTTPS-трафик на 443 порту, снимает SSL и перенаправляет запросы на локальные порты VPS (`8000` и `5173`).
* **SSH Reverse Tunnel:** связывает порты на VPS с портами на вашем компьютере.
* **Локальный Django & Vite:** обрабатывают запросы, выполняют скрипты и отдают код прямо из вашей рабочей директории.

---

## 2. Предварительные требования

1. **Python 3.10+** с настроенным виртуальным окружением в `xray-be/venv`.
2. **Node.js 18+** и установленные зависимости в `xray-fe` (`npm install`).
3. **SSH-клиент** в системе (встроен в Windows 10/11: `ssh.exe`).
4. Наличие доступа по SSH-ключу к серверу `root@87.120.165.142`.

---

## 3. Настройка переменных окружения

### Бэкенд (`xray-be/.env`)
Убедитесь, что в файле `xray-be/.env` указаны доверенные хосты и домен для обхода CSRF:

```env
OPENAI_BASE_URL=http://144.31.157.209:8317/v1
OPENAI_API_KEY=sk-TnEv9ZcsfpQN3n40amQjP377qkMOOndbkIyrOveacIUX6
OPENAI_MODEL=gemini-3.8-flash-high
CSRF_TRUSTED_ORIGINS=https://xray-business-bot.online,https://www.xray-business-bot.online
ALLOWED_HOSTS=*
```

### Фронтенд (`xray-fe/.env.local`)
В `xray-fe/.env.local` параметр `VITE_API_URL` должен быть пустым — тогда все API-запросы будут отправляться относительно текущего домена (`https://xray-business-bot.online/api/...`), что предотвращает ошибки смешанного контента (Mixed Content) и CORS:

```env
VITE_API_URL=
VITE_USE_FIXTURES=false
VITE_DEBUG_TOKEN=hackathon-debug
VITE_DEBUG_USER=1001
```

---

## 4. Пошаговый запуск (3 терминала)

Для полноценной работы необходимо запустить три процесса в отдельных окнах терминала (PowerShell или CMD).

### Терминал 1: Бэкенд Django

```powershell
cd C:\Users\mdsv\Documents\Dev\xray-business\xray-be
.\venv\Scripts\python.exe xray_be\manage.py migrate
.\venv\Scripts\python.exe xray_be\manage.py runserver 127.0.0.1:8000
```
> Сервер Django запустится на `http://127.0.0.1:8000/`.

---

### Терминал 2: Фронтенд Vite

```powershell
cd C:\Users\mdsv\Documents\Dev\xray-business\xray-fe
npm run dev
```
> Vite dev-сервер запустится на `http://localhost:5173/`.

---

### Терминал 3: Обратный SSH-туннель на VPS

> [!IMPORTANT]
> Если на VPS запущен системный сервис бэкенда (`xray-api.service`), он занимает порт `8000` на сервере. Перед запуском туннеля временно остановите его командой:
> ```powershell
> ssh.exe root@87.120.165.142 "systemctl stop xray-api.service"
> ```

Запустите команду проброса портов:

```powershell
ssh.exe -N -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -R 5173:127.0.0.1:5173 -R 8000:127.0.0.1:8000 root@87.120.165.142
```

#### Разбор флагов команды:
* `-N`: не открывать интерактивную командную строку на сервере, использовать сессию только для туннелирования.
* `-R 5173:127.0.0.1:5173`: перенаправлять порт `5173` на VPS на ваш локальный `127.0.0.1:5173` (Vite).
* `-R 8000:127.0.0.1:8000`: перенаправлять порт `8000` на VPS на ваш локальный `127.0.0.1:8000` (Django).
* `-o ServerAliveInterval=15`: отправлять keep-alive пинг серверу каждые 15 секунд, чтобы туннель не засыпал.
* `-o ServerAliveCountMax=3`: закрыть сессию, если сервер не ответил на 3 пинга подряд.
* `-o ExitOnForwardFailure=yes`: завершить команду с ошибкой, если хотя бы один из портов на сервере занят (не допускает частичного проброса).

---

## 5. Конфигурация Nginx на VPS (Справочно)

На VPS сервере `87.120.165.142` активна следующая конфигурация Nginx (файл в репозитории: `nginx_xray.conf`):

```nginx
server {
    server_name xray-business-bot.online www.xray-business-bot.online;
    client_max_body_size 25m;

    # API endpoints -> локальный Django (порт 8000)
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off; # Обязательно для SSE-стриминга ответов LLM!
        proxy_cache off;
        proxy_read_timeout 180s;
        gzip off;
    }

    # Панель администратора Django
    location /admin {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }

    # Статика Django (стили админки)
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend SPA и Vite WebSocket (HMR) -> порт 5173
    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/xray-business-bot.online/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/xray-business-bot.online/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

# Редирект HTTP -> HTTPS
server {
    listen 80;
    server_name xray-business-bot.online www.xray-business-bot.online;
    return 301 https://$host$request_uri;
}
```

---

## 6. Проверка работоспособности

После запуска всех трёх процессов проверьте соединение:

1. **Проверка API через туннель:**
   ```powershell
   curl.exe -I https://xray-business-bot.online/api/amo
   ```
   Должен вернуться статус `HTTP/2 200`.

2. **Проверка фронтенда:**
   Откройте в браузере: `https://xray-business-bot.online/`.
   Должен отображаться главный экран X-Ray со всеми источниками данных и возможностью загрузки файлов или подключения amoCRM.

3. **Проверка в MAX MiniApp:**
   Откройте приложение внутри клиента MAX через бота или прямую ссылку MiniApp. Проверьте:
   * Наличие кнопки «Назад» в шапке при переходе в снимок.
   * Работу чата с консультантом и стриминг ответов.
   * Переходы между вкладками.

---

## 7. Устранение неполадок (FAQ)

### Ошибка: `Warning: remote port forwarding failed for listen port 8000` (или 5173)
* **Причина:** На VPS порт `8000` или `5173` занят зависшей предыдущей SSH-сессией.
* **Решение:** Подключитесь к VPS по SSH и освободите порт:
  ```bash
  ssh root@87.120.165.142
  fuser -k 8000/tcp 5173/tcp
  exit
  ```
  После этого перезапустите туннель на локальной машине.

### Ошибка: `502 Bad Gateway` в браузере при открытии домена
* **Причина:** Либо не запущен локальный Vite (`5173`) / Django (`8000`), либо упал SSH-туннель.
* **Решение:** Убедитесь, что все 3 терминала (Django, Vite, SSH) активны и не содержат ошибок в консоли.

### Стриминг чата зависает или выдает ответ только целиком в конце
* **Причина:** Включена буферизация прокси в Nginx.
* **Решение:** В блоке `location /api` конфигурации Nginx на VPS обязательно должна присутствовать директива `proxy_buffering off;`.
