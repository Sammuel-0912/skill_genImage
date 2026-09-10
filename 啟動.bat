@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import PySide6" 2>nul || (
  echo 第一次啟動，正在安裝 PySide6...
  python -m pip install PySide6
)
start "" pythonw run.pyw
