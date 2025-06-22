import requests
import logging
from textblob import TextBlob

class NewsSentiment:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_news_sentiment(self, symbol):
        try:
            url = f'https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={self.api_key}'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            sentiments = []
            for news in data.get('data', []):
                headline = news.get('headline', '')
                polarity = TextBlob(headline).sentiment.polarity
                sentiments.append(polarity)
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
            return avg_sentiment
        except Exception as e:
            logging.error(f"News sentiment fetch error: {e}")
            return 0
