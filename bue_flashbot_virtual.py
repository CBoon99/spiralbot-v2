"""
SpiralBot v2.1 - Cryptocurrency Trading Simulation System
=====================================================

UK Banking Compliant Version - CoinGecko Data Only
Due to UK banking restrictions, this system operates exclusively 
in simulation mode using CoinGecko price data.

No live exchange integration permitted at this time.
"""

import requests
import time
import random
import csv
import argparse
import signal
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Dynamic configuration - no hardcoded paths
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "bue_log.csv"
BOT_LOG_FILE = BASE_DIR / "bot.log"

# Trading configuration - environment variable driven
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', 0.05))
SCAN_INTERVAL = int(os.getenv('SCAN_INTERVAL', 30))
PORTFOLIO_INITIAL = float(os.getenv('PORTFOLIO_INITIAL', 1000.0))
TOP_N = int(os.getenv('TOP_N', 50))
TRADE_DURATION = int(os.getenv('TRADE_DURATION', 300))
TRAILING_STOP_PCT = float(os.getenv('TRAILING_STOP_PCT', 0.02))
STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PCT', 0.03))
TAKE_PROFIT_PCT = float(os.getenv('TAKE_PROFIT_PCT', 0.05))
FEE_PCT = float(os.getenv('FEE_PCT', 0.001))
MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', 3))

# UK Banking Compliance Check
LIVE_MODE_ENABLED = False  # Hardcoded to False for UK compliance
if os.getenv('SPIRALBOT_LIVE_OVERRIDE') == 'true':
    logging.warning("⚠️ LIVE mode override detected but disabled due to UK banking restrictions")

session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

# Professional logging setup
def setup_logging():
    """Configure professional logging with rotation"""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(session_id)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(BOT_LOG_FILE)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler for important messages only
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    console_handler.setLevel(logging.WARNING)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Ensure all log records include the session_id field
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.session_id = session_id
        return record

    logging.setLogRecordFactory(record_factory)
    return logger

