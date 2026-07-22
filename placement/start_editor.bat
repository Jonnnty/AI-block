@echo off
cd /d "%~dp0"
set PORT=8080
set HOST=127.0.0.1
echo.
echo ========================================
echo   场景编辑器本地服务
echo   http://127.0.0.1:8080/placement_editor.html
echo   请用此地址打开（不要用 github.io）
echo   Ctrl+C 停止
echo ========================================
echo.
start "" "http://127.0.0.1:8080/placement_editor.html"
python -u serve_editor.py
pause
