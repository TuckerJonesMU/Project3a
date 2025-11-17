from datetime import datetime
from pathlib import Path
import os
import requests
import webbrowser
import pygal
from lxml import etree , html
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Custom exception classes for better error handling
class StockSymbolNotFoundError(Exception):
    """Raised when a stock symbol is not found or invalid."""
    pass


class APIRateLimitError(Exception):
    """Raised when API rate limit is exceeded."""
    pass


class NoDataAvailableError(Exception):
    """Raised when no data is available for the requested parameters."""
    pass


# Returns (series_key, time_series_dict) if a key exists.
def extract_time_series_from_response(data: dict):

    # Try to find the expected time series data
    for key in data:
        if "Time Series" in key:
            return key, data[key]

    # API error checking with more specific messages
    if "Error Message" in data:
        error_msg = data['Error Message']
        # Check for invalid symbol error
        if "Invalid API call" in error_msg or "Invalid stock symbol" in error_msg:
            raise StockSymbolNotFoundError(
                f"Stock symbol not found. Please check the symbol and try again.\n"
                f"Original error: {error_msg}"
            )
        raise RuntimeError(f"API error: {error_msg}")
    
    if "Note" in data:
        note_msg = data['Note']
        # Check for rate limit
        if "API call frequency" in note_msg or "rate limit" in note_msg.lower():
            raise APIRateLimitError(
                f"API rate limit exceeded. Please wait a moment and try again.\n"
                f"Note: Free tier allows 25 requests per day.\n"
                f"Original message: {note_msg}"
            )
        raise RuntimeError(f"API note: {note_msg}")
    
    if "Information" in data:
        raise RuntimeError(f"API info: {data['Information']}")

    raise RuntimeError(f"Unexpected response format. Received keys: {list(data.keys())}") 


# Returns Alpha Vantage function based on period.
def alpha_function_for_period(period: str, intraday_interval: str = "60min") -> tuple[str, dict]:
    
    period = period.lower()
    
    if period == "intraday":
        return "TIME_SERIES_INTRADAY", {"interval": intraday_interval, "adjusted": "true"}
    if period == "daily":
        return "TIME_SERIES_DAILY", {}
    if period == "weekly":
        return "TIME_SERIES_WEEKLY", {}
    if period == "monthly":
        return "TIME_SERIES_MONTHLY", {}
    # Default
    return "TIME_SERIES_DAILY", {}


# Fetches stock data from Alpha Vantage and returns a list of rows.
# (Open, High, Low, Close in rows)
def fetch_stock_rows_from_alpha_vantage(
    symbol: str,
    period: str = "daily",
    *,
    api_key: str | None = None,
    outputsize: str = "full",
    intraday_interval: str = "60min",
) -> list[dict]:

    # Validate stock symbol
    if not symbol or not symbol.strip():
        raise ValueError("Stock symbol cannot be empty")
    
    symbol = symbol.strip().upper()

    # Gets API key from environment
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError(
            "ALPHA_VANTAGE_API_KEY environment variable is not set.\n"
            "Please set your API key: export ALPHA_VANTAGE_API_KEY='your_key_here'"
        )

    # Choose function and parameters
    function, extra = alpha_function_for_period(period, intraday_interval)
    url = "https://www.alphavantage.co/query"
    params = {
        "function": function,
        "symbol": symbol,
        "outputsize": outputsize,
        "apikey": api_key,
        **extra,
    }

    # Sends API request with error handling
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Request timed out while connecting to Alpha Vantage API.\n"
            "Please check your internet connection and try again."
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Failed to connect to Alpha Vantage API.\n"
            "Please check your internet connection and try again."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"HTTP error occurred: {e}\n"
            "The API server may be experiencing issues. Please try again later."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error connecting to API: {e}")

    # Parse JSON response
    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(
            f"Failed to parse API response as JSON.\n"
            f"The API may have returned an invalid response. Error: {e}"
        )

    # Extracts time series section
    _, time_series = extract_time_series_from_response(data)

    # Check if we got any data
    if not time_series or len(time_series) == 0:
        raise NoDataAvailableError(
            f"No data available for symbol '{symbol}' with {period} time series.\n"
            "The stock may not have data for the selected time period."
        )

    # Formats each record into a dictionary
    rows: list[dict] = []
    try:
        for date_str, values in time_series.items():
            rows.append({
                "date": date_str,
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
            })
    except (KeyError, ValueError) as e:
        raise RuntimeError(
            f"Unexpected data format in API response.\n"
            f"Error parsing stock data: {e}"
        )
    
    return rows

