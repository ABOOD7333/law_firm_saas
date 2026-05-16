@echo off
cd /d "%~dp0"
echo Preparing to upload changes to GitHub and Railway...
echo.

git add .
git commit -m "Implement SaaS manual subscription flow with receipt uploads and SuperAdmin approvals"
git push origin main

echo.
echo Deployment triggered! Railway will now automatically update your site.
pause
