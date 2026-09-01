@echo off
title AutoShorts AI - Gerador de Shorts do YouTube
chcp 65001 > nul
cls
echo =====================================================================
echo  ⚡ AutoShorts AI - Gerador Inteligente de Shorts do YouTube
echo  100%% Gratuito ^| Legendas Virais ^| Marca d'Água ^| Formato 9:16
echo =====================================================================
echo.
echo [1/2] Verificando dependencias Python...
python -m pip install -r requirements.txt --quiet
echo [2/2] Iniciando aplicacao e abrindo navegador...
echo.
python start.py
pause