# Converts input into a datetime object
def parse_date(date_text):
    try:
        return datetime.strptime(date_text, "%Y-%m-%d")
    
    except ValueError:
        return datetime.strptime(date_text, "%Y-%m-%d %H:%M:%S")


# Loops through every row, only keeps rows inside the range, sorts the result by date
def filter_by_date(rows, start_date, end_date):
    # Validate date strings
    try:
        start = parse_date(start_date)
        end = parse_date(end_date)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {e}")
    
    # Validate date range
    if start > end:
        raise ValueError(
            f"Start date ({start_date}) cannot be after end date ({end_date})"
        )

    filtered_rows = []

    for row in rows:
        date_obj = parse_date(row["date"])
        if start <= date_obj <= end:
            filtered_rows.append(row)

    # Check if we got any data in the date range
    if not filtered_rows:
        raise NoDataAvailableError(
            f"No data available between {start_date} and {end_date}.\n"
            f"The stock may not have been trading during this period, or\n"
            f"the date range may be outside the available data range.\n"
            f"Try selecting a more recent date range."
        )

    filtered_rows.sort(key=lambda r: r["date"])
    return filtered_rows


"""
Groups stock data into grouped rows for intraday, daily, weekly, or monthly time periods

Arguments:
    data_rows: list of dictionaries with keys 'date', 'open', 'high', 'low', 'close'
    period: "intraday", "daily", "weekly", or "monthly"

Returns:
    list of grouped dictionaries (date, open, high, low, close)
"""
def group_by_period(data_rows, period):
    
    # If intraday or daily, sort and return the data without grouping
    if period in ("intraday", "daily"):
        return sorted(data_rows, key=lambda row: row["date"])

    grouped_data = {}

    # Loops through each record, creates labels for groups
    for row in data_rows:
        date_obj = parse_date(row["date"])

        if period == "weekly":
            year, week_num, _ = date_obj.isocalendar()
            group_label = f"{year}-W{week_num:02d}"  
        elif period == "monthly":
            group_label = f"{date_obj.year}-{date_obj.month:02d}"
        else:
            group_label = row["date"]

        if group_label not in grouped_data:
            grouped_data[group_label] = []
            
        grouped_data[group_label].append(row)

    grouped_rows = []
    
    # Combines data into one record for each date
    for label, rows_in_group in grouped_data.items():
        rows_in_group.sort(key=lambda x: x["date"])

        open_price = rows_in_group[0]["open"]
        close_price = rows_in_group[-1]["close"]
        high_price = max(r["high"] for r in rows_in_group)
        low_price = min(r["low"] for r in rows_in_group)

        grouped_rows.append({
            "date": label,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price
        })

    # Sort all summarized rows by their date label
    grouped_rows.sort(key=lambda r: r["date"])
    return grouped_rows


# Builds a webpage to display a chart.
def _build_html(title_text, svg_filename, inline_svg=False):
    from lxml import etree, html
    from pathlib import Path

    # Root element
    doc = etree.Element("html", lang="en")

    # Head section
    head = etree.SubElement(doc, "head")
    etree.SubElement(head, "meta", charset="utf-8")
    etree.SubElement(head, "title").text = title_text
    etree.SubElement(head, "style").text = (
        "body { font-family: sans-serif; margin: 24px; }"
        "h2 { margin-bottom: 16px; }"
        ".chart { max-width: 90%; }"
    )

    # Body section
    body = etree.SubElement(doc, "body")
    etree.SubElement(body, "h2").text = title_text

    if inline_svg:
        svg_root = etree.parse(str(Path(svg_filename))).getroot()
        container = etree.SubElement(body, "div", **{"class": "chart"})
        container.append(svg_root)
    else:
        etree.SubElement(
            body,
            "object",
            data=svg_filename,
            type="image/svg+xml",
            **{"class": "chart"}
        )

    return etree.tostring(
        doc,
        pretty_print=True,
        method="html",
        doctype="<!doctype html>"
    )


