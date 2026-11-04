import yfinance as yf
import plotly.express as px
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import os
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# ==========================================
# 0. READ TICKERS FROM FILE
# 1. Using AI to help me write this code
# ==========================================
print("Reading tickers from 'stocklist.txt'...")

tickers = []
filename = "stocklist.txt"

if os.path.exists(filename):
    with open(filename, "r") as file:
        tickers = [line.strip().upper() for line in file if line.strip()]
else:
    print(f"Error: '{filename}' not found. Please create it with one ticker symbol per line.")
    print("Using default tickers for now...")
    tickers = ["AAPL", "MSFT", "TSLA", "GOOGL", "AMZN", "META", "NFLX", "NVDA", "AMD"]

print(f"Loaded {len(tickers)} tickers total. Processing data...\n")

# ==========================================
# 1. FETCH STOCK DATA & COLLECT TABLE DATA
# ==========================================
summary_table_data = []
stock_history_dict = {}

for ticker in tickers:
    stock_data = yf.Ticker(ticker)
    # Fetching 2 years so the 200-day SMA has enough historical data to calculate fully across the 1-year chart
    history = stock_data.history(period="2y").reset_index()

    try:
        info = stock_data.info

        # P/E Ratio
        pe_ratio = info.get('trailingPE', None)
        pe_display = f"{pe_ratio:.2f}" if pe_ratio else "N/A"

        # Earnings Per Share (EPS)
        eps = info.get('trailingEps', None)
        eps_display = f"${eps:.2f}" if eps else "N/A"

        # Dividend Yield
        div_yield = info.get('dividendYield', None)
        if div_yield is None:
            div_yield = info.get('trailingAnnualDividendYield', None)

        if div_yield is not None:
            div_display = f"{div_yield * 100:.2f}%"
        else:
            div_display = "N/A"

        # Analyst Consensus
        rec_key = info.get('recommendationKey', None)
        if rec_key and rec_key != "none":
            rec_display = rec_key.replace('_', ' ').title()
        else:
            rec_display = "N/A"

        # Mean Target Price
        target_price = info.get('targetMeanPrice', None)
        target_display = f"${target_price:.2f}" if target_price else "N/A"

        # Volatility and Range
        beta = info.get('beta', None)
        beta_display = f"{beta:.2f}" if beta else "N/A"

        fifty_two_week_low = info.get('fiftyTwoWeekLow', None)
        low_display = f"${fifty_two_week_low:.2f}" if fifty_two_week_low else "N/A"

        fifty_two_week_high = info.get('fiftyTwoWeekHigh', None)
        high_display = f"${fifty_two_week_high:.2f}" if fifty_two_week_high else "N/A"

        # Fetch Earnings Date safely
        earnings_date_display = "N/A"
        days_to_earnings = None
        try:
            cal = stock_data.calendar
            next_date = None

            # Handle both dictionary and DataFrame formats returned by different yfinance versions
            if isinstance(cal, dict) and 'Earnings Date' in cal and cal['Earnings Date']:
                next_date = pd.to_datetime(cal['Earnings Date'][0]).tz_localize(None)
            elif hasattr(cal, 'empty') and not cal.empty and 'Earnings Date' in cal.columns:
                next_date = pd.to_datetime(cal['Earnings Date'].iloc[0]).tz_localize(None)

            if next_date:
                today = pd.Timestamp.now().tz_localize(None)
                days_to_earnings = (next_date - today).days
                if days_to_earnings >= 0:
                    earnings_date_display = next_date.strftime('%Y-%m-%d')
                else:
                    days_to_earnings = None  # Date has already passed
        except Exception:
            pass

    except Exception:
        pe_display = "N/A"
        eps_display = "N/A"
        div_display = "N/A"
        rec_display = "N/A"
        target_display = "N/A"
        beta_display = "N/A"
        low_display = "N/A"
        high_display = "N/A"

    if len(history) >= 2:
        last_idx = history.index[-1]
        prev_idx = history.index[-2]

        latest_close = history.loc[last_idx, 'Close']
        prev_close = history.loc[prev_idx, 'Close']
        latest_volume = history.loc[last_idx, 'Volume']
        price_diff = latest_close - prev_close

        # Using numerical values for easier sorting, formatting will happen in HTML rendering
        summary_table_data.append({
            'Ticker': ticker,
            'Prev_Close': prev_close,
            'Close': latest_close,
            'Diff': price_diff,
            'Volume': latest_volume,
            'PE': pe_ratio if pe_ratio else 0,
            'PE_Display': pe_display,
            'EPS': eps if eps else 0,
            'EPS_Display': eps_display,
            'Div': div_yield if div_yield else 0,
            'Div_Display': div_display,
            'Rec': rec_display,
            'Target': target_display,
            'Beta': beta if beta else 0,
            'Beta_Display': beta_display,
            'Low': fifty_two_week_low if fifty_two_week_low else 0,
            'Low_Display': low_display,
            'High': fifty_two_week_high if fifty_two_week_high else 0,
            'High_Display': high_display,
            'Earnings_Date': earnings_date_display,
            'Days_To_Earnings': days_to_earnings

        })

        stock_history_dict[ticker] = history
    else:
        print(f"Warning: Not enough data found for ticker '{ticker}'. Skipping...")

