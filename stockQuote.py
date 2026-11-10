import yfinance as yf
import plotly.express as px
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import os
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import numpy as np


# ==========================================
# 0. READ TICKERS FROM FILE
# ==========================================
if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = "stockfiles/michaelResearch.txt"

print(f"Reading tickers from '{filename}'...")

tickers = []

if os.path.exists(filename):
    with open(filename, "r") as file:
        for line in file:
            clean_line = line.strip()
            # Ignore empty lines and full-line comments
            if clean_line and not clean_line.startswith("#"):
                # Extract just the ticker symbol in case of inline comments or commas
                tkr = clean_line.split()[0].split(',')[0].strip().upper()
                if tkr and tkr not in tickers:
                    tickers.append(tkr)
else:
    print(f"Error: '{filename}' not found. Please create it with one ticker symbol per line.")
    print("Using default tickers for now...")
    tickers = ["AAPL", "MSFT", "TSLA", "GOOGL", "AMZN", "META", "NFLX", "NVDA", "AMD", "GDX", "FSKAX"]

print(f"Loaded {len(tickers)} tickers total. Processing data...\n")

# ==========================================
# 1. FETCH STOCK, ETF & FUND DATA
# ==========================================
summary_table_data = []
stock_history_dict = {}
current_year = datetime.now().year

