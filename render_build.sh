#!/bin/bash

set -e

echo "Running build script for Render..."

pip install -r requirements.txt

export FLASK_APP=microblog.py
flask db upgrade

echo "Build completed successfully!"