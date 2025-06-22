import os
import logging
import pandas as pd
from datetime import datetime, timedelta

class TradeLogger:
    def __init__(self, mt5_manager, log_file='trade_history.csv'):
        self.mt5_manager = mt5_manager
        self.log_file = log_file

    def log_closed_trades(self):
        try:
            now = datetime.utcnow()
            from_time = now - timedelta(days=7)
            deals = self.mt5_manager.history_deals_get(from_time, now)
            if deals is None or len(deals) == 0:
                logging.info("No recent closed trades to log.")
                return

            df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df[df['type'].isin([1, 2])]  # BUY and SELL only

            if os.path.exists(self.log_file):
                existing = pd.read_csv(self.log_file, parse_dates=['time'])
                combined = pd.concat([existing, df]).drop_duplicates(subset='ticket')
            else:
                combined = df

            combined.to_csv(self.log_file, index=False)
            logging.info(f"Logged {len(df)} closed trades to {self.log_file}")

        except Exception as e:
            logging.error(f"Trade logging failed: {e}", exc_info=True)

    def calculate_performance_metrics(self):
        if not os.path.exists(self.log_file):
            return None

        df = pd.read_csv(self.log_file)
        if df.empty:
            return None

        metrics = {
            'win_rate': len(df[df['profit'] > 0]) / len(df) * 100,
            'avg_win': df[df['profit'] > 0]['profit'].mean(),
            'avg_loss': df[df['profit'] <= 0]['profit'].mean(),
            'profit_factor': abs(df[df['profit'] > 0]['profit'].sum() / df[df['profit'] <= 0]['profit'].sum()),
            'max_drawdown': (df['balance'].max() - df['balance'].min()) / df['balance'].max()
        }

        return metrics
