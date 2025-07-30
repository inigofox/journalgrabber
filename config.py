"""
Configuration settings for Journal Grabber application
"""

import os

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///journalgrabber.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Download settings
    DEFAULT_DOWNLOAD_PATH = os.environ.get('DOWNLOAD_PATH', '/app/downloads')
    MAX_DOWNLOAD_SIZE_MB = int(os.environ.get('MAX_DOWNLOAD_SIZE_MB', '100'))
    
    # ArXiv API settings
    ARXIV_API_DELAY = float(os.environ.get('ARXIV_API_DELAY', '3.0'))  # Seconds between requests
    DEFAULT_MAX_RESULTS = int(os.environ.get('DEFAULT_MAX_RESULTS', '50'))
    DEFAULT_SEARCH_DAYS = int(os.environ.get('DEFAULT_SEARCH_DAYS', '7'))
    
    # Scheduler settings
    MIN_FREQUENCY_HOURS = int(os.environ.get('MIN_FREQUENCY_HOURS', '1'))
    MAX_FREQUENCY_HOURS = int(os.environ.get('MAX_FREQUENCY_HOURS', '168'))  # 1 week
    
    # Security settings
    ALLOWED_EXTENSIONS = {'pdf'}
    MAX_CONTENT_LENGTH = MAX_DOWNLOAD_SIZE_MB * 1024 * 1024
