import sys
import os

# Root directory যোগ করো
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# app.py থেকে Flask app ইমপোর্ট করো
from app import app

# Vercel handler
handler = app
