$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

Write-Host "Preparing Hugging Face Space files..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe tools\prepare_hf_space.py

Write-Host "Checking Hugging Face login..." -ForegroundColor Cyan
.\.venv\Scripts\hf.exe auth whoami

Write-Host "Creating free Docker Space if needed..." -ForegroundColor Cyan
.\.venv\Scripts\hf.exe repos create MEONN/weather-risk-assistant --type space --space-sdk docker --exist-ok

Write-Host "Uploading core service files..." -ForegroundColor Cyan
.\.venv\Scripts\hf.exe upload MEONN/weather-risk-assistant .hf-space-build --type space --commit-message "Deploy weather risk assistant"

Write-Host ""
Write-Host "Done. Space URL:" -ForegroundColor Green
Write-Host "https://meonn-weather-risk-assistant.hf.space" -ForegroundColor Green
Read-Host "Press Enter to close"
