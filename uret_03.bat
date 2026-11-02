@echo off
chcp 65001 >nul
set FLOW_API_URL=http://127.0.0.1:8000
cd /d "C:\Users\yahowa\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\scratch-workspaces\32a64456-85c9-45f5-8b4d-ee040224c3ac\a930890e-456b-4c02-a40d-d29cc3fddf62\scratch-2026-10-26-5e6450"
python -u tools\apibatch.py videolar\03-humans-vanished
pause
