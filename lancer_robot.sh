#!/bin/bash
cd "$(dirname "$0")"
echo "Mise a jour des matchs et des pronostics..."
python3 build_dashboard.py
