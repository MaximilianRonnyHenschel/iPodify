@echo off
setlocal

cd /d "%~dp0"
flet build apk --yes --module-name gui .
