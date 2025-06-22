import time
import logging
import MetaTrader5 as mt5
from datetime import datetime
from utils import retry  # We'll provide utils.py later

class MT5Manager:
    def __init__(self, login, password, server):
        self.login = login
        self.password = password
        self.server = server
        self.max_retries = 5
        self.connection_retries = 0
        self.initialize_connection()

    def initialize_connection(self):
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            error = mt5.last_error()
            logging.error(f"MT5 initialization failed, error code: {error}")
            if self.connection_retries < self.max_retries:
                self.connection_retries += 1
                wait_time = 2 ** self.connection_retries
                logging.info(f"Retrying MT5 connection in {wait_time} seconds...")
                time.sleep(wait_time)
                return self.initialize_connection()
            raise RuntimeError(f"Failed to initialize MT5 after {self.max_retries} attempts")
        logging.info("MT5 initialized successfully")
        self.connection_retries = 0

    def shutdown(self):
        mt5.shutdown()
        logging.info("MT5 shutdown completed.")

    @retry()
    def get_account_info(self):
        return mt5.account_info()

    @retry()
    def get_symbol_info(self, symbol):
        return mt5.symbol_info(symbol)

    @retry()
    def get_symbol_tick(self, symbol):
        return mt5.symbol_info_tick(symbol)

    @retry()
    def copy_rates(self, symbol, timeframe, n=500):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
        if rates is None:
            raise ValueError(f"Failed to copy rates for {symbol} timeframe {timeframe}")
        import pandas as pd
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    @retry()
    def history_deals_get(self, from_time, to_time, symbol=None):
        return mt5.history_deals_get(from_time, to_time, group=symbol)

    @retry()
    def positions_get(self, symbol=None):
        return mt5.positions_get(symbol=symbol)

    @retry()
    def order_send(self, request):
        return mt5.order_send(request)

