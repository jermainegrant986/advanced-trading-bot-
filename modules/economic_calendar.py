import requests
import logging
from datetime import datetime, timedelta

class EconomicCalendar:
    def __init__(self, api_key=None):
        self.api_key = api_key

    def is_high_impact_event_now(self):
        try:
            now = datetime.utcnow()
            url = f"https://economic-calendar.tradingview.com/events?minImportance=high&from={now.strftime('%Y-%m-%d')}&to={(now + timedelta(hours=1)).strftime('%Y-%m-%d')}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            events = response.json()
            return len(events) > 0
        except Exception as e:
            logging.error(f"Economic calendar error: {e}")
            return False
