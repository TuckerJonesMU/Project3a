"""
flask web application for stock data visualization
converts the command-line stock visualizer to a web application
"""

from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import os
import csv
import io
import requests
from dotenv import load_dotenv
from charts import (
    generate_chart_for_web,
    StockSymbolNotFoundError,
    APIRateLimitError,
    NoDataAvailableError
)

# load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')


def load_stock_symbols_from_api():
    """
    load stock symbols from alpha vantage api.
    returns a list of tuples (symbol, name).
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    
    if not api_key:
        print("Warning: ALPHA_VANTAGE_API_KEY not set, using fallback stock list")
        return get_fallback_stock_list()
    
    try:
        # use alpha vantage listing_status endpoint to get all active stocks
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "LISTING_STATUS",
            "apikey": api_key,
        }
        
        print("Fetching stock symbols from Alpha Vantage API...")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        # parse csv response
        stock_symbols = []
        csv_data = csv.DictReader(io.StringIO(response.text))
        
        for row in csv_data:
            symbol = row.get('symbol', '').strip()
            name = row.get('name', '').strip()
            status = row.get('status', '').strip()
            
            # only include active stocks
            if symbol and name and status == 'Active':
                stock_symbols.append((symbol, name))
        
        # sort by symbol and limit to reasonable number (e.g., first 500)
        stock_symbols.sort(key=lambda x: x[0])
        
        # filter to only include common exchanges to reduce size
        # keep only stocks from major exchanges (no otc, etc.)
        filtered_symbols = [
            (sym, name) for sym, name in stock_symbols
            if len(sym) <= 5 and sym.isalpha()  # basic filter for standard symbols
        ]
        
        print(f"Loaded {len(filtered_symbols)} stock symbols from Alpha Vantage API")
        
        # return limited list (first 1000 to keep dropdown manageable)
        return filtered_symbols[:1000] if filtered_symbols else get_fallback_stock_list()
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching stock symbols from API: {e}")
        print("Using fallback stock list")
        return get_fallback_stock_list()
    except Exception as e:
        print(f"Unexpected error loading stock symbols: {e}")
        return get_fallback_stock_list()


def get_fallback_stock_list():
    """
    returns a fallback list of popular stocks if api fails.
    """
    return [
        ('AAPL', 'Apple Inc.'),
        ('MSFT', 'Microsoft Corporation'),
        ('GOOGL', 'Alphabet Inc. Class A'),
        ('GOOG', 'Alphabet Inc. Class C'),
        ('AMZN', 'Amazon.com Inc.'),
        ('TSLA', 'Tesla Inc.'),
        ('META', 'Meta Platforms Inc.'),
        ('NVDA', 'NVIDIA Corporation'),
        ('JPM', 'JPMorgan Chase & Co.'),
        ('V', 'Visa Inc.'),
        ('WMT', 'Walmart Inc.'),
        ('JNJ', 'Johnson & Johnson'),
        ('PG', 'Procter & Gamble Co.'),
        ('UNH', 'UnitedHealth Group Inc.'),
        ('MA', 'Mastercard Inc.'),
        ('HD', 'Home Depot Inc.'),
        ('DIS', 'The Walt Disney Company'),
        ('BAC', 'Bank of America Corp.'),
        ('XOM', 'Exxon Mobil Corporation'),
        ('PFE', 'Pfizer Inc.'),
        ('ABBV', 'AbbVie Inc.'),
        ('KO', 'The Coca-Cola Company'),
        ('COST', 'Costco Wholesale Corporation'),
        ('AVGO', 'Broadcom Inc.'),
        ('PEP', 'PepsiCo Inc.'),
        ('TMO', 'Thermo Fisher Scientific'),
        ('MRK', 'Merck & Co. Inc.'),
        ('CSCO', 'Cisco Systems Inc.'),
        ('ABT', 'Abbott Laboratories'),
        ('ACN', 'Accenture plc'),
        ('LLY', 'Eli Lilly and Company'),
        ('DHR', 'Danaher Corporation'),
        ('NKE', 'NIKE Inc.'),
        ('VZ', 'Verizon Communications'),
        ('ADBE', 'Adobe Inc.'),
        ('NEE', 'NextEra Energy Inc.'),
        ('CMCSA', 'Comcast Corporation'),
        ('TXN', 'Texas Instruments'),
        ('INTC', 'Intel Corporation'),
        ('CRM', 'Salesforce Inc.'),
        ('UNP', 'Union Pacific Corporation'),
        ('PM', 'Philip Morris International'),
        ('BMY', 'Bristol-Myers Squibb'),
        ('RTX', 'Raytheon Technologies'),
        ('T', 'AT&T Inc.'),
        ('HON', 'Honeywell International'),
        ('QCOM', 'QUALCOMM Incorporated'),
        ('LOW', "Lowe's Companies Inc."),
        ('UPS', 'United Parcel Service'),
        ('AMGN', 'Amgen Inc.'),
        ('ORCL', 'Oracle Corporation'),
    ]


# load stock symbols when app starts
print("Initializing stock symbols...")
STOCK_SYMBOLS = load_stock_symbols_from_api()


@app.route('/', methods=['GET', 'POST'])
def index():
    """display the main form and handle chart generation"""
    chart_svg = None
    chart_info = None
    
    if request.method == 'POST':
        # get form data
        symbol = request.form.get('symbol', '').strip().upper()
        chart_type = request.form.get('chart_type', 'line')
        time_series = request.form.get('time_series', 'daily')
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()
        
        # validate inputs
        if not symbol:
            flash('Please select or enter a stock symbol.', 'error')
        elif not start_date or not end_date:
            flash('Please provide both start and end dates.', 'error')
        else:
            # validate date format and generate chart
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                
                if end_date_obj < start_date_obj:
                    flash('End date cannot be before start date.', 'error')
                else:
                    # generate chart
                    chart_svg = generate_chart_for_web(
                        symbol=symbol,
                        period=time_series,
                        start_date=start_date,
                        end_date=end_date,
                        chart_type=chart_type
                    )
                    
                    # store chart info for display
                    chart_info = {
                        'symbol': symbol,
                        'chart_type': chart_type.capitalize(),
                        'time_series': time_series.capitalize(),
                        'start_date': start_date,
                        'end_date': end_date
                    }
                    
                    flash('Chart generated successfully!', 'success')
                    
            except ValueError:
                flash('Invalid date format. Please use YYYY-MM-DD format.', 'error')
            except StockSymbolNotFoundError as e:
                flash(f'Stock Symbol Not Found: {str(e)}', 'error')
            except APIRateLimitError as e:
                flash(f'API Rate Limit Exceeded: {str(e)}', 'error')
            except NoDataAvailableError as e:
                flash(f'No Data Available: {str(e)}', 'error')
            except Exception as e:
                flash(f'An unexpected error occurred: {str(e)}', 'error')
    
    return render_template(
        'index.html',
        stock_symbols=STOCK_SYMBOLS,
        chart_svg=chart_svg,
        chart_info=chart_info
    )


if __name__ == '__main__':
    # run the flask development server
    # in production, use a proper wsgi server like gunicorn
    app.run(host='0.0.0.0', port=3003, debug=True)