# ==========================================
# 2. BUILD MARKET INDICES CHARTS (DOW & NASDAQ)
# ==========================================
print("Fetching Dow Jones and Nasdaq data...")
indices = {"Dow Jones Industrial Average": "^DJI", "Nasdaq Composite": "^IXIC"}
index_charts = []

for name, ticker in indices.items():
    idx_data = yf.Ticker(ticker).history(period="1y").reset_index()
    if not idx_data.empty:
        fig_idx = px.line(idx_data, x='Date', y='Close',
                          title=f'{name} (1 Year)',
                          labels={'Close': 'Index Value'})

        if name == "Nasdaq Composite":
            fig_idx.update_traces(line_color='yellow')

        max_val = idx_data['Close'].max()
        max_date = idx_data.loc[idx_data['Close'].idxmax(), 'Date']
        min_val = idx_data['Close'].min()
        min_date = idx_data.loc[idx_data['Close'].idxmin(), 'Date']
        latest_val = idx_data['Close'].iloc[-1]
        latest_date = idx_data['Date'].iloc[-1]

        fig_idx.add_annotation(
            x=max_date, y=max_val, text=f"High: {max_val:,.2f}",
            showarrow=True, arrowhead=2, arrowcolor="white", ax=0, ay=-30, font=dict(color="lime", size=12)
        )
        fig_idx.add_annotation(
            x=min_date, y=min_val, text=f"Low: {min_val:,.2f}",
            showarrow=True, arrowhead=2, arrowcolor="white", ax=0, ay=30, font=dict(color="red", size=12)
        )
        fig_idx.add_annotation(
            x=latest_date, y=latest_val, text=f"Close: {latest_val:,.2f}",
            showarrow=True, arrowhead=2, arrowcolor="white", ax=-40, ay=0, font=dict(color="cyan", size=12)
        )

        fig_idx.update_layout(
            width=490, height=350,
            plot_bgcolor='black', paper_bgcolor='black',
            font=dict(color='white', size=12),
            title=dict(font=dict(size=18)),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#333333'),
            margin=dict(l=40, r=20, t=50, b=30)
        )
        index_charts.append(fig_idx.to_html(full_html=False, include_plotlyjs='cdn'))

indices_html = f"""
<div style="display: flex; justify-content: center; gap: 20px; padding-top: 20px;">
    {''.join(index_charts)}
</div>
"""

