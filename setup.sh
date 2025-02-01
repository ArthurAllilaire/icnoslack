#!/bin/bash

# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install Flask
pip install Flask

echo "Flask has been installed in the virtual environment."
