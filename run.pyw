# -*- coding: utf-8 -*-
"""雙擊這個檔就能啟動 FAL Studio（不會跳出黑色主控台視窗）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.main import main

if __name__ == "__main__":
    main()