for ticker in tickers:
    stock_data = yf.Ticker(ticker)

    # 1. Pass actions=False to prevent the ETF/Mutual Fund 'Capital Gains' merge bug in yfinance
    try:
        history = stock_data.history(period="2y", actions=False, auto_adjust=True)
    except Exception as e:
        print(f"Primary history fetch failed for {ticker}: {e}")
        history = pd.DataFrame()

    # 2. Fallback to yf.download if .history() returns empty for an ETF or Mutual Fund
    if history is None or history.empty:
        try:
            history = yf.download(ticker, period="2y", progress=False, auto_adjust=True)
        except Exception as e:
            print(f"Fallback download failed for {ticker}: {e}")
            history = pd.DataFrame()

    # 3. Flatten MultiIndex columns if present in newer yfinance versions and normalize Date
    if history is not None and not history.empty:
        if isinstance(history.columns, pd.MultiIndex):
            history.columns = history.columns.get_level_values(0)

        history = history.reset_index()

        # Normalize the Date column name across different yfinance methods
        if 'Date' not in history.columns:
            if 'index' in history.columns:
                history.rename(columns={'index': 'Date'}, inplace=True)
            elif 'Datetime' in history.columns:
                history.rename(columns={'Datetime': 'Date'}, inplace=True)

        # Strip timezone so Plotly subplots, bars, and annotations align properly
        if 'Date' in history.columns:
            history['Date'] = pd.to_datetime(history['Date']).dt.tz_localize(None)

        # Ensure Close is numeric and drop missing rows
        if 'Close' in history.columns:
            history['Close'] = pd.to_numeric(history['Close'], errors='coerce')
            history = history.dropna(subset=['Close']).reset_index(drop=True)

    pe_ratio = None
    eps = None
    div_yield = None
    beta = None
    fifty_two_week_low = None
    fifty_two_week_high = None
    quote_type = "EQUITY"
    earnings_date_display = "N/A"
    days_to_earnings = None

    try:
        info = stock_data.info or {}
        quote_type = info.get('quoteType', 'EQUITY')

        # P/E Ratio
        pe_ratio = info.get('trailingPE', None)
        pe_display = f"{pe_ratio:.2f}" if pe_ratio is not None else "N/A"

        # Earnings Per Share (EPS)
        eps = info.get('trailingEps', None)
        eps_display = f"${eps:.2f}" if eps is not None else "N/A"

        # Dividend / Fund Yield (Checks standard dividend fields + ETF/Mutual Fund 'yield')
        div_yield = info.get('dividendYield', None)
        if div_yield is None:
            div_yield = info.get('trailingAnnualDividendYield', None)
        if div_yield is None:
            div_yield = info.get('yield', None)

        if div_yield is not None:
            div_pct = div_yield * 100 if div_yield < 1 else div_yield
            div_display = f"{div_pct:.2f}%"
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
        target_display = f"${target_price:.2f}" if target_price is not None else "N/A"

        # Volatility (Checks standard 'beta' and ETF/Mutual Fund 'beta3Year')
        beta = info.get('beta', None)
        if beta is None:
            beta = info.get('beta3Year', None)
        beta_display = f"{beta:.2f}" if beta is not None else "N/A"

        # 52-Week Range
        fifty_two_week_low = info.get('fiftyTwoWeekLow', None)
        low_display = f"${fifty_two_week_low:.2f}" if fifty_two_week_low is not None else "N/A"

        fifty_two_week_high = info.get('fiftyTwoWeekHigh', None)
        high_display = f"${fifty_two_week_high:.2f}" if fifty_two_week_high is not None else "N/A"

        # Fetch Earnings Date safely (Only applicable to individual equities)
        if quote_type == 'EQUITY':
            try:
                cal = stock_data.calendar
                next_date = None

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
                        days_to_earnings = None
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

    if history is not None and len(history) >= 2:
        # Pre-calculate 50-Day and 200-Day SMAs
        history['SMA_50'] = history['Close'].rolling(window=50, min_periods=1).mean()
        history['SMA_200'] = history['Close'].rolling(window=200, min_periods=1).mean()

        # Pre-calculate 14-Day RSI
        delta = history['Close'].diff()
        gain = delta.where(delta > 0, 0.0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / 14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        history['RSI_14'] = 100 - (100 / (1 + rs))
        history['RSI_14'] = history['RSI_14'].fillna(50.0)

        last_idx = history.index[-1]
        prev_idx = history.index[-2]

        latest_close = float(history.loc[last_idx, 'Close'])
        prev_close = float(history.loc[prev_idx, 'Close'])
        sma_50_val = float(history.loc[last_idx, 'SMA_50'])
        sma_200_val = float(history.loc[last_idx, 'SMA_200'])
        rsi_val = float(history.loc[last_idx, 'RSI_14'])

        # Determine 14-Day RSI Status (Overbought >= 70, Oversold <= 30)
        if rsi_val >= 70:
            rsi_display = f"{rsi_val:.1f} (🔥 Overbought)"
            rsi_color = "#ff4d4d"
        elif rsi_val <= 30:
            rsi_display = f"{rsi_val:.1f} (🟢 Oversold)"
            rsi_color = "lime"
        else:
            rsi_display = f"{rsi_val:.1f}"
            rsi_color = "#ffeb3b"

        # Determine 50/200 SMA Trend Signal (Golden Cross vs Death Cross)
        if len(history) >= 50 and sma_200_val > 0:
            sma_spread_pct = ((sma_50_val - sma_200_val) / sma_200_val) * 100
            lookback_idx = history.index[-min(6, len(history))]
            prev_sma_50 = float(history.loc[lookback_idx, 'SMA_50'])
            prev_sma_200 = float(history.loc[lookback_idx, 'SMA_200'])

            if sma_50_val > sma_200_val:
                if prev_sma_50 <= prev_sma_200:
                    sma_signal_display = "🔥 Golden Cross"
                    sma_signal_color = "#00ff88"
                else:
                    sma_signal_display = "🟢 Bullish (50 > 200)"
                    sma_signal_color = "lime"
            else:
                if prev_sma_50 >= prev_sma_200:
                    sma_signal_display = "💀 Death Cross"
                    sma_signal_color = "#ff3333"
                else:
                    sma_signal_display = "🔴 Bearish (50 < 200)"
                    sma_signal_color = "red"
        else:
            sma_spread_pct = 0.0
            sma_signal_display = "N/A"
            sma_signal_color = "#888"

        # Safe Volume extraction for Mutual Funds and ETFs
        if 'Volume' in history.columns and pd.notna(history.loc[last_idx, 'Volume']):
            latest_volume = int(float(history.loc[last_idx, 'Volume']))
        else:
            latest_volume = 0

        price_diff = latest_close - prev_close
        pct_diff = (price_diff / prev_close) * 100 if prev_close != 0 else 0.0

        # Calculate YTD % Return from the first trading day of the current year
        ytd_df = history[history['Date'].dt.year == current_year]
        if not ytd_df.empty:
            ytd_start_price = float(ytd_df.iloc[0]['Close'])
            ytd_pct = ((latest_close - ytd_start_price) / ytd_start_price) * 100 if ytd_start_price != 0 else 0.0
        else:
            ytd_pct = 0.0

        # Fallback to historical 1-year High/Low if info dictionary missed them
        if fifty_two_week_low is None:
            fifty_two_week_low = float(history['Close'].tail(252).min())
            low_display = f"${fifty_two_week_low:.2f}"
        if fifty_two_week_high is None:
            fifty_two_week_high = float(history['Close'].tail(252).max())
            high_display = f"${fifty_two_week_high:.2f}"

        summary_table_data.append({
            'Ticker': ticker,
            'Quote_Type': quote_type,
            'Prev_Close': prev_close,
            'Close': latest_close,
            'Diff': price_diff,
            'Pct_Diff': pct_diff,
            'YTD_Pct': ytd_pct,
            'SMA_50': sma_50_val,
            'SMA_200': sma_200_val,
            'SMA_Spread_Pct': sma_spread_pct,
            'SMA_Signal_Display': sma_signal_display,
            'SMA_Signal_Color': sma_signal_color,
            'RSI': rsi_val,
            'RSI_Display': rsi_display,
            'RSI_Color': rsi_color,
            'Volume': latest_volume,
            'Volume_Display': f"{latest_volume:,}" if latest_volume > 0 else "N/A",
            'PE': pe_ratio if pe_ratio is not None else 0,
            'PE_Display': pe_display,
            'EPS': eps if eps is not None else 0,
            'EPS_Display': eps_display,
            'Div': div_yield if div_yield is not None else 0,
            'Div_Display': div_display,
            'Rec': rec_display,
            'Target': target_display,
            'Beta': beta if beta is not None else 0,
            'Beta_Display': beta_display,
            'Low': fifty_two_week_low if fifty_two_week_low is not None else 0,
            'Low_Display': low_display,
            'High': fifty_two_week_high if fifty_two_week_high is not None else 0,
            'High_Display': high_display,
            'Earnings_Date': earnings_date_display,
            'Days_To_Earnings': days_to_earnings
        })

        stock_history_dict[ticker] = history
        print(f"Successfully processed {ticker} ({quote_type}) - {sma_signal_display} | RSI: {rsi_display}")
    else:
        print(f"Warning: Not enough historical price data found for ticker '{ticker}'. Skipping...")

# ==========================================
# 2. BUILD MARKET INDICES CHARTS (DOW, S&P 500 & NASDAQ)
# ==========================================
print("\nFetching Dow Jones, S&P 500, and Nasdaq data...")
indices = {
    "Dow Jones": "^DJI",
    "S&P 500": "^GSPC",
    "Nasdaq Composite": "^IXIC"
}
index_charts = []

for name, ticker in indices.items():
    idx_data = yf.Ticker(ticker).history(period="1y", actions=False).reset_index()
    if not idx_data.empty:
        if isinstance(idx_data.columns, pd.MultiIndex):
            idx_data.columns = idx_data.columns.get_level_values(0)
        idx_data['Date'] = pd.to_datetime(idx_data['Date']).dt.tz_localize(None)

        fig_idx = px.line(idx_data, x='Date', y='Close',
                          title=f'{name} (1 Year)',
                          labels={'Close': 'Index Value'})

        if name == "S&P 500":
            fig_idx.update_traces(line_color='#00ff88')
        elif name == "Nasdaq Composite":
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
            width=450, height=340,
            plot_bgcolor='black', paper_bgcolor='black',
            font=dict(color='white', size=12),
            title=dict(font=dict(size=17)),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#333333'),
            margin=dict(l=40, r=20, t=50, b=30)
        )
        index_charts.append(fig_idx.to_html(full_html=False, include_plotlyjs='cdn'))