class BotManager:
    def __init__(self):
        self.prices = {}
        self.price_history = {}
        self.cash = PORTFOLIO_INITIAL
        self.portfolio_value = PORTFOLIO_INITIAL
        self.positions = {}
        self.state_saved = False
        self.last_activity = datetime.now()
        self.total_api_calls = 0
        self.session = self._create_robust_session()
        
        # Ensure required directories exist
        BASE_DIR.mkdir(exist_ok=True)
        
        logging.info("SpiralBot v2.1 initialized - UK Banking Compliant (CoinGecko Only)")

    def _create_robust_session(self):
        """Create HTTP session with robust retry strategy"""
        session = requests.Session()
        
        # Retry strategy for CoinGecko API
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Professional headers
        session.headers.update({
            'User-Agent': 'SpiralBot/2.1 (UK-Compliant-Trading-Simulator)',
            'Accept': 'application/json'
        })
        
        return session

    def fetch_coingecko_data(self, n=TOP_N):
        """
        Fetch cryptocurrency price data from CoinGecko API
        
        Note: This is the ONLY permitted data source due to UK banking restrictions.
        Live exchange APIs (Binance, Coinbase, etc.) are not compatible with UK bank accounts.
        """
        url = 'https://api.coingecko.com/api/v3/coins/markets'
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': min(n, 100),  # API limit compliance
            'page': 1,
            'sparkline': 'false',
            'price_change_percentage': '24h'
        }
        
        try:
            self.total_api_calls += 1
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if not isinstance(data, list):
                logging.error("CoinGecko API returned unexpected format: %s", data)
                return {}
            
            # Extract price data with validation
            price_data = {}
            for item in data:
                symbol = item.get("symbol", "").upper()
                price = item.get("current_price")
                
                if symbol and price is not None and price > 0:
                    price_data[symbol] = float(price)
            
            logging.info("Fetched %d prices from CoinGecko (API call #%d)", 
                        len(price_data), self.total_api_calls)
            return price_data
            
        except requests.exceptions.RequestException as e:
            logging.error("CoinGecko API error: %s", e)
            return {}
        except (ValueError, KeyError) as e:
            logging.error("Data parsing error: %s", e)
            return {}

    def calculate_bue_value(self, symbol, current_price):
        """
        Calculate BUE (Bot's Understanding of Expected) value
        Uses technical analysis instead of pure randomness
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(current_price)
        
        # Maintain rolling window of 20 prices
        if len(self.price_history[symbol]) > 20:
            self.price_history[symbol].pop(0)
        
        # Insufficient data - return current price
        if len(self.price_history[symbol]) < 5:
            return current_price
        
        # Calculate momentum factor (trend analysis)
        momentum_factor = 0
        if len(self.price_history[symbol]) >= 10:
            recent_avg = sum(self.price_history[symbol][-5:]) / 5
            older_avg = sum(self.price_history[symbol][-10:-5]) / 5
            
            if older_avg > 0:
                momentum_factor = (recent_avg - older_avg) / older_avg * 0.15
        
        # Calculate volatility factor
        volatility_factor = 0
        if len(self.price_history[symbol]) >= 10:
            recent_prices = self.price_history[symbol][-10:]
            price_range = max(recent_prices) - min(recent_prices)
            
            if current_price > 0:
                volatility = price_range / current_price
                volatility_factor = min(max(volatility * 0.08, -0.03), 0.03)
        
        # Minimal random component for market unpredictability
        random_component = random.uniform(-0.008, 0.008)  # ±0.8%
        
        # Combine factors
        total_adjustment = momentum_factor + volatility_factor + random_component
        bue_value = current_price * (1 + total_adjustment)
        
        return round(bue_value, 8)

    def generate_signal(self, current_price, bue_value):
        """Generate trading signal based on BUE analysis"""
        if current_price <= 0:
            return "HOLD", 0.0
        
        delta = ((bue_value - current_price) / current_price) * 100
        
        # Conservative thresholds for quality signals
        if delta > 1.2:
            return "BUY", delta
        elif delta < -1.2:
            return "SELL", delta
        else:
            return "HOLD", delta

    def log_to_csv(self, row_data):
        """
        Professional CSV logging with file locking and retry logic
        Ensures data integrity during concurrent access
        """
        header = [
            "session_id", "timestamp", "symbol", "price", "bue", "delta", 
            "signal", "value_estimate", "action", "pnl", "close_reason", "equity"
        ]
        
        # Ensure session_id is properly formatted
        if len(row_data) == len(header) - 1:
            row_data.insert(0, session_id)
        elif len(row_data) == len(header) and row_data[0] != session_id:
            row_data[0] = session_id
        
        # Ensure log file exists with header
        if not LOG_FILE.exists():
            try:
                with open(LOG_FILE, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(header)
            except Exception as e:
                logging.error("Failed to create log file: %s", e)
                return False
        
        # Append data with retry logic and file locking
        for attempt in range(3):
            try:
                with open(LOG_FILE, 'a', newline='') as file:
                    # Acquire file lock
                    import fcntl
                    fcntl.flock(file.fileno(), fcntl.LOCK_EX)
                    
                    # Verify header matches
                    file.seek(0)
                    reader = csv.reader(file)
                    existing_header = next(reader, None)
                    if existing_header != header:
                        logging.error("CSV header mismatch - expected: %s, got: %s", 
                                    header, existing_header)
                        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
                        return False
                    
                    # Write data
                    file.seek(0, 2)  # Seek to end
                    writer = csv.writer(file)
                    writer.writerow(row_data)
                    
                    # Release file lock
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)
                
                self.state_saved = True
                return True
                
            except Exception as e:
                logging.error("CSV write error (attempt %d): %s", attempt + 1, e)
                time.sleep(0.2)
        
        logging.error("Failed to write to CSV after 3 attempts")
        return False

    def deposit_funds(self, amount):
        """Process fund deposit - simulation only"""
        if amount <= 0:
            logging.warning("Invalid deposit amount: %.2f", amount)
            return False
        
        self.cash += amount
        self.portfolio_value += amount
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        logging.info("Deposited £%.2f (New balance: £%.2f)", amount, self.cash)
        
        # Log deposit transaction
        deposit_row = [
            session_id, timestamp, "SYSTEM", 0, 0, 0, "DEPOSIT",
            amount, "DEPOSIT", 0, "N/A", self.portfolio_value
        ]
        
        return self.log_to_csv(deposit_row)

    def execute_trade(self, symbol, signal, price, delta):
        """
        Execute simulated trade
        
        Note: All trades are SIMULATION ONLY due to UK banking restrictions.
        No real money or exchange APIs are involved.
        """
        # Pre-trade validation
        if signal not in ["BUY", "SELL"]:
            return False
        
        if len(self.positions) >= MAX_POSITIONS:
            logging.debug("Maximum positions reached (%d)", MAX_POSITIONS)
            return False
        
        if symbol in self.positions:
            logging.debug("Position already exists for %s", symbol)
            return False
        
        # Calculate trade size
        trade_value = self.cash * RISK_PER_TRADE
        if trade_value < 10:  # Minimum trade size
            logging.debug("Insufficient funds for trade (£%.2f available)", self.cash)
            return False
        
        # Calculate fees and net position
        fee = trade_value * FEE_PCT
        net_trade_value = trade_value - fee
        quantity = net_trade_value / price
        
        # Open position
        self.positions[symbol] = {
            "entry_price": price,
            "quantity": quantity,
            "timestamp": datetime.now(),
            "peak_price": price,
            "side": signal,
            "trade_value": net_trade_value
        }
        
        # Update cash
        self.cash -= trade_value
        self.last_activity = datetime.now()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.info("SIMULATED %s: %s @ £%.4f | Qty: %.6f | Fee: £%.2f", 
                    signal, symbol, price, quantity, fee)
        
        # Log trade opening
        trade_row = [
            session_id, timestamp, symbol, price, 0, delta, signal,
            net_trade_value, "OPEN", 0, "N/A", self.calculate_equity({symbol: price})
        ]
        
        return self.log_to_csv(trade_row)

    def close_position(self, symbol, current_price, reason):
        """Close a trading position with P&L calculation"""
        if symbol not in self.positions:
            return 0, "NONE", reason
        
        pos = self.positions[symbol]
        entry_price = pos["entry_price"]
        quantity = pos["quantity"]
        side = pos["side"]
        
        # Calculate P&L based on position side
        if side == "BUY":
            proceeds = quantity * current_price
            pnl = proceeds - pos["trade_value"]
        else:  # SELL
            proceeds = pos["trade_value"]
            cost = quantity * current_price
            pnl = proceeds - cost
        
        # Apply exit fees
        exit_fee = proceeds * FEE_PCT
        net_pnl = pnl - exit_fee
        
        # Update portfolio
        self.cash += proceeds - exit_fee
        action = f"CLOSE_{side}"
        self.last_activity = datetime.now()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.info("SIMULATED %s: %s @ £%.4f | P&L: £%.2f | Reason: %s", 
                    action, symbol, current_price, net_pnl, reason)
        
        # Log position closing
        close_row = [
            session_id, timestamp, symbol, current_price, 0, 0, action,
            proceeds, action, net_pnl, reason, self.calculate_equity({symbol: current_price})
        ]
        
        self.log_to_csv(close_row)
        
        # Remove position
        del self.positions[symbol]
        return net_pnl, action, reason

    def calculate_equity(self, current_prices):
        """Calculate total portfolio value including unrealized P&L"""
        unrealized_pnl = 0
        
        for symbol, pos in self.positions.items():
            current_price = current_prices.get(symbol, pos["entry_price"])
            
            if pos["side"] == "BUY":
                market_value = pos["quantity"] * current_price
                unrealized_pnl += market_value - pos["trade_value"]
            else:  # SELL
                cost = pos["quantity"] * current_price
                unrealized_pnl += pos["trade_value"] - cost
        
        self.portfolio_value = self.cash + unrealized_pnl
        return self.portfolio_value

    def manage_positions(self, current_prices):
        """Manage open positions with risk controls"""
        if not self.positions:
            return 0, "NONE", "N/A"
        
        current_time = datetime.now()
        
        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            current_price = current_prices.get(symbol, pos["entry_price"])
            
            # Update peak price for trailing stops
            if pos["side"] == "BUY":
                pos["peak_price"] = max(pos["peak_price"], current_price)
            else:
                pos["peak_price"] = min(pos["peak_price"], current_price)
            
            peak_price = pos["peak_price"]
            entry_price = pos["entry_price"]
            
            # Check exit conditions
            
            # 1. Trailing stop loss
            if pos["side"] == "BUY" and current_price <= peak_price * (1 - TRAILING_STOP_PCT):
                return self.close_position(symbol, current_price, "TRAILING_STOP")
            elif pos["side"] == "SELL" and current_price >= peak_price * (1 + TRAILING_STOP_PCT):
                return self.close_position(symbol, current_price, "TRAILING_STOP")
            
            # 2. Hard stop loss
            if pos["side"] == "BUY" and current_price <= entry_price * (1 - STOP_LOSS_PCT):
                return self.close_position(symbol, current_price, "STOP_LOSS")
            elif pos["side"] == "SELL" and current_price >= entry_price * (1 + STOP_LOSS_PCT):
                return self.close_position(symbol, current_price, "STOP_LOSS")
            
            # 3. Take profit
            if pos["side"] == "BUY" and current_price >= entry_price * (1 + TAKE_PROFIT_PCT):
                return self.close_position(symbol, current_price, "TAKE_PROFIT")
            elif pos["side"] == "SELL" and current_price <= entry_price * (1 - TAKE_PROFIT_PCT):
                return self.close_position(symbol, current_price, "TAKE_PROFIT")
            
            # 4. Time-based exit
            position_age = (current_time - pos["timestamp"]).total_seconds()
            if position_age >= TRADE_DURATION:
                return self.close_position(symbol, current_price, "TIMED_EXIT")
        
        return 0, "NONE", "N/A"

    def run_simulation(self):
        """
        Main simulation loop
        
        UK Banking Compliant: All trading is simulated using CoinGecko data only.
        No real exchange connections or live trading capabilities.
        """
        
        logging.info("🌀 SpiralBot v2.1 - UK Banking Compliant Simulation Started")
        logging.info("Data Source: CoinGecko API (Simulation Only)")
        logging.info("Initial Portfolio: £%.2f", PORTFOLIO_INITIAL)
        
        def graceful_shutdown(signum, frame):
            """Handle shutdown signals gracefully"""
            signal_name = signal.Signals(signum).name
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            logging.info("Received %s signal - shutting down gracefully", signal_name)
            
            # Save final state
            if not self.state_saved:
                shutdown_row = [
                    session_id, timestamp, "SYSTEM", 0, 0, 0, "SHUTDOWN",
                    0, "SHUTDOWN", 0, "GRACEFUL", self.portfolio_value
                ]
                self.log_to_csv(shutdown_row)
            
            logging.info("Final Portfolio Value: £%.2f", self.portfolio_value)
            logging.info("Total API Calls: %d", self.total_api_calls)
            logging.info("SpiralBot shutdown complete")
            
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)
        
        cycle_count = 0
        
        while True:
            cycle_start = time.time()
            cycle_count += 1
            
            logging.info("=== Cycle %d ===", cycle_count)
            
            # Fetch market data from CoinGecko
            self.prices = self.fetch_coingecko_data()
            
            if not self.prices:
                logging.warning("No price data available - skipping cycle")
                time.sleep(SCAN_INTERVAL)
                continue
            
            # Process each symbol
            for symbol, price in self.prices.items():
                if price <= 0:
                    continue
                
                # Generate BUE value and signal
                bue_value = self.calculate_bue_value(symbol, price)
                signal_type, delta = self.generate_signal(price, bue_value)
                
                value_estimate = (self.cash / len(self.prices)) * (1 + delta / 100)
                
                # Execute trades on strong signals
                if signal_type in ["BUY", "SELL"] and abs(delta) > 1.5:
                    self.execute_trade(symbol, signal_type, price, delta)
                
                # Manage existing positions
                pnl, action, close_reason = self.manage_positions(self.prices)
                
                # Update portfolio value
                self.portfolio_value = self.calculate_equity(self.prices)
                
                # Log market scan
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                scan_row = [
                    session_id, timestamp, symbol, price, bue_value, delta,
                    signal_type, value_estimate, action if action != "NONE" else "SCAN",
                    pnl, close_reason if close_reason != "N/A" else "N/A", self.portfolio_value
                ]
                
                self.log_to_csv(scan_row)
                
                # Brief pause between symbols
                time.sleep(0.05)
            
            # Cycle summary
            cycle_duration = time.time() - cycle_start
            
            logging.info("Cycle %d complete (%.2fs) | Positions: %d | Cash: £%.2f | Equity: £%.2f",
                        cycle_count, cycle_duration, len(self.positions), self.cash, self.portfolio_value)
            
            # Sleep until next cycle
            time.sleep(max(0, SCAN_INTERVAL - cycle_duration))

def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description="SpiralBot v2.1 - UK Banking Compliant Trading Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
UK Banking Compliance Notice:
This system operates exclusively in simulation mode using CoinGecko data.
Live trading with exchange APIs is not supported due to UK banking restrictions.

Examples:
  python3 bue_flashbot_virtual.py              # Run simulation
  python3 bue_flashbot_virtual.py --debug      # Debug mode
        """
    )
    
    parser.add_argument(
        "--live", 
        action="store_true", 
        help="Live trading mode (DISABLED - UK banking restrictions)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.info("Debug mode enabled")
    
    # UK Compliance Check
    if args.live:
        logging.error("❌ LIVE mode disabled due to UK banking restrictions")
        logging.error("❌ Only CoinGecko simulation mode is permitted")
        print("\n🚫 LIVE TRADING DISABLED")
        print("Due to UK banking restrictions, only simulation mode is available.")
        print("Use CoinGecko data for simulation purposes only.\n")
        sys.exit(1)
    
    # Initialize and run bot
    try:
        bot = BotManager()
        bot.run_simulation()
        
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.error("Fatal error: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()