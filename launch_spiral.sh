#!/bin/bash
# SpiralBot v2.1 Launch Script - UK Banking Compliant
# ===================================================

set -e  # Exit on any error

# Dynamic base directory detection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"

# Color codes for clean output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${BLUE}🌀 SpiralBot v2.1 Launch System${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo -e "UK Banking Compliant | CoinGecko Only | Simulation Mode"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Parse command line arguments
DEBUG_MODE=false
TEST_MODE=false
HELP_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            DEBUG_MODE=true
            shift
            ;;
        --test)
            TEST_MODE=true
            shift
            ;;
        --help|-h)
            HELP_MODE=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Show help if requested
if [ "$HELP_MODE" = true ]; then
    print_header
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --debug    Enable debug logging and verbose output"
    echo "  --test     Run in diagnostic test mode"
    echo "  --help     Show this help message"
    echo ""
    echo "Launch Modes:"
    echo "  1) Dashboard Only (monitoring interface)"
    echo "  2) Bot Only (background simulation)"
    echo "  3) Dashboard + Bot (recommended full system)"
    echo ""
    echo "UK Banking Compliance:"
    echo "  • Only CoinGecko data source permitted"
    echo "  • All trading is simulation only"
    echo "  • No live exchange API integration"
    echo ""
    exit 0
fi

print_header

print_info "Base directory: $BASE_DIR"

if [ "$DEBUG_MODE" = true ]; then
    print_warning "Debug mode enabled"
    set -x  # Enable debug output
fi

if [ "$TEST_MODE" = true ]; then
    print_warning "Test mode enabled - running diagnostics"
fi

echo ""

# System checks
print_info "Performing system checks..."

# Check Python installation
if ! command -v python3 &> /dev/null; then
    print_error "Python3 is not installed or not in PATH"
    print_info "Please install Python 3.7+ to continue"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
print_success "Python3 found: $PYTHON_VERSION"

# Check virtual environment
VENV_DIR="$BASE_DIR/spiral-env"
if [ -d "$VENV_DIR" ]; then
    print_success "Virtual environment found"
    
    # Activate virtual environment
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source "$VENV_DIR/Scripts/activate"
    else
        source "$VENV_DIR/bin/activate"
    fi
    print_success "Virtual environment activated"
else
    print_warning "No virtual environment detected"
    print_info "Creating virtual environment..."
    
    python3 -m venv "$VENV_DIR"
    if [ $? -eq 0 ]; then
        print_success "Virtual environment created"
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
            source "$VENV_DIR/Scripts/activate"
        else
            source "$VENV_DIR/bin/activate"
        fi
        print_success "Virtual environment activated"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
fi

# Check and install dependencies
print_info "Checking dependencies..."

REQUIREMENTS_FILE="$BASE_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    print_error "requirements.txt not found"
    exit 1
fi

# Check if core packages are installed
MISSING_PACKAGES=()
for package in "streamlit" "pandas" "plotly" "requests" "psutil"; do
    if ! python3 -c "import $package" 2>/dev/null; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
    print_warning "Missing packages: ${MISSING_PACKAGES[*]}"
    print_info "Installing requirements..."
    
    pip install -r "$REQUIREMENTS_FILE" --quiet
    if [ $? -eq 0 ]; then
        print_success "Dependencies installed successfully"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi
else
    print_success "All dependencies satisfied"
fi

# Test mode - run diagnostics and exit
if [ "$TEST_MODE" = true ]; then
    print_info "Running diagnostic tests..."
    
    # Test bot syntax
    print_info "Testing bot syntax..."
    if python3 -m py_compile "$BASE_DIR/bue_flashbot_virtual.py"; then
        print_success "Bot syntax check passed"
    else
        print_error "Bot syntax check failed"
        exit 1
    fi
    
    # Test dashboard syntax
    print_info "Testing dashboard syntax..."
    if python3 -m py_compile "$BASE_DIR/sb_dashboard.py"; then
        print_success "Dashboard syntax check passed"
    else
        print_error "Dashboard syntax check failed"
        exit 1
    fi
    
    # Test API connectivity
    print_info "Testing CoinGecko API connectivity..."
    if curl -s --head --fail --connect-timeout 10 "https://api.coingecko.com/api/v3/ping" > /dev/null; then
        print_success "CoinGecko API connectivity verified"
    else
        print_warning "CoinGecko API connectivity issues detected"
    fi
    
    # Test file permissions
    print_info "Testing file permissions..."
    if touch "$BASE_DIR/test_permissions.tmp" 2>/dev/null; then
        rm -f "$BASE_DIR/test_permissions.tmp"
        print_success "File write permissions verified"
    else
        print_error "File write permissions denied"
        exit 1
    fi
    
    print_success "All diagnostic tests passed!"
    print_info "System ready for operation"
    exit 0
