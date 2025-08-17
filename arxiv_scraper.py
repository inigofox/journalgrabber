"""
ArXiv Scraper Module
Handles searching and downloading articles from arXiv
"""

import os
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, quote
import time
import re
from datetime import datetime, timedelta

class ArxivScraper:
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        self.download_url = "https://arxiv.org/pdf/"
        
    def search_articles(self, topics, max_results=50, days_back=30):
        """
        Search for articles on arXiv based on topics
        
        Args:
            topics (list): List of search terms/topics
            max_results (int): Maximum number of results to return
            days_back (int): How many days back to search (default 30 for better results)
            
        Returns:
            list: List of article dictionaries
        """
        
        # Separate category codes from keyword terms
        category_terms = []
        keyword_terms = []
        
        for topic in topics:
            # Check if it looks like a category code (contains dot or specific prefixes)
            if ('.' in topic and any(topic.startswith(prefix) for prefix in ['cs.', 'math.', 'physics.', 'astro-ph', 'cond-mat', 'quant-ph', 'stat.'])) or topic in ['cs', 'math', 'physics']:
                category_terms.append(topic)
            else:
                keyword_terms.append(topic)
        
        # Build search query parts
        search_parts = []
        
        # Add category search
        if category_terms:
            cat_query = " OR ".join([f'cat:"{cat}"' for cat in category_terms])
            search_parts.append(f'({cat_query})')
        
        # Add keyword search (in title and abstract)
        if keyword_terms:
            for keyword in keyword_terms:
                keyword_query = f'(ti:"{keyword}" OR abs:"{keyword}")'
                search_parts.append(keyword_query)
        
        # Combine all search parts
        if search_parts:
            query = " OR ".join(search_parts)
        else:
            query = "all"  # Fallback to search all if no valid terms
        
        # Add date filter for recent articles (increased to 30 days for better results)
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
        query += f' AND submittedDate:[{start_date}* TO *]'
        
        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        url = f"{self.base_url}?{urlencode(params)}"
        
        print(f"ArXiv search URL: {url}")
        print(f"Search query: {query}")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            print(f"ArXiv response status: {response.status_code}")
            print(f"Response content length: {len(response.content)}")
            
            articles = self._parse_arxiv_response(response.content)
            print(f"Parsed {len(articles)} articles from response")
            
            # If no articles found with date filter, try without it
            if len(articles) == 0 and days_back < 365:
                print("No results with date filter, trying without date restriction...")
                
                # Remove date filter
                query_no_date = query.split(' AND submittedDate:')[0]
                params_no_date = params.copy()
                params_no_date['search_query'] = query_no_date
                params_no_date['max_results'] = min(max_results, 20)  # Reduce results for broader search
                
                url_no_date = f"{self.base_url}?{urlencode(params_no_date)}"
                print(f"Trying without date filter: {url_no_date}")
                
                response_no_date = requests.get(url_no_date, timeout=30)
                response_no_date.raise_for_status()
                
                articles = self._parse_arxiv_response(response_no_date.content)
                print(f"Found {len(articles)} articles without date filter")
            
            return articles
            
        except requests.exceptions.RequestException as e:
            print(f"Error searching arXiv: {e}")
            return []
    
    def _parse_arxiv_response(self, xml_content):
        """Parse XML response from arXiv API"""
        articles = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Define namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                  'arxiv': 'http://arxiv.org/schemas/atom'}
            
            entries = root.findall('atom:entry', ns)
            
            for entry in entries:
                article = {}
                
                # Extract ID
                id_elem = entry.find('atom:id', ns)
                if id_elem is not None:
                    article['id'] = id_elem.text.split('/')[-1]
                
                # Extract title
                title_elem = entry.find('atom:title', ns)
                if title_elem is not None:
                    article['title'] = title_elem.text.strip().replace('\n', ' ')
                
                # Extract summary/abstract
                summary_elem = entry.find('atom:summary', ns)
                if summary_elem is not None:
                    article['summary'] = summary_elem.text.strip().replace('\n', ' ')
                
                # Extract authors
                authors = []
                author_elems = entry.findall('atom:author', ns)
                for author_elem in author_elems:
                    name_elem = author_elem.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                article['authors'] = authors
                
                # Extract categories
                categories = []
                category_elems = entry.findall('atom:category', ns)
                for cat_elem in category_elems:
                    term = cat_elem.get('term')
                    if term:
                        categories.append(term)
                article['categories'] = categories
                
                # Extract published date
                published_elem = entry.find('atom:published', ns)
                if published_elem is not None:
                    article['published'] = published_elem.text
                
                # Extract updated date
                updated_elem = entry.find('atom:updated', ns)
                if updated_elem is not None:
                    article['updated'] = updated_elem.text
                
                # Extract PDF link
                links = entry.findall('atom:link', ns)
                for link in links:
                    if link.get('type') == 'application/pdf':
                        article['pdf_url'] = link.get('href')
                        break
                
                if 'id' in article:
                    articles.append(article)
                    
        except ET.ParseError as e:
            print(f"Error parsing XML response: {e}")
            
        return articles
    
    def download_article(self, arxiv_id, download_path='/app/downloads'):
        """
        Download a PDF article from arXiv
        
        Args:
            arxiv_id (str): ArXiv ID (e.g., '2301.00001')
            download_path (str): Directory to save the file
            
        Returns:
            str: Path to downloaded file or None if failed
        """
        
        # Ensure download directory exists
        os.makedirs(download_path, exist_ok=True)
        
        # Clean the arXiv ID (remove version if present)
        clean_id = arxiv_id.split('v')[0]
        
        # Construct download URL
        pdf_url = f"{self.download_url}{clean_id}.pdf"
        
        # Create filename
        filename = f"{clean_id}.pdf"
        filepath = os.path.join(download_path, filename)
        
        # Check if file already exists
        if os.path.exists(filepath):
            print(f"File {filename} already exists")
            return filepath
        
        try:
            print(f"Downloading {arxiv_id}...")
            
            response = requests.get(pdf_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Check if response is actually a PDF
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' not in content_type:
                print(f"Warning: Response may not be a PDF. Content-Type: {content_type}")
            
            # Write file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"Successfully downloaded {filename}")
            return filepath
            
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {arxiv_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error downloading {arxiv_id}: {e}")
            return None
    
    def get_article_info(self, arxiv_id):
        """
        Get detailed information about a specific arXiv article
        
        Args:
            arxiv_id (str): ArXiv ID
            
        Returns:
            dict: Article information or None if not found
        """
        
        params = {
            'id_list': arxiv_id,
            'max_results': 1
        }
        
        url = f"{self.base_url}?{urlencode(params)}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            articles = self._parse_arxiv_response(response.content)
            return articles[0] if articles else None
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching article info for {arxiv_id}: {e}")
            return None
    
    def search_by_category(self, category, max_results=50, days_back=7):
        """
        Search for articles in a specific arXiv category
        
        Args:
            category (str): arXiv category (e.g., 'cs.AI', 'physics.gen-ph')
            max_results (int): Maximum number of results
            days_back (int): How many days back to search
            
        Returns:
            list: List of article dictionaries
        """
        
        # Add date filter
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
        query = f'cat:{category} AND submittedDate:[{start_date}* TO *]'
        
        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        url = f"{self.base_url}?{urlencode(params)}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            return self._parse_arxiv_response(response.content)
            
        except requests.exceptions.RequestException as e:
            print(f"Error searching category {category}: {e}")
            return []

    def get_available_categories(self):
        """
        Return a list of common arXiv categories
        """
        return {
            'Computer Science': [
                'cs.AI', 'cs.CL', 'cs.CV', 'cs.LG', 'cs.NE', 'cs.RO',
                'cs.CR', 'cs.DB', 'cs.DS', 'cs.IR', 'cs.IT', 'cs.NI'
            ],
            'Physics': [
                'physics.gen-ph', 'physics.class-ph', 'physics.comp-ph',
                'physics.data-an', 'physics.flu-dyn', 'physics.med-ph'
            ],
            'Mathematics': [
                'math.AG', 'math.AT', 'math.CA', 'math.CO', 'math.CT',
                'math.DG', 'math.DS', 'math.FA', 'math.GM', 'math.GN'
            ],
            'Biology': [
                'q-bio.BM', 'q-bio.CB', 'q-bio.GN', 'q-bio.MN',
                'q-bio.NC', 'q-bio.OT', 'q-bio.PE', 'q-bio.QM'
            ],
            'Economics': [
                'econ.EM', 'econ.GN', 'econ.TH'
            ],
            'Statistics': [
                'stat.AP', 'stat.CO', 'stat.ME', 'stat.ML', 'stat.TH'
            ]
        }
