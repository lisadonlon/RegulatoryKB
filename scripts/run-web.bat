@echo off
cd /d C:\Projects\RegulatoryKB
set PYTHONPATH=C:\Users\Lisa_\AppData\Roaming\Python\Python313\site-packages;%PYTHONPATH%
C:\Python313\python.exe -m uvicorn regkb.web.main:app --host 127.0.0.1 --port 8000
