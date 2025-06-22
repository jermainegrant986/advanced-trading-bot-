import logging
import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from pykalman import KalmanFilter
from datetime import datetime, timedelta
from economic_calendar import EconomicCalendar  # your module
from telegram_notifier import TelegramNotifier  # your module

class TradeExecutor:
    def __init__(self, mt5_manager, notifier: TelegramNotifier):
        self.mt5_manager = mt5_manager
        self.notifier = notifier
        self.kalman_filters = {}
        self.economic_calendar = EconomicCalendar()

    def init_kalman_filter(self, symbol):
        kf = KalmanFilter(
            transition_matrices=[1],
            observation_matrices=[1],
            initial_state_mean=0,
            initial_state_covariance=1,
            observation_covariance=1,
            transition_covariance=0.01
        )
        self.kalman_filters[symbol] = kf
        return kf

    def get_filtered_price(self, symbol, prices):
        if symbol not in self.kalman_filters:
            self.init_kalman_filter(symbol)

        kf = self.kalman_filters[symbol]
        if len(prices) < 10:
            return prices[-1] if len(prices) > 0 else None

        filtered_state_means, _ = kf.filter(prices)
        return filtered_state_means[-1][0]

    def calculate_lot_size(self, symbol, entry_price, stop_price, risk_percent):
        account_info = self.mt5_manager.get_account_info()
        symbol_info = self.mt5_manager.get_symbol_info(symbol)
        if account_info is None or symbol_info is None:
            return 0.01

        current_balance = account_info.balance
        drawdown = (account_info.equity - current_balance) / account_info.equity if account_info.equity > 0 else 0

        adjusted_risk = risk_percent
        if drawdown > 0.05:
            adjusted_risk = max(risk_percent * 0.5, 0.005)

        risk_amount = current_balance * adjusted_risk
        pip_value = symbol_info.trade_tick_value / symbol_info.trade_tick_size
        pips_risk = abs(entry_price - stop_price) / symbol_info.point

        if pips_risk == 0:
            return 0.01

        lot_size = (risk_amount / pips_risk) / pip_value
        lot_size = max(round(lot_size, 2), symbol_info.volume_min)
        lot_size = min(lot_size, symbol_info.volume_max)

        margin_required = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY if entry_price > stop_price else mt5.ORDER_TYPE_SELL,
            symbol,
            lot_size,
            entry_price
        )

        if margin_required is None or margin_required > account_info.margin_free:
            logging.warning("Insufficient margin for desired position size")
            return 0.01

        return lot_size

    def calculate_dynamic_stops(self, symbol, entry_price, direction, atr):
        symbol_info = self.mt5_manager.get_symbol_info(symbol)
        if not symbol_info:
            return None, None

        point = symbol_info.point
        spread = symbol_info.ask - symbol_info.bid

        if direction == "BUY":
            base_sl = entry_price - (atr * 1.5 * point)
            base_tp = entry_price + (atr * 3 * point)
            base_sl -= spread
            base_tp -= spread
            base_sl = max(base_sl, symbol_info.ask - (symbol_info.ask * 0.05))
        else:
            base_sl = entry_price + (atr * 1.5 * point)
            base_tp = entry_price - (atr * 3 * point)
            base_sl += spread
            base_tp += spread
            base_sl = min(base_sl, symbol_info.bid + (symbol_info.bid * 0.05))

        return base_sl, base_tp

    def should_enter_trade(self, symbol, direction, current_price):
        regime = self.mt5_manager.check_market_regime(symbol)
        recent_ticks = self.mt5_manager.get_ticks(symbol, n=50)
        recent_prices = [tick.last for tick in recent_ticks]
        filtered_price = self.get_filtered_price(symbol, recent_prices)

        if filtered_price is None:
            return False

        if regime == "trending":
            ma_fast = pd.Series(recent_prices).rolling(9).mean().iloc[-1]
            ma_slow = pd.Series(recent_prices).rolling(21).mean().iloc[-1]
            if direction == "BUY" and ma_fast < ma_slow:
                return False
            elif direction == "SELL" and ma_fast > ma_slow:
                return False

        if self.economic_calendar.is_high_impact_event_now():
            return False

        return True

    def open_position(self, symbol, order_type, lot_size, entry_price, sl, tp):
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": entry_price,
            "sl": sl,
            "tp": tp,
            "deviation": 10,
            "magic": 234000,
            "comment": "Advanced bot",
        }
        result = self.mt5_manager.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            msg = f"Position opened: {'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} {lot_size} lots on {symbol} at {entry_price:.5f}"
            logging.info(msg)
            self.notifier.send_message(msg)
            return result
        else:
            logging.error(f"Failed to open position: {result}")
            return None

    def close_position(self, position):
        tick = self.mt5_manager.get_symbol_tick(position.symbol)
        if tick is None:
            return False
        price = tick.bid if position.type == mt5.POSITION_TYPE_BUY else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": position.ticket,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "price": price,
            "deviation": 10,
            "magic": 234000,
            "comment": "Close position",
        }
        result = self.mt5_manager.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            msg = f"Position closed: {position.volume} lots on {position.symbol} at {price:.5f}"
            logging.info(msg)
            self.notifier.send_message(msg)
            return True
        else:
            logging.error(f"Failed to close position: {result}")
            return False
