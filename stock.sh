#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

STOCKFILES_DIR="stockfiles"
OUTPUT_DIR="stockHTML"

# Activate Python virtual environment
source .venv/bin/activate

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

if compgen -G "$OUTPUT_DIR/*.html" > /dev/null; then
    scp "$OUTPUT_DIR"/*.html fastsnow@fastsnowboarder.com:~/public_html/stock_report/
    echo "All HTML files from '$OUTPUT_DIR/' successfully uploaded."
else
    echo "Warning: No .html files found in '$OUTPUT_DIR/' to upload."
fi