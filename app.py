#!/usr/bin/env python3
"""
Journal Grabber - ArXiv Article Scraper and Downloader
Main Flask application for the web interface
"""

import os
import json
import schedule
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from arxiv_scraper import ArxivScraper
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

# Database Models
class SearchProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    topics = db.Column(db.Text, nullable=False)  # JSON string of topics
    frequency_hours = db.Column(db.Integer, default=24)
    download_path = db.Column(db.String(500), default='/app/downloads')
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DownloadedArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    arxiv_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    authors = db.Column(db.Text)
    abstract = db.Column(db.Text)
    subjects = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    profile_id = db.Column(db.Integer, db.ForeignKey('search_profile.id'))
    downloaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize scraper
scraper = ArxivScraper()

@app.route('/')
def index():
    """Main dashboard page"""
    profiles = SearchProfile.query.all()
    recent_downloads = DownloadedArticle.query.order_by(DownloadedArticle.downloaded_at.desc()).limit(10).all()
    return render_template('index.html', profiles=profiles, recent_downloads=recent_downloads)

@app.route('/profiles')
def profiles():
    """Manage search profiles"""
    profiles = SearchProfile.query.all()
    return render_template('profiles.html', profiles=profiles)

@app.route('/api/profiles', methods=['GET', 'POST'])
def api_profiles():
    """API endpoint for profile management"""
    if request.method == 'POST':
        data = request.get_json()
        
        profile = SearchProfile(
            name=data['name'],
            topics=json.dumps(data['topics']),
            frequency_hours=data.get('frequency_hours', 24),
            download_path=data.get('download_path', '/app/downloads'),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(profile)
        db.session.commit()
        
        # Schedule the new profile
        schedule_profile(profile)
        
        return jsonify({'success': True, 'id': profile.id})
    
    else:
        profiles = SearchProfile.query.all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'topics': json.loads(p.topics),
            'frequency_hours': p.frequency_hours,
            'download_path': p.download_path,
            'is_active': p.is_active,
            'last_run': p.last_run.isoformat() if p.last_run else None
        } for p in profiles])

@app.route('/api/profiles/<int:profile_id>', methods=['PUT', 'DELETE'])
def api_profile_detail(profile_id):
    """API endpoint for individual profile management"""
    profile = SearchProfile.query.get_or_404(profile_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        profile.name = data.get('name', profile.name)
        profile.topics = json.dumps(data.get('topics', json.loads(profile.topics)))
        profile.frequency_hours = data.get('frequency_hours', profile.frequency_hours)
        profile.download_path = data.get('download_path', profile.download_path)
        profile.is_active = data.get('is_active', profile.is_active)
        
        db.session.commit()
        
        # Reschedule the profile
        schedule_profile(profile)
        
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        db.session.delete(profile)
        db.session.commit()
        return jsonify({'success': True})

@app.route('/api/run-profile/<int:profile_id>', methods=['POST'])
def run_profile_now(profile_id):
    """Manually trigger a profile run"""
    profile = SearchProfile.query.get_or_404(profile_id)
    
    try:
        downloaded_count = run_search_profile(profile)
        return jsonify({
            'success': True, 
            'message': f'Downloaded {downloaded_count} new articles'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/downloads')
def api_downloads():
    """API endpoint for downloaded articles"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    downloads = DownloadedArticle.query.order_by(
        DownloadedArticle.downloaded_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'downloads': [{
            'id': d.id,
            'arxiv_id': d.arxiv_id,
            'title': d.title,
            'authors': d.authors,
            'subjects': d.subjects,
            'downloaded_at': d.downloaded_at.isoformat(),
            'file_path': d.file_path
        } for d in downloads.items],
        'total': downloads.total,
        'pages': downloads.pages,
        'current_page': downloads.page
    })

@app.route('/downloads/<path:filename>')
def download_file(filename):
    """Serve downloaded files"""
    return send_from_directory('/app/downloads', filename)

def run_search_profile(profile):
    """Execute a search profile and download new articles"""
    topics = json.loads(profile.topics)
    
    # Search for articles
    articles = scraper.search_articles(topics, max_results=50)
    
    downloaded_count = 0
    
    for article in articles:
        # Check if already downloaded
        existing = DownloadedArticle.query.filter_by(arxiv_id=article['id']).first()
        if existing:
            continue
        
        # Download the article
        file_path = scraper.download_article(article['id'], profile.download_path)
        
        if file_path:
            # Save to database
            downloaded_article = DownloadedArticle(
                arxiv_id=article['id'],
                title=article['title'],
                authors=', '.join(article['authors']),
                abstract=article['summary'],
                subjects=', '.join(article['categories']),
                file_path=file_path,
                profile_id=profile.id
            )
            
            db.session.add(downloaded_article)
            downloaded_count += 1
    
    # Update last run time
    profile.last_run = datetime.utcnow()
    db.session.commit()
    
    return downloaded_count

def schedule_profile(profile):
    """Schedule a profile to run at specified intervals"""
    if not profile.is_active:
        return
    
    job_tag = f"profile_{profile.id}"
    
    # Clear existing schedule for this profile
    schedule.clear(job_tag)
    
    # Schedule new job
    schedule.every(profile.frequency_hours).hours.do(
        run_search_profile, profile
    ).tag(job_tag)

def schedule_runner():
    """Background thread to run scheduled jobs"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    # Create database tables
    with app.app_context():
        db.create_all()
        
        # Schedule existing active profiles
        profiles = SearchProfile.query.filter_by(is_active=True).all()
        for profile in profiles:
            schedule_profile(profile)
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=schedule_runner, daemon=True)
    scheduler_thread.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