fi

# Cleanup old files
print_info "Cleaning up old session files..."
rm -f "$BASE_DIR/bot.log" "$BASE_DIR/dashboard.log" "$BASE_DIR/bue_log.csv"
print_success "Cleanup complete"

# Check for existing processes
print_info "Checking for existing bot processes..."
if pgrep -f "bue_flashbot_virtual.py" > /dev/null; then
    print_warning "Existing bot process detected"
    echo ""
    echo "Options:"
    echo "1) Kill existing process and continue"
    echo "2) Exit and manage manually"
    echo ""
    read -p "Enter choice (1-2): " kill_choice
    
    case $kill_choice in
        1)
            pkill -f "bue_flashbot_virtual.py"
            sleep 2
            print_success "Existing process terminated"
            ;;
        2)
            print_info "Launch cancelled. Manage existing processes manually."
            exit 0
            ;;
        *)
            print_error "Invalid choice. Exiting."
            exit 1
            ;;
    esac
fi

# Test API connectivity
print_info "Testing CoinGecko API connectivity..."
if curl -s --head --fail --connect-timeout 10 "https://api.coingecko.com/api/v3/ping" > /dev/null; then
    print_success "CoinGecko API accessible"
else
    print_warning "CoinGecko API connectivity issues"
    print_info "Continuing anyway - bot will handle API errors gracefully"
fi

echo ""
print_info "🚀 Ready to launch SpiralBot v2.1"
echo ""

# Launch mode selection
echo "Select launch mode:"
echo ""
echo "1) 🖥️  Dashboard Only (monitoring interface)"
echo "2) 🤖 Bot Only (background simulation)"
echo "3) 🚀 Dashboard + Bot (recommended)"
echo ""

read -p "Enter choice (1-3): " launch_choice

case $launch_choice in
    1)
        echo ""
        print_info "Starting dashboard only..."
        print_success "Dashboard will be available at: http://localhost:8501"
        print_info "Use the dashboard to start/stop the bot as needed"
        echo ""
        
        streamlit run "$BASE_DIR/sb_dashboard.py" --server.port 8501 --server.headless true
        ;;
        
    2)
        echo ""
        print_info "Starting bot in simulation mode..."
        
        if [ "$DEBUG_MODE" = true ]; then
            python3 "$BASE_DIR/bue_flashbot_virtual.py" --debug
        else
            python3 "$BASE_DIR/bue_flashbot_virtual.py"
        fi
        ;;
        
    3)
        echo ""
        print_info "Starting full system (Dashboard + Bot)..."
        
        # Start bot in background
        if [ "$DEBUG_MODE" = true ]; then
            nohup python3 "$BASE_DIR/bue_flashbot_virtual.py" --debug > "$BASE_DIR/bot.log" 2>&1 &
        else
            nohup python3 "$BASE_DIR/bue_flashbot_virtual.py" > "$BASE_DIR/bot.log" 2>&1 &
        fi
        
        BOT_PID=$!
        sleep 3
        
        # Verify bot started
        if ps -p $BOT_PID > /dev/null; then
            print_success "Bot started successfully (PID: $BOT_PID)"
        else
            print_error "Bot failed to start"
            print_info "Check bot.log for error details"
            exit 1
        fi
        
        print_success "Dashboard starting at: http://localhost:8501"
        print_info "Bot running in background (PID: $BOT_PID)"
        print_info "Press Ctrl+C to stop both services"
        echo ""
        
        # Function to cleanup on exit
        cleanup() {
            echo ""
            print_info "Shutting down services..."
            
            # Stop streamlit
            if [ ! -z "$STREAMLIT_PID" ]; then
                kill $STREAMLIT_PID 2>/dev/null || true
            fi
            
            # Stop bot gracefully
            if ps -p $BOT_PID > /dev/null; then
                kill -TERM $BOT_PID
                sleep 5
                
                # Force kill if still running
                if ps -p $BOT_PID > /dev/null; then
                    kill -KILL $BOT_PID
                fi
            fi
            
            print_success "Services stopped"
            exit 0
        }
        
        # Set trap for cleanup
        trap cleanup SIGINT SIGTERM
        
        # Start dashboard
        streamlit run "$BASE_DIR/sb_dashboard.py" --server.port 8501 --server.headless true &
        STREAMLIT_PID=$!
        
        # Wait for either process to exit
        wait $STREAMLIT_PID
        cleanup
        ;;
        
    *)
        print_error "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
print_success "SpiralBot v2.1 launch complete!"

if [ "$DEBUG_MODE" = true ]; then
    echo ""
    print_info "Debug files available:"
    print_info "• Bot log: $BASE_DIR/bot.log"
    print_info "• Dashboard log: $BASE_DIR/dashboard.log"
    print_info "• Trading log: $BASE_DIR/bue_log.csv"
fi