def render_chart(grouped, title, chart_type="line", inline_svg=False):
    import webbrowser
    import tempfile

    # Determine chart class
    chart_map = {
        "line": pygal.Line,
        "bar": pygal.Bar,
        "stacked_bar": pygal.StackedBar,
        "xy": pygal.XY
    }
    ChartClass = chart_map.get(chart_type.lower(), pygal.Line)
    
    if isinstance(grouped, list):
        x_labels = [row["date"] for row in grouped]
        series = [
            {"label": "Open",  "values": [row["open"]  for row in grouped]},
            {"label": "High",  "values": [row["high"]  for row in grouped]},
            {"label": "Low",   "values": [row["low"]   for row in grouped]},
            {"label": "Close", "values": [row["close"] for row in grouped]},
        ]
        grouped = {"x_labels": x_labels, "series": series}

    # Create and configure chart
    chart = ChartClass(show_legend=True, x_label_rotation=45)
    chart.title = title
    chart.x_labels = grouped.get("x_labels", [])

    # Add all series to chart
    for s in grouped.get("series", []):
        chart.add(s.get("label", "Series"), s.get("values", []))

    # Renders directly to memory and open in browser
    svg_data = chart.render(is_unicode=True)
    html_content = f"""
    <html>
        <head><title>{title}</title></head>
        <body>{svg_data}</body>
    </html>
    """
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as tmp:
        tmp.write(html_content)
        tmp_path = tmp.name

    webbrowser.open(f"file://{tmp_path}")

    #Return final html path
    return tmp_path

# Fetches, filters, groups, and renders a chart from Alpha Vantage data.
def generate_chart_from_api(
    *,
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
    chart_type: str = "line",
    api_key: str | None = None,
    intraday_interval: str = "60min",
) -> str:

    # Gets data from the API
    all_rows = fetch_stock_rows_from_alpha_vantage(
        symbol, period, api_key=api_key, intraday_interval=intraday_interval
    )
    
    # Keeps only rows within selected date range
    filtered = filter_by_date(all_rows, start_date, end_date)
    
    # Group data by chosen time period
    grouped = group_by_period(filtered, period)
    
     # Create chart title
    title = f"{symbol.upper()} Stock Prices ({period.capitalize()})"
    
    # Render chart and open in browser
    return render_chart(grouped, title, chart_type=chart_type, inline_svg=False)


# Generates chart for web display (returns SVG string instead of opening browser)
def generate_chart_for_web(
    *,
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
    chart_type: str = "line",
    api_key: str | None = None,
    intraday_interval: str = "60min",
) -> str:
    """
    Generates a stock chart for web display.
    Returns SVG string that can be embedded directly in HTML.
    """
    # Gets data from the API
    all_rows = fetch_stock_rows_from_alpha_vantage(
        symbol, period, api_key=api_key, intraday_interval=intraday_interval
    )
    
    # Keeps only rows within selected date range
    filtered = filter_by_date(all_rows, start_date, end_date)
    
    # Group data by chosen time period
    grouped = group_by_period(filtered, period)
    
    # Create chart title
    title = f"{symbol.upper()} Stock Prices ({period.capitalize()})"
    
    # Determine chart class
    chart_map = {
        "line": pygal.Line,
        "bar": pygal.Bar,
    }
    ChartClass = chart_map.get(chart_type.lower(), pygal.Line)
    
    # Prepare data
    x_labels = [row["date"] for row in grouped]
    
    # Create and configure chart
    chart = ChartClass(
        show_legend=True,
        x_label_rotation=45,
        width=1200,
        height=600,
        explicit_size=True,
        style=pygal.style.DefaultStyle(
            colors=('#667eea', '#764ba2', '#f093fb', '#4facfe')
        )
    )
    chart.title = title
    chart.x_labels = x_labels
    
    # Add series to chart
    chart.add('Open', [row["open"] for row in grouped])
    chart.add('High', [row["high"] for row in grouped])
    chart.add('Low', [row["low"] for row in grouped])
    chart.add('Close', [row["close"] for row in grouped])
    
    # Render as SVG string
    return chart.render(is_unicode=True)