# ==========================================
# 3. BUILD THE HTML TABLE FOR LATEST PRICES
# ==========================================
# Added ID 'summaryTable' for DataTables JS initialization
table_html = """
<div style="display: flex; justify-content: center; margin-top: 20px; margin-bottom: 30px; max-width: 1300px; margin-left: auto; margin-right: auto;">
    <table id="summaryTable" style="color: white; border-collapse: collapse; font-family: Arial, sans-serif; width: 100%; text-align: center; border: 1px solid #444;">
        <thead>
            <tr style="background-color: #222; border-bottom: 2px solid cyan;">
                <th style="padding: 12px; font-size: 16px;">Ticker</th>
                <th style="padding: 12px; font-size: 16px;">Prev Close</th>
                <th style="padding: 12px; font-size: 16px;">Latest Close</th>
                <th style="padding: 12px; font-size: 16px;">Diff</th>
                <th style="padding: 12px; font-size: 16px;">Volume</th>
                <th style="padding: 12px; font-size: 16px;">P/E</th>
                <th style="padding: 12px; font-size: 16px; color: #ff9900;">EPS</th>
                <th style="padding: 12px; font-size: 16px; color: #ff9900;">Div Yield</th>
                <th style="padding: 12px; font-size: 16px; color: #00ffcc;">Beta</th>
                <th style="padding: 12px; font-size: 16px; color: #00ffcc;">52W Low</th>
                <th style="padding: 12px; font-size: 16px; color: #00ffcc;">52W High</th>
            </tr>
        </thead>
        <tbody>
"""

for data in summary_table_data:
    diff_val = data['Diff']
    diff_color = "lime" if diff_val >= 0 else "red"
    diff_sign = "+" if diff_val >= 0 else ""

    # Using data-order attribute so DataTables sorts by the raw number instead of the formatted string
    table_html += f"""
            <tr style="border-bottom: 1px solid #333; background-color: transparent;">
                <td style="padding: 12px; font-weight: bold; color: cyan;">{data['Ticker']}</td>
                <td style="padding: 12px;" data-order="{data['Prev_Close']}">${data['Prev_Close']:.2f}</td>
                <td style="padding: 12px;" data-order="{data['Close']}">${data['Close']:.2f}</td>
                <td style="padding: 12px; font-weight: bold; color: {diff_color};" data-order="{diff_val}">{diff_sign}${diff_val:.2f}</td>
                <td style="padding: 12px;" data-order="{data['Volume']}">{int(data['Volume']):,}</td>
                <td style="padding: 12px; font-weight: bold;" data-order="{data['PE']}">{data['PE_Display']}</td>
                <td style="padding: 12px; font-weight: bold; color: #ff9900;" data-order="{data['EPS']}">{data['EPS_Display']}</td>
                <td style="padding: 12px; font-weight: bold; color: #ff9900;" data-order="{data['Div']}">{data['Div_Display']}</td>
                <td style="padding: 12px; font-weight: bold; color: #00ffcc;" data-order="{data['Beta']}">{data['Beta_Display']}</td>
                <td style="padding: 12px; font-weight: bold; color: #00ffcc;" data-order="{data['Low']}">{data['Low_Display']}</td>
                <td style="padding: 12px; font-weight: bold; color: #00ffcc;" data-order="{data['High']}">{data['High_Display']}</td>
            </tr>
    """

table_html += """
        </tbody>
    </table>
</div>
"""

# ==========================================
# 4. BUILD INDIVIDUAL CHARTS, NEWS, & OPTIONS
# ==========================================
print("Generating individual charts with SMAs, MACD, RSI, fetching news, and calculating options ROC...")

details_html = """
<div style='color: white; font-family: Arial, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px;'>
    <h1 style='border-bottom: 1px solid #333; margin-top: 40px;'>Stock Analysis & Latest News</h1>
"""

