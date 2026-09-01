@echo off
chcp 65001 > nul
title Sanesca Telemetria Bot (@SanescaAIBot)
echo ===================================================
echo Iniciando Servicio de Telemetria y Despacho Sanesca
echo ===================================================
cd /d "%~dp0"
python main.py
pause
