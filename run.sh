#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        print_error "Failed to create virtual environment"
        exit 1
    fi
    print_success "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install requirements
print_status "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    print_error "Failed to install dependencies"
    exit 1
fi

print_success "Dependencies installed successfully"

# Check if ffmpeg is installed (required for file-formatter)
if ! command -v ffmpeg &> /dev/null; then
    print_warning "ffmpeg is not installed. The file-formatter tool requires ffmpeg to work properly."
    print_warning "To install ffmpeg:"
    print_warning "  - Ubuntu/Debian: sudo apt install ffmpeg"
    print_warning "  - Arch Linux: sudo pacman -S ffmpeg"
    print_warning "  - macOS: brew install ffmpeg"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found! Please create one with:"
    echo "ADMIN_PASSWORD=your_password"
    echo "SECRET_KEY=your_secret_key"
    echo "GCS_BUCKET_NAME=blog-posts-gazerah"
    echo "GCS_SERVICE_ACCOUNT_KEY_PATH=../credentials.json"
    exit 1
fi

# Check if credentials.json exists
if [ ! -f "credentials.json" ]; then
    print_warning "credentials.json not found in project root"
fi

# Change to blog-site directory
print_status "Starting blog-site server..."
cd blog-site

# Run the blog-site
print_success "Starting FastAPI server on http://localhost:8000"
print_status "Admin panel: http://localhost:8000/admin"
print_status "Press Ctrl+C to stop the server"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
