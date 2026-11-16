@echo off
REM AeroFox + link publico gratuito, com supervisor (reinicia sozinho o que cair).
REM   Padrao: Cloudflare Quick Tunnel (link https://....trycloudflare.com, muda a cada reinicio do tunel).
REM   Link FIXO gratuito: defina AEROFOX_TUNNEL=tailscale (ou cloudflare-named) no arquivo .env
REM   - veja docs\ESTABILIDADE.md.
REM Somente a porta do AeroFox e publicada; o servidor do modelo continua em 127.0.0.1.
setlocal
cd /d "%~dp0"
title AeroFox - servidor publico (nao feche esta janela)
set "PORT=8012"
if not defined AEROFOX_TUNNEL set "AEROFOX_TUNNEL=cloudflare"
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /i "AEROFOX_TUNNEL=" .env 2^>nul`) do set "AEROFOX_TUNNEL=%%b"

REM ---- 1. Python e ambiente privado (.venv)
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (where python >nul 2>nul && set "PYEXE=python")
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if not defined PYEXE (
  echo [AeroFox] ERRO: Python nao encontrado. Instale Python 3.11 ou 3.12 64-bit em https://www.python.org/downloads/windows/
  goto :fim
)
%PYEXE% scripts\launch.py --setup-only
if errorlevel 1 goto :fim
set "PYEXE=.venv\Scripts\python.exe"

REM ---- 2. Cliente do tunel
if /i "%AEROFOX_TUNNEL%"=="tailscale" goto :porta
set "CF="
where cloudflared >nul 2>nul && set "CF=cloudflared"
if not defined CF if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" set "CF=1"
if not defined CF if exist "%ProgramFiles%\cloudflared\cloudflared.exe" set "CF=1"
if not defined CF (
  echo [AeroFox] O cliente cloudflared ^(gratuito, oficial da Cloudflare^) nao esta instalado.
  choice /C SN /M "Instalar agora com winget (Cloudflare.cloudflared)"
  if errorlevel 2 goto :fim
  winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
)

:porta
REM ---- 3. A porta precisa estar livre
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
  echo [AeroFox] A porta %PORT% ja esta em uso. Feche a outra janela do AeroFox ^(ou o programa que usa a porta^) e tente de novo.
  goto :fim
)

REM ---- 4. Supervisor: modelo local + aplicacao + tunel, com verificacao a cada 10 s e reinicio automatico.
REM      Se o proprio supervisor cair, esta janela o inicia de novo apos 10 s.
echo.
echo [AeroFox] Iniciando. Na primeira vez o modelo pode levar varios minutos para baixar e carregar.
echo [AeroFox] O LINK PUBLICO aparece abaixo como "PUBLIC LINK" e fica salvo em logs\public_url.txt
echo [AeroFox] Estado atual: logs\status.json   Registros: pasta logs\   Para encerrar: Ctrl+C
echo.
:supervisor
%PYEXE% scripts\supervisor.py --port %PORT% --tunnel %AEROFOX_TUNNEL% %*
if errorlevel 1 (
  echo [AeroFox] O supervisor parou inesperadamente. Reiniciando em 10 s ^(feche a janela para cancelar^)...
  timeout /t 10 >nul
  goto :supervisor
)

:fim
echo.
pause
