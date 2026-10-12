@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo   LawSaaS - جاري رفع التحديثات إلى GitHub و Railway
echo ========================================================
echo.

git add .
git commit -m "fix(reports): comprehensive resilience and error handling updates" 2>nul
git push origin main

echo.
echo ========================================================
echo   تم الرفع بنجاح! ستقوم منصة Railway بالبناء التلقائي الآن.
echo ========================================================
pause
