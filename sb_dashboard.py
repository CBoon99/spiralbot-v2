"""
SpiralBot v2.1 Dashboard - UK Banking Compliant
===============================================

Professional trading simulation dashboard
CoinGecko data only - No live exchange integration permitted
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
import csv
import logging
import subprocess
import signal
import psutil
from datetime import datetime, timedelta
from pathlib import Path
import fcntl
from contextlib import contextmanager

# Dynamic configuration
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "bue_log.csv"
BOT_LOG_FILE = BASE_DIR / "bot.log"
BOT_SCRIPT = BASE_DIR / "bue_flashbot_virtual.py"
DASHBOARD_LOG_FILE = BASE_DIR / "dashboard.log"

# Dashboard configuration
PAGE_CONFIG = {
    "page_title": "SpiralBot v2.1 Dashboard",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Setup professional logging
logging.basicConfig(
    filename=DASHBOARD_LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_dashboard_event(message, level="info"):
    """Log dashboard events professionally"""
    if level == "error":
        logging.error(message)
    elif level == "warning":
        logging.warning(message)
    else:
        logging.info(message)

# Page configuration
st.set_page_config(**PAGE_CONFIG)

# UK Banking Compliance Notice
st.markdown("""
<div style="background-color: #1e3a8a; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
    <h3 style="color: white; margin: 0;">🌀 SpiralBot v2.1 - UK Banking Compliant</h3>
    <p style="color: #bfdbfe; margin: 0.5rem 0 0 0;">
        Simulation Mode Only | CoinGecko Data Source | No Live Exchange Integration
    </p>
