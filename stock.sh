#!/bin/bash
source .venv/bin/activate 
python3 -m pip install yfinance
eoch "compiling the Stock Quote program"
python3 stockQuote.py
echo "Uploading michaelResearch.html"
scp michaelResearch.html fastsnow@fastsnowboarder.com:~/public_html/stock_report