indices_html = f"""
<div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 15px; padding-top: 10px; max-width: 1500px; margin: 0 auto;">
    {''.join(index_charts)}
</div>
"""

# ==========================================
# 3. BUILD THE HTML TABLE FOR LATEST PRICES
# ==========================================
table_html = """
<div id="topSummarySection" style="display: flex; justify-content: center; margin-top: 20px; margin-bottom: 30px; max-width: 1500px; margin-left: auto; margin-right: auto;">
    <table id="summaryTable" style="color: white; border-collapse: collapse; font-family: Arial, sans-serif; width: 100%; text-align: center; border: 1px solid #444;">
        <thead>
            <tr style="background-color: #222; border-bottom: 2px solid cyan;">
                <th style="padding: 10px; font-size: 14px;">Ticker</th>
                <th style="padding: 10px; font-size: 14px;">Prev Close</th>
                <th style="padding: 10px; font-size: 14px;">Latest Close</th>
                <th style="padding: 10px; font-size: 14px;">Diff</th>
                <th style="padding: 10px; font-size: 14px;">% Diff</th>
                <th style="padding: 10px; font-size: 14px;">YTD %</th>
                <th style="padding: 10px; font-size: 14px; color: yellow;">SMA Trend (50/200)</th>
                <th style="padding: 10px; font-size: 14px; color: yellow;">RSI (14)</th>
                <th style="padding: 10px; font-size: 14px;">Volume</th>
                <th style="padding: 10px; font-size: 14px;">P/E</th>
                <th style="padding: 10px; font-size: 14px; color: #ff9900;">EPS</th>
                <th style="padding: 10px; font-size: 14px; color: #ff9900;">Div Yield</th>
                <th style="padding: 10px; font-size: 14px; color: #00ffcc;">Beta</th>
                <th style="padding: 10px; font-size: 14px; color: #00ffcc;">52W Low</th>
                <th style="padding: 10px; font-size: 14px; color: #00ffcc;">52W High</th>
            </tr>
        </thead>
        <tbody>
"""

