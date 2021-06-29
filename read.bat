@echo off
cd /d %appdata%\..\..\GitHub\bilibili_danmaku
venv\Scripts\activate & cd /d %appdata%\..\..\GitHub\bilibili_danmaku & py.exe -m danmaku_app
pause
