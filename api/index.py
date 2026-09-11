import sys
import os

# প্রজেক্টের রুট ডিরেক্টরি sys.path-এ যোগ করো
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# app.py থেকে Flask app ইমপোর্ট করো
from app import app
