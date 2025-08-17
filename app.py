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
from zotero_integration import ZoteroIntegration
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

# Add custom Jinja2 filter for JSON parsing
@app.template_filter('from_json')
def from_json_filter(json_str):
    """Convert JSON string to Python object"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []

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

# Initialize scraper and Zotero integration
scraper = ArxivScraper()
zotero = ZoteroIntegration()

@app.route('/')
def index():
    """Main dashboard page"""
    profiles = SearchProfile.query.all()
    recent_downloads = DownloadedArticle.query.order_by(DownloadedArticle.downloaded_at.desc()).limit(10).all()
    
    # Convert profiles to dictionary format for JSON serialization
    profiles_dict = [{
        'id': p.id,
        'name': p.name,
        'topics': json.loads(p.topics),
        'frequency_hours': p.frequency_hours,
        'download_path': p.download_path,
        'is_active': p.is_active,
        'last_run': p.last_run.isoformat() if p.last_run else None
    } for p in profiles]
    
    return render_template('index.html', profiles=profiles, profiles_json=profiles_dict, recent_downloads=recent_downloads)

@app.route('/library')
def library():
    """Library management page"""
    return render_template('library.html')

@app.route('/api/library/articles', methods=['GET'])
def get_library_articles():
    """Get all articles with advanced filtering and organization"""
    # Get filter parameters
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    author = request.args.get('author', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    profile_id = request.args.get('profile_id', '')
    sort_by = request.args.get('sort_by', 'downloaded_at')
    sort_order = request.args.get('sort_order', 'desc')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Build query
    query = DownloadedArticle.query
    
    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            DownloadedArticle.title.ilike(search_filter) |
            DownloadedArticle.authors.ilike(search_filter) |
            DownloadedArticle.abstract.ilike(search_filter) |
            DownloadedArticle.arxiv_id.ilike(search_filter)
        )
    
    if category:
        query = query.filter(DownloadedArticle.subjects.ilike(f"%{category}%"))
    
    if author:
        query = query.filter(DownloadedArticle.authors.ilike(f"%{author}%"))
    
    if profile_id:
        query = query.filter(DownloadedArticle.profile_id == profile_id)
    
    if date_from:
        from datetime import datetime
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(DownloadedArticle.downloaded_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        from datetime import datetime
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(DownloadedArticle.downloaded_at <= date_to_obj)
        except ValueError:
            pass
    
    # Apply sorting
    if sort_by == 'title':
        order_col = DownloadedArticle.title
    elif sort_by == 'authors':
        order_col = DownloadedArticle.authors
    elif sort_by == 'arxiv_id':
        order_col = DownloadedArticle.arxiv_id
    else:
        order_col = DownloadedArticle.downloaded_at
    
    if sort_order == 'asc':
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
    
    # Paginate
    articles = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'articles': [{
            'id': article.id,
            'arxiv_id': article.arxiv_id,
            'title': article.title,
            'authors': article.authors,
            'abstract': article.abstract,
            'subjects': article.subjects,
            'file_path': article.file_path,
            'profile_id': article.profile_id,
            'downloaded_at': article.downloaded_at.isoformat() if article.downloaded_at else None
        } for article in articles.items],
        'total': articles.total,
        'pages': articles.pages,
        'current_page': articles.page,
        'has_next': articles.has_next,
        'has_prev': articles.has_prev
    })

@app.route('/api/library/articles/<int:article_id>', methods=['GET'])
def get_article_by_id(article_id):
    """Get a single article by ID"""
    article = DownloadedArticle.query.get_or_404(article_id)
    
    return jsonify({
        'id': article.id,
        'arxiv_id': article.arxiv_id,
        'title': article.title,
        'authors': article.authors,
        'abstract': article.abstract,
        'subjects': article.subjects,
        'file_path': article.file_path,
        'profile_id': article.profile_id,
        'downloaded_at': article.downloaded_at.isoformat() if article.downloaded_at else None
    })

@app.route('/api/library/stats', methods=['GET'])
def get_library_stats():
    """Get library statistics for dashboard"""
    total_articles = DownloadedArticle.query.count()
    
    # Get category distribution
    categories = {}
    articles = DownloadedArticle.query.all()
    for article in articles:
        if article.subjects:
            for subject in article.subjects.split(','):
                subject = subject.strip()
                categories[subject] = categories.get(subject, 0) + 1
    
    # Get top categories (limit to top 10)
    top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Get articles by profile
    profile_stats = db.session.query(
        SearchProfile.name,
        db.func.count(DownloadedArticle.id).label('count')
    ).outerjoin(DownloadedArticle).group_by(SearchProfile.id, SearchProfile.name).all()
    
    # Get recent activity (articles downloaded in last 30 days)
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_count = DownloadedArticle.query.filter(
        DownloadedArticle.downloaded_at >= thirty_days_ago
    ).count()
    
    return jsonify({
        'total_articles': total_articles,
        'categories': top_categories,
        'profiles': [{'name': name, 'count': count} for name, count in profile_stats],
        'recent_articles': recent_count
    })

@app.route('/api/library/categories', methods=['GET'])
def get_library_categories():
    """Get all unique categories for filtering"""
    categories = set()
    articles = DownloadedArticle.query.all()
    for article in articles:
        if article.subjects:
            for subject in article.subjects.split(','):
                categories.add(subject.strip())
    
    return jsonify(sorted(list(categories)))

@app.route('/api/library/authors', methods=['GET'])
def get_library_authors():
    """Get all unique authors for filtering"""
    authors = set()
    articles = DownloadedArticle.query.all()
    for article in articles:
        if article.authors:
            for author in article.authors.split(','):
                authors.add(author.strip())
    
    return jsonify(sorted(list(authors)))

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

@app.route('/api/zotero/test', methods=['GET'])
def test_zotero_connection():
    """Test Zotero API connection"""
    result = zotero.test_connection()
    return jsonify(result)

@app.route('/api/zotero/send/<int:article_id>', methods=['POST'])
def send_to_zotero(article_id):
    """Send a downloaded article to Zotero"""
    article = DownloadedArticle.query.get_or_404(article_id)
    
    if not zotero.is_configured():
        return jsonify({
            "success": False, 
            "error": "Zotero integration not configured. Please set ZOTERO_API_KEY and ZOTERO_USER_ID environment variables."
        })
    
    # Prepare article data for Zotero
    article_data = {
        'title': article.title,
        'abstract': article.abstract,
        'arxiv_id': article.arxiv_id,
        'authors': article.authors,
        'subjects': article.subjects,
        'published': article.downloaded_at.strftime('%Y-%m-%d') if article.downloaded_at else ''
    }
    
    # Get the full file path
    pdf_path = f"/app/downloads/{article.file_path.split('/')[-1]}" if article.file_path else None
    
    result = zotero.create_arxiv_item(article_data, pdf_path)
    
    if result.get('success'):
        return jsonify({
            "success": True, 
            "message": f"Article '{article.title[:50]}...' sent to Zotero successfully!",
            "zotero_key": result.get('item_key')
        })
    else:
        return jsonify({
            "success": False,
            "error": result.get('error', 'Unknown error occurred')
        })

@app.route('/api/zotero/config', methods=['GET'])
def get_zotero_config():
    """Get Zotero configuration status"""
    return jsonify({
        "configured": zotero.is_configured(),
        "user_id": zotero.user_id if zotero.user_id else None,
        "has_api_key": bool(zotero.api_key),
        "group_id": zotero.group_id if zotero.group_id else None
    })

@app.route('/api/zotero/userinfo', methods=['GET'])
def get_zotero_user_info():
    """Get Zotero user info from API key to find correct user ID"""
    result = zotero.get_user_info()
    return jsonify(result)

def run_search_profile(profile):
    """Execute a search profile and download new articles"""
    topics = json.loads(profile.topics)
    
    print(f"Running profile '{profile.name}' with topics: {topics}")
    
    # Search for articles
    articles = scraper.search_articles(topics, max_results=50)
    
    print(f"Found {len(articles)} articles from search")
    
    downloaded_count = 0
    
    for article in articles:
        print(f"Processing article: {article.get('id', 'Unknown')} - {article.get('title', 'No title')[:100]}...")
        
        # Check if already downloaded
        existing = DownloadedArticle.query.filter_by(arxiv_id=article['id']).first()
        if existing:
            print(f"Article {article['id']} already downloaded, skipping")
            continue
        
        # Download the article
        file_path = scraper.download_article(article['id'], profile.download_path)
        
        print(f"Download result for {article['id']}: {file_path}")
        
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
    # Ensure data directory exists
    os.makedirs('/app/data', exist_ok=True)
    
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
