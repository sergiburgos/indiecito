import os
from main import app
# Import rag_system to ensure it's included in Vercel deployment
import rag_system

# This is the entry point for Vercel.
# It assumes your FastAPI app instance is named 'app' in main.py
# Vercel will look for 'app' or 'api'
