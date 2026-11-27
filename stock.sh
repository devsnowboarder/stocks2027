#!/bin/bash
set -e

echo "=========================================="
echo "1. Setting up Python environment..."
echo "=========================================="
cd "$WORKSPACE"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ -f "requirements.txt" ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
else
    pip install --upgrade pip yfinance pandas numpy plotly
fi

echo "=========================================="
echo "2. Running stock report script..."
echo "=========================================="
if [ -f "stock.sh" ]; then
    chmod +x stock.sh
    ./stock.sh
elif [ -f "stockQuote.py" ]; then
    python3 stockQuote.py
else
    echo "Error: Neither stock.sh nor stockQuote.py found in $WORKSPACE"
    exit 1
fi

echo "=========================================="
echo "3. Uploading reports to fastsnowboarder.com/stock_report/..."
echo "=========================================="
SOURCE_DIR="./"
if [ -d "stockHTML" ]; then
    SOURCE_DIR="stockHTML/"
fi


if rsync -avz --include="*.html" --exclude="*" "$SOURCE_DIR" fastsnow@fastsnowboarder.com:~/public_html/stock_report/; then
    echo "Upload completed successfully to https://fastsnowboarder.com/stock_report/"
else
    echo "Upload failed!"
    exit 1
fi