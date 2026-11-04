import webbrowser
from datetime import datetime
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import feedparser
import requests
import yfinance as yf

# ANSI Color Codes for Terminal Display
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Note: These 4 highlights are currently hardcoded for Apple.
# If you run this for other stocks, you may want to update or remove this list.
FOUR_MAIN_POINTS = [
    {
        "title": "1. Q4 FY26 Earnings Next Week (Nov 2)",
        "tag": "Earnings & Analysts",
        "detail": "Marks the first earnings call led by CEO John Ternus. Bernstein SocGen ($370 PT), Evercore ISI ($380 PT), and Goldman Sachs reiterated Buy/Outperform ratings ahead of Monday's report."
    },
    {
        "title": "2. Decoupling from the 'AI Spend' Sell-Off",
        "tag": "Market Correlation",
        "detail": "Apple's 3-month correlation with the Nasdaq 100 turned negative (-0.12) for the first time on record. Restrained AI capex has made AAPL a safe haven, trading near $350."
    },
    {
        "title": "3. M6 Mac & A20 Pro Lineup Refresh",
        "tag": "Product Catalyst",
        "detail": "Apple unveiled updated 14-inch MacBook Pro, 24-inch iMac, and iPad models powered by the M6 and A20 Pro chips, driving a favorable premium hardware mix."
    },
    {
        "title": "4. South Korea App Store Fine",
        "tag": "Regulatory Watch",
        "detail": "South Korea's KMCC fined Apple 20.81B won (~$15.6M) over in-app payment restrictions. Minimal impact on $136.7B FCF, but watched for external payment link precedent."
    }
]


