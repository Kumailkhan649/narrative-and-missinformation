$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose build migrate ai08
if ($LASTEXITCODE -ne 0) { throw "DOCKER BUILD FAILED" }
docker compose up -d db
if ($LASTEXITCODE -ne 0) { throw "POSTGRES START FAILED" }
docker compose run --rm migrate
if ($LASTEXITCODE -ne 0) { throw "MIGRATION FAILED" }
docker compose run --rm --no-deps -e AI08_TEST_DATABASE=1 ai08 python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "UNIT OR INTEGRATION TESTS FAILED" }
docker compose run --rm --no-deps ai08 python tools/check_no_comments.py
if ($LASTEXITCODE -ne 0) { throw "CODE CHECK FAILED" }
Write-Host "AI-08 BACKEND CHECKS PASSED" -ForegroundColor Green