for ticker in tickers:
    ticker_info = next((item for item in summary_table_data if item["Ticker"] == ticker), None)

    if ticker_info:
        badge_html = ""
        dte = ticker_info.get('Days_To_Earnings')

        if dte is not None:
            if dte <= 14:
                badge_html = f" <span style='background-color: red; color: white; font-size: 14px; padding: 4px 8px; border-radius: 5px; vertical-align: middle; margin-left: 15px; font-weight: bold;'>⚠️ Earnings in {dte} Days ({ticker_info['Earnings_Date']})</span>"
            elif dte <= 30:
                badge_html = f" <span style='background-color: darkorange; color: white; font-size: 14px; padding: 4px 8px; border-radius: 5px; vertical-align: middle; margin-left: 15px; font-weight: bold;'>⚠️ Earnings in {dte} Days ({ticker_info['Earnings_Date']})</span>"

        header_extra = (f" <span style='color: white;'>- ${ticker_info['Close']:.2f}</span> "
                        f"<span style='color: #888; font-size: 16px;'>| EPS: {ticker_info['EPS_Display']} | Div: {ticker_info['Div_Display']} "
                        f"| Target: {ticker_info['Target']} | Consensus: {ticker_info['Rec']}</span>"
                        f"{badge_html}")
    else:
        header_extra = "" 

    details_html += f"<h2 style='color: cyan; margin-top: 50px; border-bottom: 1px dashed #444; padding-bottom: 5px;'>{ticker} Overview{header_extra}</h2>"

    # --- ADD INDIVIDUAL PLOTLY CHART WITH SMAs, MACD, and RSI ---
    df = stock_history_dict.get(ticker)
    if df is not None and not df.empty:
        # Calculate Simple Moving Averages
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()

        # Calculate MACD (12, 26, 9)
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # Calculate 14-day RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / 14, adjust=False).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # Trim to the last ~252 trading days (1 year) for display
        df_plot = df.tail(252).copy()

        # Create subplots: 3 rows, 1 column
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                            vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25])

        # Row 1: Price and SMAs
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['Close'], mode='lines', name='Close Price',
                                 line=dict(color='#00ffcc')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['SMA_50'], mode='lines', name='50-Day SMA',
                                 line=dict(color='magenta', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['SMA_200'], mode='lines', name='200-Day SMA',
                                 line=dict(color='orange', width=1.5)), row=1, col=1)

        # Row 2: MACD
        # Color histogram based on whether it is positive or negative
        colors = ['lime' if val >= 0 else 'red' for val in df_plot['MACD_Hist']]
        fig.add_trace(go.Bar(x=df_plot['Date'], y=df_plot['MACD_Hist'], name='MACD Hist', marker_color=colors), row=2,
                      col=1)
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['MACD'], mode='lines', name='MACD',
                                 line=dict(color='cyan', width=1.5)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['MACD_Signal'], mode='lines', name='Signal',
                                 line=dict(color='yellow', width=1.5)), row=2, col=1)

        # Row 3: RSI
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['RSI_14'], mode='lines', name='RSI (14)',
                                 line=dict(color='yellow', width=1.5)), row=3, col=1)
        # Add Oversold/Overbought thresholds
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="lime", row=3, col=1)

        # Annotate latest close price
        latest_val = df_plot['Close'].iloc[-1]
        latest_date = df_plot['Date'].iloc[-1]
        fig.add_annotation(
            x=latest_date, y=latest_val, text=f"Close: {latest_val:,.2f}",
            showarrow=True, arrowhead=2, arrowcolor="white", ax=-40, ay=0, font=dict(color="#00ffcc", size=12), row=1,
            col=1
        )

        fig.update_layout(
            height=700,
            plot_bgcolor='black', paper_bgcolor='black',
            font=dict(color='white', size=12),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#333333'),
            xaxis2=dict(showgrid=False), yaxis2=dict(showgrid=True, gridcolor='#333333', title="MACD"),
            xaxis3=dict(showgrid=False), yaxis3=dict(showgrid=True, gridcolor='#333333', title="RSI", range=[0, 100]),
            margin=dict(l=40, r=20, t=30, b=30),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        chart_div = fig.to_html(full_html=False, include_plotlyjs='cdn')
        details_html += f"<div style='margin-bottom: 20px;'>{chart_div}</div>"
    else:
        details_html += "<p style='color: red;'>No chart data available for this ticker.</p>"

    # --- ADD NEWS COLUMNS ---
    details_html += "<div style='display: flex; justify-content: space-between; gap: 15px; margin-bottom: 30px;'>"

    # Source 1: Google News
    details_html += "<div style='flex: 1;'>"
    details_html += "<h3 style='color: #aaa;'>Google News</h3><ul style='line-height: 1.6; padding-left: 20px;'>"
    google_rss_url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
    try:
        response = requests.get(google_rss_url)
        root = ET.fromstring(response.content)
        articles = root.findall('.//channel/item')
        if articles:
            for article in articles[:4]:
                title = article.find('title').text
                link = article.find('link').text
                details_html += f"<li><a href='{link}' target='_blank' style='color: #4da6ff; text-decoration: none;'>{title}</a></li>"
        else:
            details_html += "<li style='color: #888;'>No news found.</li>"
    except Exception as e:
        details_html += f"<li style='color: red;'>Error: {e}</li>"
    details_html += "</ul></div>"

    # Source 2: CNBC
    details_html += "<div style='flex: 1;'>"
    details_html += "<h3 style='color: #aaa;'>CNBC</h3><ul style='line-height: 1.6; padding-left: 20px;'>"
    cnbc_rss_url = f"https://news.google.com/rss/search?q={ticker}+stock+site:cnbc.com&hl=en-US&gl=US&ceid=US:en"
    try:
        response = requests.get(cnbc_rss_url)
        root = ET.fromstring(response.content)
        articles = root.findall('.//channel/item')
        if articles:
            for article in articles[:4]:
                title = article.find('title').text
                link = article.find('link').text
                details_html += f"<li><a href='{link}' target='_blank' style='color: #4da6ff; text-decoration: none;'>{title}</a></li>"
        else:
            details_html += "<li style='color: #888;'>No CNBC news found.</li>"
    except Exception as e:
        details_html += f"<li style='color: red;'>Error: {e}</li>"
    details_html += "</ul></div>"

    # Source 3: Bloomberg
    details_html += "<div style='flex: 1;'>"
    details_html += "<h3 style='color: #aaa;'>Bloomberg</h3><ul style='line-height: 1.6; padding-left: 20px;'>"
    bloomberg_rss_url = f"https://news.google.com/rss/search?q={ticker}+stock+site:bloomberg.com&hl=en-US&gl=US&ceid=US:en"
    try:
        response = requests.get(bloomberg_rss_url)
        root = ET.fromstring(response.content)
        articles = root.findall('.//channel/item')
        if articles:
            for article in articles[:4]:
                title = article.find('title').text
                link = article.find('link').text
                details_html += f"<li><a href='{link}' target='_blank' style='color: #4da6ff; text-decoration: none;'>{title}</a></li>"
        else:
            details_html += "<li style='color: #888;'>No Bloomberg news found.</li>"
    except Exception as e:
        details_html += f"<li style='color: red;'>Error: {e}</li>"
    details_html += "</ul></div>"

    details_html += "</div>"

    # --- ADD COVERED CALL ROC CALCULATOR ---
    details_html += f"""
    <div style='background-color: #111; padding: 15px; border-radius: 5px; border: 1px solid #333; margin-bottom: 40px;'>
        <h3 style='color: #ff9900; margin-top: 0;'>Covered Call Return on Capital (Near-Term OTM Options)</h3>
    """
    try:
        tkr_data = yf.Ticker(ticker)
        options_dates = tkr_data.options
        current_price = df['Close'].iloc[-1] if (df is not None and not df.empty) else None

        if options_dates and current_price:
            exp_date = options_dates[0]
            dte = max((datetime.strptime(exp_date, "%Y-%m-%d") - datetime.now()).days, 1)
            calls = tkr_data.option_chain(exp_date).calls

            # Filter OTM and calculate metrics
            otm_calls = calls[calls['strike'] > current_price].copy()
            if not otm_calls.empty:
                otm_calls['Cost Basis'] = current_price - otm_calls['lastPrice']
                otm_calls['Static ROC (%)'] = (otm_calls['lastPrice'] / otm_calls['Cost Basis']) * 100
                otm_calls['Assigned ROC (%)'] = (((otm_calls['strike'] - current_price) + otm_calls['lastPrice']) /
                                                 otm_calls['Cost Basis']) * 100

                # Format for display (Top 5 nearest strikes)
                display_df = otm_calls[['strike', 'lastPrice', 'volume', 'Static ROC (%)', 'Assigned ROC (%)']].head(
                    5).copy()
                display_df['strike'] = display_df['strike'].apply(lambda x: f"${x:.2f}")
                display_df['lastPrice'] = display_df['lastPrice'].apply(lambda x: f"${x:.2f}")
                display_df['Static ROC (%)'] = display_df['Static ROC (%)'].apply(lambda x: f"{x:.2f}%")
                display_df['Assigned ROC (%)'] = display_df['Assigned ROC (%)'].apply(lambda x: f"{x:.2f}%")

                display_df.columns = ['Strike Price', 'Premium', 'Volume', 'Static ROC', 'Assigned ROC']

                # Convert to HTML table
                options_html = display_df.to_html(index=False, border=0)
                options_html = options_html.replace('<table border="0" class="dataframe">',
                                                    '<table style="width: 100%; text-align: center; color: white; border-collapse: collapse;">')
                options_html = options_html.replace('<th>',
                                                    '<th style="border-bottom: 1px solid #444; padding: 8px; color: cyan;">')
                options_html = options_html.replace('<td>', '<td style="border-bottom: 1px solid #222; padding: 8px;">')

                details_html += f"<p style='color: #aaa; font-size: 14px; margin-bottom: 10px;'>Expiration: {exp_date} (DTE: {dte}) | Current Price: ${current_price:.2f}</p>"
                details_html += options_html
            else:
                details_html += "<p style='color: #888;'>No Out-Of-The-Money calls found for the nearest expiration.</p>"
        else:
            details_html += "<p style='color: #888;'>Options data not available for this ticker.</p>"
    except Exception as e:
        details_html += f"<p style='color: red;'>Error calculating options data: {e}</p>"

    details_html += "</div>"

details_html += "</div>"
# ==========================================
# 5. COMBINE EVERYTHING & SAVE
# ==========================================
final_html_document = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Stock Dashboard with News, SMAs, Options & Sorting</title>
    <!-- DataTables CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <style>
        /* Custom styling for DataTables in dark mode */
        .dataTables_wrapper .dataTables_length, 
        .dataTables_wrapper .dataTables_filter, 
        .dataTables_wrapper .dataTables_info, 
        .dataTables_wrapper .dataTables_processing, 
        .dataTables_wrapper .dataTables_paginate {{
            color: white !important;
            margin-bottom: 10px;
        }}
        table.dataTable thead th, table.dataTable thead td {{
            border-bottom: 2px solid cyan !important;
            color: white;
        }}
        table.dataTable.no-footer {{
            border-bottom: 1px solid #444 !important;
        }}
        .dataTables_wrapper .dataTables_paginate .paginate_button {{
            color: white !important;
        }}
        /* Keep table background transparent for our custom styling */
        table.dataTable tbody tr {{ background-color: transparent !important; }}
        /* Ensure search bar text input is visible */
        .dataTables_filter input {{
            background-color: #222;
            color: white;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 4px;
        }}
    </style>
</head>
<body style="background-color: black; margin: 0;">
<!-- Main Title -->
    <h1 style="color: yellow; text-align: center; font-family: Arial, sans-serif; font-size: 36px; margin-top: 30px; margin-bottom: 40px;">
    Michael Financial Analysis
</h1>

    <!-- Top Section: Dow Jones and Nasdaq Indices -->
    {indices_html}

    <!-- Middle Section: Extended Price & Volume Table (All Stocks) -->
    {table_html}

    <!-- Bottom Section: Individual Charts, News Feed & Options -->
    {details_html}

    <!-- Footer Section -->
    <div style="text-align: center; color: #888; font-family: Arial, sans-serif; font-size: 14px; padding: 30px 10px; border-top: 1px solid #333; margin-top: 40px; margin-bottom: 20px;">
        &copy; Michael Financial Analysis
    </div>

    <!-- jQuery & DataTables JS -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script>
        $(document).ready(function() {{
            $('#summaryTable').DataTable({{
                "paging": false,          // Shows all tickers without pagination
                "info": false,            // Hides the "Showing 1 of X" text
                "searching": true,        // Adds a search bar for the table
                "order": [[ 3, "desc" ]]  // Default sort by the "Diff" column (Index 3), descending
            }});
        }});
    </script>
</body>
</html>
"""

html_filename = "michaelResearch.html"

with open(html_filename, "w", encoding="utf-8") as f:
    f.write(final_html_document)

print(
    f"\nDone! Open '{html_filename}' in your web browser. You can now click the column headers on the main summary table to instantly sort the data.")