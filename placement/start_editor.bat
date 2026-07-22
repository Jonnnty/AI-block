@echo off
cd /d "%~dp0"
set PORT=8080
set HOST=127.0.0.1
echo 启动场景编辑器服务器...
echo 浏览器打开: http://127.0.0.1:8080/placement_editor.html
python -u serve_editor.py
pause
