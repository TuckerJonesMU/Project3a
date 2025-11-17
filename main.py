"""
Stock Data Visualizer - Main Application
This application queries the Alpha Vantage API and allows users to:
- Select a stock symbol
- Choose a chart type
- Choose a time series function
- Select a date range
- Generate and view a stock price chart
"""

from datetime import datetime
import sys
from charts import (
    generate_chart_from_api,
    StockSymbolNotFoundError,
    APIRateLimitError,
    NoDataAvailableError
)


def get_stock_symbol():
    """
    Prompts user to enter a stock symbol.
    Returns the stock symbol in uppercase.
    """
    while True:
        symbol = input("\nEnter the stock symbol: ").strip().upper()
        if symbol:
            return symbol
        print("Error: Stock symbol cannot be empty. Please try again.")


def get_chart_type():
    """
    Prompts user to select a chart type.
    Returns the selected chart type.
    """
    print("\nChart Types:")
    print("1. Line")
    print("2. Bar")
    
    chart_types = {
        "1": "line",
        "2": "bar",
    }
    
    while True:
        choice = input("\nEnter the chart type (1, 2): ").strip()
        if choice in chart_types:
            return chart_types[choice]
        print("Error: Invalid choice. Please enter 1 or 2.")


def get_time_series():
    """
    Prompts user to select a time series function.
    Returns the selected time series period.
    """
    print("\nTime Series Functions:")
    print("1. Intraday")
    print("2. Daily")
    print("3. Weekly")
    print("4. Monthly")
    
    time_series_map = {
        "1": "intraday",
        "2": "daily",
        "3": "weekly",
        "4": "monthly",
    }
    
    while True:
        choice = input("\nEnter the time series function (1, 2, 3, 4): ").strip()
        if choice in time_series_map:
            return time_series_map[choice]
        print("Error: Invalid choice. Please enter 1, 2, 3, or 4.")


def get_date(prompt):
    """
    Prompts user to enter a date in YYYY-MM-DD format.
    Validates the date format and returns a datetime object.
    """
    while True:
        date_str = input(f"\n{prompt} (YYYY-MM-DD): ").strip()
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return date_str, date_obj
        except ValueError:
            print("Error: Invalid date format. Please use YYYY-MM-DD format (e.g., 2024-01-15).")


def get_date_range():
    """
    Prompts user for start and end dates.
    Validates that end date is not before start date.
    Returns (start_date_str, end_date_str).
    """
    start_date_str, start_date_obj = get_date("Enter the start date")
    
    while True:
        end_date_str, end_date_obj = get_date("Enter the end date")
        
        if end_date_obj >= start_date_obj:
            return start_date_str, end_date_str
        
        print(f"Error: End date ({end_date_str}) cannot be before start date ({start_date_str}).")
        print("Please enter a valid end date.")


def display_welcome():
    """Displays welcome message and application information."""
    print("=" * 60)
    print("           STOCK DATA VISUALIZER")
    print("=" * 60)
    print("\nWelcome! This application visualizes stock data from")
    print("Alpha Vantage API for your selected date range.\n")


def display_summary(symbol, chart_type, time_series, start_date, end_date):
    """Displays a summary of user selections."""
    print("\n" + "=" * 60)
    print("SUMMARY OF YOUR SELECTIONS")
    print("=" * 60)
    print(f"Stock Symbol:      {symbol}")
    print(f"Chart Type:        {chart_type.capitalize()}")
    print(f"Time Series:       {time_series.capitalize()}")
    print(f"Start Date:        {start_date}")
    print(f"End Date:          {end_date}")
    print("=" * 60)


def ask_continue():
    """
    Asks user if they want to view another stock symbol.
    Returns True to continue, False to exit.
    """
    while True:
        response = input("\nWould you like to view another stock? (y/n): ").strip().lower()
        if response == 'n':
            return False
        elif response == 'y' or response == '':
            return True
        else:
            print("Please enter 'y' to continue or 'n' to exit.")


def main():
    """
    Main application function.
    Collects user input and generates stock chart.
    """
    # Display welcome message once
    display_welcome()
    
    # Main loop - continues until user chooses to exit
    while True:
        try:
            # Collect user input
            symbol = get_stock_symbol()
            chart_type = get_chart_type()
            time_series = get_time_series()
            start_date, end_date = get_date_range()
            
            # Display summary
            display_summary(symbol, chart_type, time_series, start_date, end_date)
            
            # Generate chart
            print("\nFetching data from Alpha Vantage API...")
            print("Please wait, this may take a moment...\n")
            
            html_path = generate_chart_from_api(
                symbol=symbol,
                period=time_series,
                start_date=start_date,
                end_date=end_date,
                chart_type=chart_type
            )
            
            print(f"✓ Success! Chart has been generated and opened in your browser.")
            print(f"  Chart file: {html_path}")
            
            # Ask if user wants to continue
            if not ask_continue():
                print("\nThank you for using Stock Data Visualizer. Goodbye!")
                break
            
            # Add separator for next iteration
            print("\n" + "=" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n\nApplication interrupted by user. Exiting...")
            sys.exit(0)
        
        except StockSymbolNotFoundError as e:
            print(f"\n✗ Stock Symbol Not Found:")
            print(f"   {e}")
            print("\nTip: Make sure you're using the correct ticker symbol (e.g., AAPL, MSFT, GOOGL)")
            
            # Ask if user wants to try again
            if not ask_continue():
                sys.exit(1)
            print("\n" + "=" * 60 + "\n")
        
        except APIRateLimitError as e:
            print(f"\n✗ API Rate Limit Exceeded:")
            print(f"   {e}")
            
            # Ask if user wants to try again
            if not ask_continue():
                sys.exit(1)
            print("\n" + "=" * 60 + "\n")
        
        except NoDataAvailableError as e:
            print(f"\n✗ No Data Available:")
            print(f"   {e}")
            
            # Ask if user wants to try again
            if not ask_continue():
                sys.exit(1)
            print("\n" + "=" * 60 + "\n")
            
        except ValueError as e:
            print(f"\n✗ Input Error:")
            print(f"   {e}")
            
            # Ask if user wants to try again
            if not ask_continue():
                sys.exit(1)
            print("\n" + "=" * 60 + "\n")
            
        except RuntimeError as e:
            print(f"\n✗ Error:")
            print(f"   {e}")
            
            # Ask if user wants to try again
            if not ask_continue():
                sys.exit(1)
            print("\n" + "=" * 60 + "\n")
            
        except Exception as e:
            print(f"\n✗ Unexpected error occurred:")
            print(f"   {e}")
            print("\nPlease report this error if it persists.")
            
            # Ask if user wants to try again
            if not ask_continue():
                sys.exit(1)
            print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()