for data in summary_table_data:
    diff_val = data['Diff']
    pct_val = data['Pct_Diff']
    ytd_val = data['YTD_Pct']

    diff_color = "lime" if diff_val >= 0 else "red"
    diff_sign = "+" if diff_val >= 0 else ""

    ytd_color = "lime" if ytd_val >= 0 else "red"
    ytd_sign = "+" if ytd_val >= 0 else ""

    tkr = data['Ticker']
    sma_tooltip = f"50-SMA: ${data['SMA_50']:.2f} | 200-SMA: ${data['SMA_200']:.2f} ({data['SMA_Spread_Pct']:+.2f}%)"

    table_html += f"""
            <tr style="border-bottom: 1px solid #333; background-color: transparent;">
                <td style="padding: 10px; font-weight: bold;" data-order="{tkr}">
                    <a href="#section-{tkr}" class="ticker-link" title="Jump to {tkr} chart">{tkr}</a>
                </td>
                <td style="padding: 10px;" data-order="{data['Prev_Close']}">${data['Prev_Close']:.2f}</td>
                <td style="padding: 10px;" data-order="{data['Close']}">${data['Close']:.2f}</td>
                <td style="padding: 10px; font-weight: bold; color: {diff_color};" data-order="{diff_val}">{diff_sign}${diff_val:.2f}</td>
                <td style="padding: 10px; font-weight: bold; color: {diff_color};" data-order="{pct_val}">{diff_sign}{pct_val:.2f}%</td>
                <td style="padding: 10px; font-weight: bold; color: {ytd_color};" data-order="{ytd_val}">{ytd_sign}{ytd_val:.2f}%</td>
                <td style="padding: 10px; font-weight: bold; color: {data['SMA_Signal_Color']};" data-order="{data['SMA_Spread_Pct']}" title="{sma_tooltip}">{data['SMA_Signal_Display']}</td>
                <td style="padding: 10px; font-weight: bold; color: {data['RSI_Color']};" data-order="{data['RSI']}">{data['RSI_Display']}</td>
                <td style="padding: 10px;" data-order="{data['Volume']}">{data['Volume_Display']}</td>
                <td style="padding: 10px; font-weight: bold;" data-order="{data['PE']}">{data['PE_Display']}</td>
                <td style="padding: 10px; font-weight: bold; color: #ff9900;" data-order="{data['EPS']}">{data['EPS_Display']}</td>
                <td style="padding: 10px; font-weight: bold; color: #ff9900;" data-order="{data['Div']}">{data['Div_Display']}</td>
                <td style="padding: 10px; font-weight: bold; color: #00ffcc;" data-order="{data['Beta']}">{data['Beta_Display']}</td>
                <td style="padding: 10px; font-weight: bold; color: #00ffcc;" data-order="{data['Low']}">{data['Low_Display']}</td>
                <td style="padding: 10px; font-weight: bold; color: #00ffcc;" data-order="{data['High']}">{data['High_Display']}</td>
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
<div style='color: white; font-family: Arial, sans-serif; max-width: 1500px; margin: 0 auto; padding: 20px;'>
    <h1 style='border-bottom: 1px solid #333; margin-top: 40px;'>Stock, ETF & Fund Analysis & Latest News</h1>
"""

