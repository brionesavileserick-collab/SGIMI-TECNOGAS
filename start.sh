#!/bin/bash
# Quick Start Script for SGIMI TECNOGAS
# This script sets up and runs the system on Linux/Mac

echo "========================================="
echo "SGIMI TECNOGAS - Quick Start Script"
echo "========================================="

# Check Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Run application
echo ""
echo "Starting SGIMI TECNOGAS..."
echo "On first use, the application will ask you to create the initial user."
echo ""
python main.py
