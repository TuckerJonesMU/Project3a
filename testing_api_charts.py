'''
import os
import sys
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv


from charts import generate_chart_from_api

from dotenv import load_dotenv
load_dotenv()

generate_chart_from_api(
    symbol="MSFT",
    period="weekly",
    chart_type="bar",
    start_date="2024-06-01",
    end_date="2024-09-30"
)
'''