for ticker in tickers:
    ticker_info = next((item for item in summary_table_data if item["Ticker"] == ticker), None)

    if ticker_info:
        badge_html = ""
        dte = ticker_info.get('Days_To_Earnings')
        q_type = ticker_info.get('Quote_Type', 'EQUITY')
        diff_val = ticker_info['Diff']
        pct_val = ticker_info['Pct_Diff']
        ytd_val = ticker_info['YTD_Pct']

        diff_color = "lime" if diff_val >= 0 else "red"
        diff_sign = "+" if diff_val >= 0 else ""
        ytd_color = "lime" if ytd_val >= 0 else "red"
        ytd_sign = "+" if ytd_val >= 0 else ""

        if q_type == 'MUTUALFUND':
            badge_html = " <span style='background-color: #0066cc; color: white; font-size: 13px; padding: 4px 8px; border-radius: 5px; vertical-align: middle; margin-left: 10px; font-weight: bold;'>Mutual Fund</span>"
        elif q_type == 'ETF':
            badge_html = " <span style='background-color: #008060; color: white; font-size: 13px; padding: 4px 8px; border-radius: 5px; vertical-align: middle; margin-left: 10px; font-weight: bold;'>ETF</span>"
        elif dte is not None:
            if dte <= 14:
                badge_html = f" <span style='background-color: red; color: white; font-size: 14px; padding: 4px 8px; border-radius: 5px; vertical-align: middle; margin-left: 10px; font-weight: bold;'>⚠️ Earnings in {dte} Days ({ticker_info['Earnings_Date']})</span>"
            elif dte <= 30:
                badge_html = f" <span style='background-color: darkorange; color: white; font-size: 14px; padding: 4px 8px; border-radius: 5px; vertical-align: middle; margin-left: 10px; font-weight: bold;'>⚠️ Earnings in {dte} Days ({ticker_info['Earnings_Date']})</span>"

        header_extra = (f" <span style='color: white;'>- ${ticker_info['Close']:.2f}</span> "
                        f"<span style='color: {diff_color}; font-size: 18px;'>({diff_sign}${diff_val:.2f} / {diff_sign}{pct_val:.2f}%)</span> "
                        f"<span style='color: #888; font-size: 15px;'>| YTD: <span style='color: {ytd_color};'>{ytd_sign}{ytd_val:.2f}%</span> "
                        f"| Trend: <span style='color: {ticker_info['SMA_Signal_Color']};'>{ticker_info['SMA_Signal_Display']}</span> "
                        f"| RSI: <span style='color: {ticker_info['RSI_Color']};'>{ticker_info['RSI_Display']}</span> "
                        f"| EPS: {ticker_info['EPS_Display']} | Div: {ticker_info['Div_Display']} "
                        f"| Target: {ticker_info['Target']} | Consensus: {ticker_info['Rec']}</span>"
                        f"{badge_html}")
    else:
        header_extra = ""
        q_type = "EQUITY"

    details_html += f"""
    <h2 id='section-{ticker}' style='color: cyan; margin-top: 50px; border-bottom: 1px dashed #444; padding-bottom: 8px; display: flex; justify-content: space-between; align-items: baseline;'>
        <span>{ticker} Overview{header_extra}</span>
        <a href='#topSummarySection' class='back-to-top'>↑ Back to Summary Table</a>
    </h2>
    """

    # --- ADD INDIVIDUAL PLOTLY CHART WITH SMAs, MACD, and RSI ---
    df = stock_history_dict.get(ticker)
    if df is not None and not df.empty:
        df = df.copy()

        # Calculate MACD (12, 26, 9)
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

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
        colors = ['lime' if val >= 0 else 'red' for val in df_plot['MACD_Hist']]
        fig.add_trace(go.Bar(x=df_plot['Date'], y=df_plot['MACD_Hist'], name='MACD Hist', marker_color=colors),
                      row=2, col=1)
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['MACD'], mode='lines', name='MACD',
                                 line=dict(color='cyan', width=1.5)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['MACD_Signal'], mode='lines', name='Signal',
                                 line=dict(color='yellow', width=1.5)), row=2, col=1)

        # Row 3: RSI
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['RSI_14'], mode='lines', name='RSI (14)',
                                 line=dict(color='yellow', width=1.5)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="lime", row=3, col=1)

        # Annotate latest close price
        latest_val = df_plot['Close'].iloc[-1]
        latest_date = df_plot['Date'].iloc[-1]
        fig.add_annotation(
            x=latest_date, y=latest_val, text=f"Close: {latest_val:,.2f}",
            showarrow=True, arrowhead=2, arrowcolor="white", ax=-40, ay=0, font=dict(color="#00ffcc", size=12),
            row=1, col=1
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

    news_sources = [
        ("Google News", f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"),
        ("CNBC", f"https://news.google.com/rss/search?q={ticker}+stock+site:cnbc.com&hl=en-US&gl=US&ceid=US:en"),
        ("Bloomberg", f"https://news.google.com/rss/search?q={ticker}+stock+site:bloomberg.com&hl=en-US&gl=US&ceid=US:en")
    ]

    for source_name, rss_url in news_sources:
        details_html += "<div style='flex: 1;'>"
        details_html += f"<h3 style='color: #aaa;'>{source_name}</h3><ul style='line-height: 1.6; padding-left: 20px;'>"
        try:
            response = requests.get(rss_url, timeout=10)
            root = ET.fromstring(response.content)
            articles = root.findall('.//channel/item')
            if articles:
                for article in articles[:4]:
                    title = article.find('title').text
                    link = article.find('link').text
                    details_html += f"<li><a href='{link}' target='_blank' style='color: #4da6ff; text-decoration: none;'>{title}</a></li>"
            else:
                details_html += f"<li style='color: #888;'>No {source_name} news found.</li>"
        except Exception as e:
            details_html += f"<li style='color: red;'>Error: {e}</li>"
        details_html += "</ul></div>"

    details_html += "</div>"

    # --- ADD COVERED CALL ROC CALCULATOR ---
    details_html += """
    <div style='background-color: #111; padding: 15px; border-radius: 5px; border: 1px solid #333; margin-bottom: 40px;'>
        <h3 style='color: #ff9900; margin-top: 0;'>Covered Call Return on Capital (Near-Term OTM Options)</h3>
    """
    if q_type == 'MUTUALFUND':
        details_html += "<p style='color: #888;'>Mutual funds do not trade options chains.</p>"
    else:
        try:
            tkr_data = yf.Ticker(ticker)
            options_dates = getattr(tkr_data, 'options', ())
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
                    display_df = otm_calls[['strike', 'lastPrice', 'volume', 'Static ROC (%)', 'Assigned ROC (%)']].head(5).copy()
                    display_df['strike'] = display_df['strike'].apply(lambda x: f"${x:.2f}")
                    display_df['lastPrice'] = display_df['lastPrice'].apply(lambda x: f"${x:.2f}")
                    display_df['volume'] = display_df['volume'].fillna(0).astype(int)
                    display_df['Static ROC (%)'] = display_df['Static ROC (%)'].apply(lambda x: f"{x:.2f}%")
                    display_df['Assigned ROC (%)'] = display_df['Assigned ROC (%)'].apply(lambda x: f"{x:.2f}%")

                    display_df.columns = ['Strike Price', 'Premium', 'Volume', 'Static ROC', 'Assigned ROC']

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
last_updated_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")

final_html_document = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Stock Dashboard with News, SMAs, Options & Sorting</title>
    <!-- DataTables CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <style>
        html {{
            scroll-behavior: smooth;
        }}
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
        table.dataTable tbody tr {{ background-color: transparent !important; }}
        .dataTables_filter input {{
            background-color: #222;
            color: white;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 4px;
        }}
        /* Clickable Ticker Link Styling */
        a.ticker-link {{
            color: cyan;
            text-decoration: none;
            transition: color 0.2s ease;
        }}
        a.ticker-link:hover {{
            color: yellow;
            text-decoration: underline;
        }}
        /* Back to Summary Table Link Styling */
        a.back-to-top {{
            color: #4da6ff;
            font-size: 14px;
            font-weight: normal;
            text-decoration: none;
            padding: 4px 10px;
            border: 1px solid #333;
            border-radius: 4px;
            background-color: #111;
            white-space: nowrap;
        }}
        a.back-to-top:hover {{
            background-color: #222;
            color: cyan;
            border-color: cyan;
        }}
    </style>
</head>
<body style="background-color: black; margin: 0;">
    <h1 style="color: yellow; text-align: center; font-family: Arial, sans-serif; font-size: 36px; margin-top: 30px; margin-bottom: 8px;">
        Michael Financial Analysis
    </h1>
    <p style="color: #aaa; text-align: center; font-family: Arial, sans-serif; font-size: 15px; margin-top: 0; margin-bottom: 30px;">
        Last Updated: <span style="color: cyan; font-weight: bold;">{last_updated_str}</span>
    </p>

    <!-- Top Section: Dow Jones, S&P 500, and Nasdaq Indices -->
    {indices_html}

    <!-- Middle Section: Extended Price & Volume Table (All Stocks, ETFs & Funds) -->
    {table_html}

    <!-- Bottom Section: Individual Charts, News Feed & Options -->
    {details_html}

    <!-- Footer Section -->
    <div style="text-align: center; color: #888; font-family: Arial, sans-serif; font-size: 14px; padding: 30px 10px; border-top: 1px solid #333; margin-top: 40px; margin-bottom: 20px;">
        &copy; Michael Financial Analysis | Generated on {last_updated_str}
    </div>

    <!-- jQuery & DataTables JS -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script>
        $(document).ready(function() {{
            $('#summaryTable').DataTable({{
                "paging": false,
                "info": false,
                "searching": true,
                "order": [[ 4, "desc" ]] // Default sort by "% Diff" column (Index 4), descending
            }});
        }});
    </script>
</body>
</html>
"""

output_dir = "stockHTML"
os.makedirs(output_dir, exist_ok=True)
base_name = os.path.splitext(os.path.basename(filename))[0]
html_filename = os.path.join(output_dir, f"{base_name}.html")

with open(html_filename, "w", encoding="utf-8") as f:
    f.write(final_html_document)

print(f"\nDone! Open '{html_filename}' in your web browser. The 14-day RSI column is now live.")