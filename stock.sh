#!/bin/bash
set -euo pipefail

# Move to Jenkins workspace (or current directory when running locally)
cd "${WORKSPACE:-$(pwd)}"

echo "=========================================="
echo "1. Setting up Python virtual environment"
echo "=========================================="
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

if [ -f "requirements.txt" ]; then
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
else
  pip install --quiet yfinance pandas numpy plotly
fi

echo "=========================================="
echo "2. Running stock report scripts"
echo "=========================================="
python3 stockQuote.py
# Add any additional scripts below if needed:
# python3 dynamicFactor.py

echo "=========================================="
echo "3. Uploading reports to fastsnowboarder.com"
echo "=========================================="
LOG_FILE="upload.log"
MAX_LOG_LINES=500
REMOTE_DEST="fastsnow@fastsnowboarder.com:~/public_html/stock_report/"
MAX_RETRIES=3
RETRY_DELAY=15

# Trim upload.log to the most recent 500 lines
if [ -f "$LOG_FILE" ]; then
  tail -n "$MAX_LOG_LINES" "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

echo "=== Upload started: $(date) ===" | tee -a "$LOG_FILE"

for i in $(seq 1 "$MAX_RETRIES"); do
  if rsync -avz --partial \
    -e "ssh -o ConnectTimeout=15 -o ServerAliveInterval=30 -o ServerAliveCountMax=3" \
    stockHTML/*.html "$REMOTE_DEST" 2>&1 | tee -a "$LOG_FILE"; then
    echo "Upload succeeded on attempt $i: $(date)" | tee -a "$LOG_FILE"
    break
  fi

  if [ "$i" -eq "$MAX_RETRIES" ]; then
    echo "ERROR: Upload failed after $MAX_RETRIES attempts: $(date)" | tee -a "$LOG_FILE"
    exit 1
  fi

  echo "Attempt $i/$MAX_RETRIES failed. Retrying in ${RETRY_DELAY}s..." | tee -a "$LOG_FILE"
  sleep "$RETRY_DELAY"
done

echo "Done!"