</div>
""", unsafe_allow_html=True)

@contextmanager
def safe_file_operation(file_path, mode='r', timeout=3):
    """Professional file locking with timeout"""
    if not file_path.exists():
        if 'w' in mode or 'a' in mode:
            file_path.parent.mkdir(exist_ok=True)
        else:
            yield None
            return
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with open(file_path, mode) as f:
                if 'r' in mode:
                    fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                else:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield f
                return
        except (IOError, OSError, BlockingIOError):
            time.sleep(0.1)
    
    log_dashboard_event(f"File lock timeout: {file_path}", "warning")
    yield None

def load_trading_data():
    """Load and validate trading data with error handling"""
    try:
        with safe_file_operation(LOG_FILE, 'r') as f:
            if f is None:
                return pd.DataFrame()
            
            df = pd.read_csv(f)
            
            # Validate required columns
            required_cols = ['timestamp', 'symbol', 'price', 'action', 'pnl', 'equity']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"Invalid log format. Missing columns: {missing_cols}")
                log_dashboard_event(f"Missing columns in log: {missing_cols}", "error")
                return pd.DataFrame()
            
            # Clean and convert data
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.dropna(subset=['timestamp'])
            df = df.sort_values('timestamp')
            
            # Remove duplicates based on timestamp and symbol
            df = df.drop_duplicates(subset=['timestamp', 'symbol', 'action'], keep='last')
            
            return df
            
    except Exception as e:
        log_dashboard_event(f"Data loading error: {e}", "error")
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def get_bot_status():
    """Get detailed bot status information"""
    status = {
        "running": False,
        "pid": None,
        "start_time": None,
        "last_activity": None,
        "memory_usage": 0,
        "cpu_usage": 0
    }
    
    try:
        # Check for running bot processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                if any('bue_flashbot_virtual.py' in str(cmd) for cmd in proc.info['cmdline']):
                    status["running"] = True
                    status["pid"] = proc.info['pid']
                    status["start_time"] = datetime.fromtimestamp(proc.info['create_time'])
                    
                    # Get resource usage
                    process = psutil.Process(proc.info['pid'])
                    status["memory_usage"] = process.memory_info().rss / 1024 / 1024  # MB
                    status["cpu_usage"] = process.cpu_percent()
                    break
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    except Exception as e:
        log_dashboard_event(f"Error checking bot status: {e}", "warning")
    
    # Get last activity from log file
    try:
        df = load_trading_data()
        if not df.empty:
            status["last_activity"] = df['timestamp'].max()
    except:
        pass
    
    return status

def start_bot_process():
    """Start the bot process with error handling"""
    try:
        bot_status = get_bot_status()
        if bot_status["running"]:
            st.warning("⚠️ Bot is already running!")
            return False
        
        # Start bot process
        cmd = ["python3", str(BOT_SCRIPT)]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=BASE_DIR
        )
        
        # Store process info in session state
        st.session_state.bot_process = process
        st.session_state.bot_start_time = datetime.now()
        
        log_dashboard_event(f"Bot started with PID: {process.pid}")
        return True
        
    except Exception as e:
        log_dashboard_event(f"Failed to start bot: {e}", "error")
        st.error(f"Failed to start bot: {e}")
        return False

def stop_bot_process():
    """Stop the bot process gracefully"""
    try:
        bot_status = get_bot_status()
        if not bot_status["running"]:
            st.info("Bot is not running")
            return True
        
        # Send termination signal
        process = psutil.Process(bot_status["pid"])
        process.terminate()
        
        # Wait for graceful shutdown
        try:
            process.wait(timeout=10)
            log_dashboard_event("Bot stopped gracefully")
            return True
        except psutil.TimeoutExpired:
            # Force kill if necessary
            process.kill()
            log_dashboard_event("Bot force stopped")
            return True
            
    except Exception as e:
        log_dashboard_event(f"Error stopping bot: {e}", "error")
        st.error(f"Error stopping bot: {e}")
        return False

def make_deposit_transaction(amount):
    """Process deposit transaction with validation"""
    if amount <= 0:
        st.error("Invalid deposit amount")
        return False
    
    try:
        # Prepare deposit record
        header = ["session_id", "timestamp", "symbol", "price", "bue", "delta", 
                 "signal", "value_estimate", "action", "pnl", "close_reason", "equity"]
        
        # Ensure log file exists
        if not LOG_FILE.exists():
            with safe_file_operation(LOG_FILE, 'w') as f:
                if f is not None:
                    writer = csv.writer(f)
                    writer.writerow(header)
        
        # Get current equity
        current_df = load_trading_data()
        current_equity = current_df['equity'].iloc[-1] if not current_df.empty else 1000.0
        new_equity = current_equity + amount
        
        # Create deposit record
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        deposit_row = [
            session_id, timestamp, "SYSTEM", 0, 0, 0, "DEPOSIT",
            amount, "DEPOSIT", 0, "N/A", new_equity
        ]
        
        # Write deposit record
        with safe_file_operation(LOG_FILE, 'a') as f:
            if f is not None:
                writer = csv.writer(f)
                writer.writerow(deposit_row)
                log_dashboard_event(f"Deposit processed: £{amount}")
                return True
        
        return False
        
    except Exception as e:
        log_dashboard_event(f"Deposit error: {e}", "error")
        st.error(f"Deposit failed: {e}")
        return False

# Initialize session state
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if 'deposit_success' not in st.session_state:
    st.session_state.deposit_success = False

# Main dashboard layout
col1, col2 = st.columns([2, 1])

with col2:
    # Sidebar: Bot Control Panel
    st.markdown("### 🤖 Bot Control Panel")
    
    # Get current bot status
    bot_status = get_bot_status()
    
    # Display bot status with timestamp
    if bot_status["running"]:
        st.success("✅ Bot Running")
        st.write(f"**PID:** {bot_status['pid']}")
        
        if bot_status["start_time"]:
            runtime = datetime.now() - bot_status["start_time"]
            st.write(f"**Runtime:** {str(runtime).split('.')[0]}")
        
        if bot_status["last_activity"]:
            st.write(f"**Last Activity:** {bot_status['last_activity'].strftime('%H:%M:%S')}")
        
        st.write(f"**Memory:** {bot_status['memory_usage']:.1f} MB")
        
        # Stop button (enabled only when running)
        if st.button("🛑 Stop Bot", type="primary", key="stop_bot_btn"):
            with st.spinner("Stopping bot..."):
                if stop_bot_process():
                    st.success("Bot stopped successfully")
                    time.sleep(1)
                    st.rerun()
    else:
        st.error("⏹️ Bot Stopped")
        
        # Start button (enabled only when stopped)
        if st.button("▶️ Start Bot", type="primary", key="start_bot_btn"):
            with st.spinner("Starting bot..."):
                if start_bot_process():
                    st.success("Bot started successfully")
                    time.sleep(2)  # Give bot time to initialize
                    st.rerun()
    
    st.markdown("---")
    
    # Portfolio Management
    st.markdown("### 💰 Portfolio Management")
    
    # Load current data for portfolio display
    df = load_trading_data()
    
    if not df.empty:
        current_equity = df['equity'].iloc[-1]
        total_deposits = df[df['action'] == 'DEPOSIT']['value_estimate'].sum()
        
        # Display current stats
        st.metric("Current Equity", f"£{current_equity:.2f}")
        st.metric("Total Deposits", f"£{total_deposits:.2f}")
        
        # Calculate performance metrics
        if total_deposits > 0:
            performance = ((current_equity - total_deposits) / total_deposits) * 100
            st.metric("Performance", f"{performance:+.2f}%")
    else:
        st.metric("Current Equity", "£1,000.00")
        st.metric("Total Deposits", "£0.00")
    
    # Deposit interface
    st.markdown("**Make Deposit**")
    deposit_amount = st.number_input(
        "Amount (£)",
        min_value=1.0,
        max_value=10000.0,
        value=100.0,
        step=50.0,
        key="deposit_input"
    )
    
    if st.button("💳 Deposit Funds", key="deposit_btn"):
        with st.spinner("Processing deposit..."):
            if make_deposit_transaction(deposit_amount):
                st.session_state.deposit_success = True
                st.success(f"✅ Deposited £{deposit_amount:.2f}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Deposit failed")
    
    # Show deposit success message
    if st.session_state.deposit_success:
        st.balloons()
        st.session_state.deposit_success = False

with col1:
    # Main content area
    st.markdown("### 📊 Trading Dashboard")
    
    # Load and validate trading data
    df = load_trading_data()
    
    if df.empty:
        st.info("🚀 No trading data yet. Start the bot to begin simulation.")
        st.markdown("""
        **Getting Started:**
        1. Click **"▶️ Start Bot"** in the control panel
        2. Bot will begin fetching CoinGecko price data
        3. Trading activity will appear here within 1-2 minutes
        4. Use **"💳 Deposit Funds"** to add virtual capital
        """)
    else:
        # Performance summary
        latest_equity = df['equity'].iloc[-1]
        total_trades = len(df[df['action'].str.contains('CLOSE', na=False)])
        winning_trades = len(df[(df['action'].str.contains('CLOSE', na=False)) & (df['pnl'] > 0)])
        total_pnl = df[df['pnl'] != 0]['pnl'].sum()
        
        # Display key metrics
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        with metric_col1:
            st.metric("Portfolio Value", f"£{latest_equity:.2f}")
        with metric_col2:
            st.metric("Total Trades", total_trades)
        with metric_col3:
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            st.metric("Win Rate", f"{win_rate:.1f}%")
        with metric_col4:
            st.metric("Total P&L", f"£{total_pnl:.2f}")
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📈 Performance Charts", "📋 Recent Activity", "🏆 Trade Analysis"])
        
        with tab1:
            # Equity curve - main P&L line graph
            st.markdown("#### Portfolio Equity Over Time")
            equity_data = df[['timestamp', 'equity']].drop_duplicates(subset=['timestamp']).sort_values('timestamp')
            
            if len(equity_data) > 1:
                fig_equity = px.line(
                    equity_data,
                    x='timestamp',
                    y='equity',
                    title="Portfolio Equity Timeline",
                    labels={'equity': 'Equity (£)', 'timestamp': 'Time'}
                )
                fig_equity.update_traces(line_color='#00ff88', line_width=3)
                fig_equity.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
                    yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)')
                )
                st.plotly_chart(fig_equity, use_container_width=True)
            
            # P&L distribution
            pnl_data = df[df['pnl'] != 0]['pnl']
            if not pnl_data.empty and len(pnl_data) > 5:
                st.markdown("#### P&L Distribution")
                fig_pnl = px.histogram(
                    pnl_data,
                    title="Trade P&L Distribution",
                    labels={'value': 'P&L (£)', 'count': 'Number of Trades'},
                    nbins=min(20, len(pnl_data))
                )
                fig_pnl.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pnl, use_container_width=True)
        
        with tab2:
            st.markdown("#### Recent Trading Activity")
            
            # Filters
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                symbol_filter = st.multiselect(
                    "Filter by Symbol",
                    options=sorted(df['symbol'].unique()),
                    key="symbol_filter_v21"
                )
            with filter_col2:
                action_filter = st.multiselect(
                    "Filter by Action",
                    options=sorted(df['action'].unique()),
                    key="action_filter_v21"
                )
            
            # Apply filters
            filtered_df = df.copy()
            if symbol_filter:
                filtered_df = filtered_df[filtered_df['symbol'].isin(symbol_filter)]
            if action_filter:
                filtered_df = filtered_df[filtered_df['action'].isin(action_filter)]
            
            # Display recent activity with clean formatting
            recent_data = filtered_df.tail(50).sort_values('timestamp', ascending=False)
            
            if not recent_data.empty:
                display_df = recent_data[['timestamp', 'symbol', 'action', 'price', 'pnl', 'equity']].copy()
                display_df['timestamp'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
                display_df['price'] = display_df['price'].round(6)
                display_df['pnl'] = display_df['pnl'].round(2)
                display_df['equity'] = display_df['equity'].round(2)
                
                # Color code P&L
                def color_pnl(val):
                    if val > 0:
                        return 'color: #00ff88'
                    elif val < 0:
                        return 'color: #ff4444'
                    return ''
                
                styled_df = display_df.style.applymap(color_pnl, subset=['pnl'])
                st.dataframe(styled_df, use_container_width=True, height=400)
            else:
                st.info("No activity matching current filters")
        
        with tab3:
            st.markdown("#### Trade Performance Analysis")
            
            # Top performers
            perf_col1, perf_col2 = st.columns(2)
            
            with perf_col1:
                st.markdown("**🟢 Best Trades**")
                best_trades = df[(df['pnl'] > 0) & (df['action'].str.contains('CLOSE', na=False))]
                if not best_trades.empty:
                    top_5 = best_trades.nlargest(5, 'pnl')[['symbol', 'pnl', 'close_reason', 'timestamp']]
                    top_5['pnl'] = top_5['pnl'].round(2)
                    top_5['timestamp'] = top_5['timestamp'].dt.strftime('%m/%d %H:%M')
                    st.dataframe(top_5, hide_index=True)
                else:
                    st.info("No profitable trades yet")
            
            with perf_col2:
                st.markdown("**🔴 Worst Trades**")
                worst_trades = df[(df['pnl'] < 0) & (df['action'].str.contains('CLOSE', na=False))]
                if not worst_trades.empty:
                    bottom_5 = worst_trades.nsmallest(5, 'pnl')[['symbol', 'pnl', 'close_reason', 'timestamp']]
                    bottom_5['pnl'] = bottom_5['pnl'].round(2)
                    bottom_5['timestamp'] = bottom_5['timestamp'].dt.strftime('%m/%d %H:%M')
                    st.dataframe(bottom_5, hide_index=True)
                else:
                    st.info("No losing trades yet")
            
            # Symbol performance summary
            if total_trades > 0:
                st.markdown("**📈 Symbol Performance Summary**")
                symbol_stats = df[df['pnl'] != 0].groupby('symbol').agg({
                    'pnl': ['sum', 'count', 'mean']
                }).round(2)
                
                symbol_stats.columns = ['Total P&L', 'Trade Count', 'Avg P&L']
                symbol_stats = symbol_stats.sort_values('Total P&L', ascending=False).head(10)
                
                st.dataframe(symbol_stats, use_container_width=True)

# System status footer
st.markdown("---")
status_col1, status_col2, status_col3 = st.columns(3)

with status_col1:
    if bot_status["running"]:
        st.success(f"🟢 System Online | PID: {bot_status['pid']}")
    else:
        st.error("🔴 System Offline")

with status_col2:
    if not df.empty:
        last_update = df['timestamp'].max()
        st.info(f"📊 Last Update: {last_update.strftime('%H:%M:%S')}")
    else:
        st.info("📊 Awaiting Data")

with status_col3:
    st.info(f"🕒 Page Refresh: {datetime.now().strftime('%H:%M:%S')}")

# Auto-refresh mechanism (every 30 seconds)
current_time = time.time()
if current_time - st.session_state.last_refresh > 30:
    st.session_state.last_refresh = current_time
    st.rerun()

# Progress bar for next refresh
time_since_refresh = current_time - st.session_state.last_refresh
refresh_progress = min(time_since_refresh / 30, 1.0)
st.progress(refresh_progress)

# Export functionality
if not df.empty:
    with st.expander("📤 Export Data"):
        st.markdown("Download your trading data for external analysis")
        
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"spiralbot_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="export_csv_v21"
        )