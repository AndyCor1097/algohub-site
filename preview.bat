@echo off
cd /d "%~dp0"
python sync.py
streamlit run app.py
