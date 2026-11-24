#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

STOCKFILES_DIR="stockfiles"
OUTPUT_DIR="stockHTML"

# Activate Python virtual environment
if [ -f "/Users/michaellau/python2026/Stock2027/stocks2027/.venv/bin/activate" ]; then
    source /Users/michaellau/python2026/Stock2027/stocks2027/.venv/bin/activate
elif [ -f "/Users/michaellau/python2026/Stock2027/stocks2027/venv/bin/activate" ]; then
    source /Users/michaellau/python2026/Stock2027/stocks2027/venv/bin/activate
elif [ -f "/Users/michaellau/python2026/.venv/bin/activate" ]; then
    source /Users/michaellau/python2026/.venv/bin/activate
fi

# Verify the input directory exists
if [ ! -d "$STOCKFILES_DIR" ]; then
    echo "Error: Directory '$STOCKFILES_DIR' not found."
    exit 1
fi

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# 1. Process all text files
echo "=========================================="
echo "Starting Stock Analysis Pipeline"
echo "=========================================="

for file in "$STOCKFILES_DIR"/*.txt; do
    [ -e "$file" ] || continue

    echo "Running analysis for: $file"
    python3 stockQuote.py "$file"
done

# 2. Batch upload all HTML files from stockHTML
echo "=========================================="
echo "Uploading reports to fastsnowboarder.com..."
echo "=========================================="

MAX_RETRIES=3
RETRY_DELAY=5
COUNT=0
SUCCESS=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    rsync -avz --partial --timeout=30 \
        -e "ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3" \
        stockHTML/*.html fastsnow@fastsnowboarder.com:~/public_html/stock_report/

    if [ $? -eq 0 ]; then
        SUCCESS=true
        echo "Upload completed successfully."
        break
    fi

    COUNT=$((COUNT + 1))
    echo "Upload failed (attempt $COUNT of $MAX_RETRIES). Retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
done

if [ "$SUCCESS" = false ]; then
    echo "ERROR: Upload failed after $MAX_RETRIES attempts."
    exit 1
fi