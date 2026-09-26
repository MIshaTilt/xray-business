@echo off
start "X-Ray API" cmd /k "cd /d D:\Unity\Projects\xray-business\xray-be\xray_be && python manage.py runserver"
start "X-Ray UI" cmd /k "cd /d D:\Unity\Projects\xray-business\xray-fe && set PATH=C:\Program Files\nodejs;%PATH% && npm.cmd run dev"
echo.
echo Откройте в браузере: http://localhost:5173/
echo Два чёрных окна не закрывайте.
pause
