import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, TimeSeriesSplit, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from indicators import Indicators  # import your indicators module

SYMBOLS = os.getenv("SYMBOLS", "EURUSD,GBPUSD,USDJPY").split(",")
MODEL_VERSION = os.getenv("MODEL_VERSION", "v2")

class MLModelManager:
    def __init__(self, mt5_manager):
        self.mt5_manager = mt5_manager
        self.models = {}
        self.model_metadata = {}
        self.load_all_models()

    def load_all_models(self):
        for symbol in SYMBOLS:
            model_file = f"ml_model_{symbol}_{MODEL_VERSION}.pkl"
            meta_file = f"ml_model_{symbol}_{MODEL_VERSION}.meta"
            if os.path.exists(model_file):
                try:
                    model = joblib.load(model_file)
                    self.models[symbol] = model
                    if os.path.exists(meta_file):
                        with open(meta_file, 'r') as f:
                            self.model_metadata[symbol] = json.load(f)
                    logging.info(f"Loaded model for {symbol} (version {MODEL_VERSION})")
                except Exception as e:
                    logging.error(f"Failed to load model for {symbol}: {e}")
                    self.train_ml_model(symbol)
            else:
                self.train_ml_model(symbol)

    def save_model_metadata(self, symbol, metrics):
        meta_file = f"ml_model_{symbol}_{MODEL_VERSION}.meta"
        with open(meta_file, 'w') as f:
            json.dump(metrics, f)
        self.model_metadata[symbol] = metrics

    def prepare_features(self, df):
        df['return'] = df['close'].pct_change()
        df['ma_fast'] = df['close'].rolling(9).mean()
        df['ma_slow'] = df['close'].rolling(21).mean()
        df['rsi'] = Indicators.compute_rsi(df['close'])
        df['atr'] = Indicators.compute_atr(df)
        df['macd'], df['macd_signal'] = Indicators.compute_macd(df['close'])
        df['volatility'] = df['high'] - df['low']
        df['spread'] = df['open'] - df['close'].shift(1)
        df.dropna(inplace=True)
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        return df

    def train_ml_model(self, symbol):
        df = self.mt5_manager.copy_rates(symbol, mt5.TIMEFRAME_M15, n=2000)
        if df.empty:
            logging.error(f"No data to train ML model for {symbol}")
            return None

        df = self.prepare_features(df)
        features = ['return', 'ma_fast', 'ma_slow', 'rsi', 'atr', 'macd', 'macd_signal', 'volatility', 'spread']
        X = df[features]
        y = df['target']

        tscv = TimeSeriesSplit(n_splits=5)
        param_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [5, 10, 15],
            'min_samples_split': [2, 5, 10]
        }

        model = RandomForestClassifier(class_weight='balanced', random_state=42, n_jobs=-1)
        grid_search = GridSearchCV(model, param_grid, cv=tscv, scoring='f1', n_jobs=-1, verbose=1)
        grid_search.fit(X, y)

        best_model = grid_search.best_estimator_
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, shuffle=False)
        val_score = best_model.score(X_val, y_val)
        train_score = best_model.score(X_train, y_train)

        if train_score - val_score > 0.15:
            logging.warning(f"Potential overfitting for {symbol} (train: {train_score:.2f}, val: {val_score:.2f})")

        model_file = f"ml_model_{symbol}_{MODEL_VERSION}.pkl"
        joblib.dump(best_model, model_file)

        metrics = {
            'train_score': train_score,
            'val_score': val_score,
            'best_params': grid_search.best_params_,
            'feature_importance': dict(zip(features, best_model.feature_importances_))
        }
        self.save_model_metadata(symbol, metrics)
        logging.info(f"Trained model for {symbol} with validation accuracy: {val_score:.2%}")
        self.models[symbol] = best_model
        return best_model

    def predict_direction(self, symbol, latest_data):
        model = self.models.get(symbol)
        if model is None:
            model = self.train_ml_model(symbol)
        features = ['return', 'ma_fast', 'ma_slow', 'rsi', 'atr', 'macd', 'macd_signal', 'volatility', 'spread']
        try:
            X = latest_data[features].values.reshape(1, -1)
            pred = model.predict(X)
            return pred[0]
        except Exception as e:
            logging.error(f"Prediction error: {e}")
            return None

    def retrain_all_models(self):
        for symbol in SYMBOLS:
            self.train_ml_model(symbol)