def get_live_metrics(ticker):
    """Fetches live market data and company name using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Dynamically grab the company name (fallback to ticker if missing)
        company_name = info.get("shortName", ticker)

        # Handle different yfinance versions/fields
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0.0

        change_pct = 0.0
        if prev_close and price:
            change_pct = ((price - prev_close) / prev_close) * 100

        pe = info.get("trailingPE", "N/A")
        if isinstance(pe, float):
            pe = round(pe, 2)

        vol = info.get("volume", "N/A")
        vol_str = f"{vol:,}" if isinstance(vol, int) else str(vol)

        return {
            "name": company_name,
            "price": float(price),
            "change_pct": float(change_pct),
            "pe": pe,
            "volume": vol_str
        }
    except Exception as e:
        print(f"Note: yfinance fetch failed ({e}).")
        return {"name": ticker, "price": 0.0, "change_pct": 0.0, "pe": "N/A", "volume": "N/A"}


def fetch_cnbc_quote_page_news(ticker, limit=5):
    url = f"https://www.cnbc.com/quotes/{ticker}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        )
    }
    articles = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for item in soup.select("li.LatestNews-item")[:limit]:
            headline_tag = item.select_one("a.LatestNews-headline")
            time_tag = item.select_one("time.LatestNews-timestamp")

            if headline_tag:
                articles.append({
                    "title": headline_tag.get_text(strip=True),
                    "link": headline_tag.get("href", ""),
                    "published": time_tag.get_text(strip=True) if time_tag else "Recent",
                    "source": "CNBC Quote Page",
                })
    except Exception as e:
        pass
    return articles


def fetch_cnbc_rss_news(query, limit=5):
    encoded_query = quote_plus(f"{query} site:cnbc.com")
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    articles = []

    for entry in feed.entries[:limit]:
        clean_title = entry.title.rsplit(" - CNBC", 1)[0]
        articles.append({
            "title": clean_title,
            "link": entry.link,
            "published": entry.get("published", "N/A"),
            "source": "CNBC RSS",
        })
    return articles


def get_top_5_cnbc_news(ticker, max_items=5):
    direct_news = fetch_cnbc_quote_page_news(ticker, limit=5)
    rss_news = fetch_cnbc_rss_news(f"{ticker} OR {ticker} stock", limit=8)

    combined = []
    seen_titles = set()

    for article in direct_news + rss_news:
        title_key = article["title"].lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            combined.append(article)
        if len(combined) >= max_items:
            break
    return combined[:max_items]


def display_and_save_reports(ticker):
    articles = get_top_5_cnbc_news(ticker, max_items=5)
    metrics = get_live_metrics(ticker)

    # Formatted for reading in the report headers (e.g., "2026-10-29 10:16:00")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Formatted to be safe for saving in file names (e.g., "20261029_101600")
    file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    price_str = f"${metrics['price']:.2f}"
    change_str = f"{metrics['change_pct']:+.2f}%"

    # ANSI color logic for terminal
    change_color = GREEN if metrics['change_pct'] >= 0 else RED
    html_change_color = "#16a34a" if metrics['change_pct'] >= 0 else "#dc2626"

    # =========================================================================
    # 1. TERMINAL DISPLAY
    # =========================================================================
    print(f"\n{BOLD}{CYAN}{'=' * 95}{RESET}")
    print(f"{BOLD}{GREEN}CNBC EXECUTIVE BRIEFING: {ticker} (Generated: {timestamp}){RESET}")
    print(f"{BOLD}{CYAN}{'=' * 95}{RESET}")

    # Metrics Bar
    print(
        f"{BOLD}LIVE QUOTE:{RESET} Price: {CYAN}{price_str}{RESET} | Change: {change_color}{change_str}{RESET} | P/E: {YELLOW}{metrics['pe']}{RESET} | Vol: {metrics['volume']}")
    print(f"{CYAN}{'-' * 95}{RESET}")

    print(f"\n{BOLD}{MAGENTA}>>> 4 KEY MARKET HIGHLIGHTS ({ticker}) <<<{RESET}")
    print(f"{'-' * 95}")
    for pt in FOUR_MAIN_POINTS:
        print(f"{BOLD}{YELLOW}{pt['title']}{RESET} [{CYAN}{pt['tag']}{RESET}]")
        print(f"   {pt['detail']}\n")

    print(f"{BOLD}{MAGENTA}>>> TOP 5 CNBC HEADLINES <<<{RESET}")
    print(f"{'-' * 95}")
    print(f"{BOLD}{'#':<4} {'Published':<26} {'Headline'}{RESET}")
    print(f"{'-' * 95}")

    # =========================================================================
    # 2. PLAIN-TEXT FILE OUTPUT
    # =========================================================================
    # CHANGED: File name now includes the timestamp (e.g., AAPL_20261029_101600_news.txt)
    txt_filename = f"{ticker.upper()}_{file_timestamp}_news.txt"

    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write(f"CNBC EXECUTIVE BRIEFING: {ticker}\n")
        f.write(f"Generated: {timestamp}\n")
        f.write("=" * 95 + "\n")
        f.write(
            f"LIVE QUOTE: Price: {price_str} | Change: {change_str} | P/E: {metrics['pe']} | Vol: {metrics['volume']}\n")
        f.write("=" * 95 + "\n\n")

        f.write("4 KEY MARKET HIGHLIGHTS:\n")
        f.write("-" * 95 + "\n")
        for pt in FOUR_MAIN_POINTS:
            f.write(f"{pt['title']} ({pt['tag']})\n")
            f.write(f"   {pt['detail']}\n\n")

        f.write("TOP 5 CNBC HEADLINES:\n")
        f.write("-" * 95 + "\n")
        for idx, item in enumerate(articles, start=1):
            pub_short = item["published"][:24]
            print(f"{YELLOW}{idx:<4}{RESET} {pub_short:<26} {BOLD}{item['title']}{RESET}")
            print(f"     {CYAN}Link:{RESET} {item['link']}\n")

            f.write(f"{idx}. [{item['published']}] {item['title']}\n")
            f.write(f"   Link: {item['link']}\n\n")

    # =========================================================================
    # 3. STYLED HTML REPORT DISPLAY
    # =========================================================================
    # CHANGED: File name now includes the timestamp (e.g., AAPL_20261029_101600_news.html)
    html_filename = f"{ticker.upper()}_{file_timestamp}_news.html"

    highlights_html = ""
    for pt in FOUR_MAIN_POINTS:
        highlights_html += f"""
        <div class="highlight-card">
            <span class="highlight-tag">{pt['tag']}</span>
            <h4>{pt['title']}</h4>
            <p>{pt['detail']}</p>
        </div>
        """

    cards_html = ""
    for idx, item in enumerate(articles, start=1):
        cards_html += f"""
        <div class="news-card">
            <div class="meta">
                <span class="badge">#{idx} • {item['source']}</span>
                <span class="time">{item['published']}</span>
            </div>
            <h3 class="headline">
                <a href="{item['link']}" target="_blank" rel="noopener noreferrer">
                    {item['title']}
                </a>
            </h3>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CNBC Executive Briefing - {ticker}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #f4f6f9;
            color: #1e293b;
            max-width: 920px;
            margin: 36px auto;
            padding: 0 20px;
        }}
        header {{
            background: linear-gradient(135deg, #002f6c 0%, #005596 100%);
            color: #ffffff;
            padding: 24px 28px;
            border-radius: 10px;
            margin-bottom: 24px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        header h1 {{ margin: 0 0 6px 0; font-size: 26px; }}
        header p {{ margin: 0; color: #cbd5e1; font-size: 14px; }}

        .metrics-bar {{
            display: flex;
            justify-content: center;
            gap: 24px;
            background: #ffffff;
            padding: 16px;
            border-radius: 8px;
            margin: -10px 0 24px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border: 1px solid #e2e8f0;
        }}
        .metric {{
            text-align: center;
            padding: 0 16px;
        }}
        .metric:not(:last-child) {{
            border-right: 1px solid #e2e8f0;
        }}
        .metric span {{
            display: block;
            font-size: 12px;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .metric strong {{
            font-size: 20px;
            color: #0f172a;
        }}

        .section-title {{
            font-size: 18px;
            font-weight: 700;
            color: #002f6c;
            margin: 24px 0 12px 0;
            border-bottom: 2px solid #cbd5e1;
            padding-bottom: 6px;
        }}
        .highlights-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .highlight-card {{
            background: #ffffff;
            border-top: 4px solid #f59e0b;
            border-radius: 8px;
            padding: 16px 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        .highlight-tag {{
            display: inline-block;
            background: #fef3c7;
            color: #b45309;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 3px 8px;
            border-radius: 4px;
            margin-bottom: 8px;
        }}
        .highlight-card h4 {{ margin: 0 0 8px 0; font-size: 16px; color: #0f172a; }}
        .highlight-card p {{ margin: 0; font-size: 14px; line-height: 1.5; color: #475569; }}
        .news-card {{
            background: #ffffff;
            border-left: 5px solid #005596;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            transition: transform 0.15s ease;
        }}
        .news-card:hover {{ transform: translateY(-2px); }}
        .meta {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #64748b;
            margin-bottom: 6px;
        }}
        .badge {{
            background: #e0f2fe;
            color: #0369a1;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .headline {{ margin: 0; font-size: 16px; line-height: 1.4; }}
        .headline a {{ color: #0f172a; text-decoration: none; }}
        .headline a:hover {{ color: #005596; text-decoration: underline; }}
        footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #cbd5e1;
            font-size: 13px;
            color: #64748b;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <header>
        <h1>CNBC Market Briefing: {ticker} ({metrics['name']})</h1>
        <p>Generated on {timestamp}</p>
    </header>

    <div class="metrics-bar">
        <div class="metric">
            <span>Live Price</span>
            <strong>{price_str}</strong>
        </div>
        <div class="metric">
            <span>Day Change</span>
            <strong style="color: {html_change_color};">{change_str}</strong>
        </div>
        <div class="metric">
            <span>Trailing P/E</span>
            <strong>{metrics['pe']}</strong>
        </div>
        <div class="metric">
            <span>Volume</span>
            <strong>{metrics['volume']}</strong>
        </div>
    </div>

    <div class="section-title">4 Key Market Highlights</div>
    <div class="highlights-grid">
        {highlights_html}
    </div>

    <div class="section-title">Top 5 CNBC Headlines</div>
    {cards_html}

    <footer>
        Michael Lau Financial Analysis
    </footer>
</body>
</html>
"""

    with open(html_filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"{GREEN}Saved plain-text report to: {txt_filename}{RESET}")
    print(f"{GREEN}Saved HTML report to:       {html_filename} (Opening in browser...){RESET}\n")

    webbrowser.open(html_filename)


if __name__ == "__main__":
    # Ask the user for a ticker symbol
    user_input = input("Enter a stock ticker (e.g., AAPL, NVDA, TSLA): ").strip().upper()

    if user_input:
        print(f"\nFetching data for {user_input}...")
        display_and_save_reports(user_input)
    else:
        print("No ticker entered. Exiting script.")