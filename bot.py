import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from modules.mt5_manager import MT5Manager
from modules.ml_model_manager import MLModelManager
from modules.telegram_notifier import TelegramNotifier
from modules.trade_executor import TradeExecutor
from modules.trade_logger import TradeLogger
from modules.economic_calendar import EconomicCalendar
from modules.news_sentiment import NewsSentiment
from flask import Flask, jsonify, render_template_string
import threading

# Load environment variables
load_dotenv()

# Configuration constants
MT5_LOGIN = int(os.getenv("MT5_LOGIN"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")
SYMBOLS = os.getenv("SYMBOLS", "EURUSD,GBPUSD,USDJPY").split(",")
BASE_RISK_PERCENT = float(os.getenv("BASE_RISK_PERCENT", 0.01))
MAX_RISK_PERCENT = float(os.getenv("MAX_RISK_PERCENT", 0.03))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TradingBot:
    def __init__(self):
        self.mt5_manager = MT5Manager(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER)
        self.strategy = MLModelManager(self.mt5_manager)
        self.notifier = TelegramNotifier(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, self)
        self.executor = TradeExecutor(self.mt5_manager, self.notifier)
        self.trade_logger = TradeLogger(self.mt5_manager)
        self.economic_calendar = EconomicCalendar()
        self.news_sentiment = NewsSentiment(os.getenv("NEWS_API_KEY"))
        self.trading_enabled = True
        self.current_risk = BASE_RISK_PERCENT
        self.performance_metrics = {
            'equity_curve': [],
            'trade_history': [],
            'max_drawdown': 0,
            'start_balance': 0
        }
        self.config_mtime = os.path.getmtime('.env') if os.path.exists('.env') else 0

        # Setup Flask dashboard
        self.app = Flask(__name__)
        self.setup_dashboard()
        threading.Thread(target=lambda: self.app.run(host='0.0.0.0', port=5000), daemon=True).start()

    def setup_dashboard(self):
        @self.app.route('/')
        def dashboard():
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head><title>Trading Bot Dashboard</title></head>
            <body>
                <h1>Trading Bot Dashboard</h1>
                <div id="metrics"></div>
                <script>
                    async function fetchData() {
                        const res = await fetch('/data');
                        const data = await res.json();
                        document.getElementById('metrics').innerText = JSON.stringify(data, null, 2);
                    }
                    setInterval(fetchData, 5000);
                    fetchData();
                </script>
            </body>
            </html>
            """)

        @self.app.route('/data')
        def data():
            return jsonify(self.performance_metrics)

    async def config_reloader(self):
        while True:
            await asyncio.sleep(60)
            if not os.path.exists('.env'):
                continue
            current_mtime = os.path.getmtime('.env')
            if current_mtime > self.config_mtime:
                load_dotenv(override=True)
                logging.info("Configuration reloaded from .env")
                self.config_mtime = current_mtime
                self.current_risk = float(os.getenv("BASE_RISK_PERCENT", BASE_RISK_PERCENT))

    async def run(self):
        logging.info("Starting trading bot...")
        account_info = self.mt5_manager.get_account_info()
        if account_info:
            self.performance_metrics['start_balance'] = account_info.balance

        asyncio.create_task(self.config_reloader())

        while self.trading_enabled:
            try:
                for symbol in SYMBOLS:
                    # Fetch data, generate signals, predict, execute trades
                    # (Implement your trading logic here or call methods)
                    pass

                # Update performance metrics, log trades, etc.

                await asyncio.sleep(60)  # Run every minute
            except Exception as e:
                logging.error(f"Error in main loop: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = TradingBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
