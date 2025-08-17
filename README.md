# Journal Grabber

A Podman-based Python application for scraping and downloading journal articles from arXiv. The application provides a web interface for managing search preferences and automatically downloads articles based on your topics of interest.

## Features

- 🔍 **Smart Article Discovery**: Search arXiv by categories, keywords, and authors
- 📅 **Flexible Scheduling**: Configure how often to check for new articles (daily, weekly, monthly)
- 👤 **User Profiles**: Create multiple profiles with different preferences
- 📱 **Web Interface**: Easy-to-use web UI for managing preferences
- 🐳 **Containerized**: Runs in Podman containers for easy deployment
- 📂 **Organized Downloads**: Articles saved with proper metadata and organization
- ⏰ **Background Processing**: Continuous monitoring with configurable intervals

## Prerequisites

- Podman (or Docker)
- Python 3.9+ (for development)

## Quick Start with Podman

### 1. Build and Run with Podman Compose

```bash
# Clone the repository
git clone https://github.com/inigofox/journalgrabber.git
cd journalgrabber

# Build and start the application
podman-compose up --build

# Or run in detached mode
podman-compose up -d --build
```

### 2. Access the Web Interface

Open your browser and navigate to: `http://localhost:5000`

### 3. Create Your First Profile

1. Click "Manage Profiles" in the web interface
2. Create a new profile with your preferences
3. Configure your search criteria and download settings
4. Save and activate your profile

## Configuration Options

### arXiv Categories

You can specify any combination of these arXiv categories:

**Computer Science:**
- `cs.AI` - Artificial Intelligence
- `cs.CV` - Computer Vision and Pattern Recognition
- `cs.LG` - Machine Learning
- `cs.CL` - Computation and Language
- `cs.CR` - Cryptography and Security
- `cs.DC` - Distributed, Parallel, and Cluster Computing
- `cs.DS` - Data Structures and Algorithms

**Physics:**
- `physics.comp-ph` - Computational Physics
- `quant-ph` - Quantum Physics
- `astro-ph` - Astrophysics
- `cond-mat` - Condensed Matter

**Mathematics:**
- `math.NA` - Numerical Analysis
- `math.OC` - Optimization and Control
- `stat.ML` - Machine Learning (Statistics)

### Search Parameters

When creating a profile, you can configure:

- **Categories**: Select from arXiv subject classifications
- **Keywords**: Specific terms to search for in titles/abstracts
- **Authors**: Specific authors to follow
- **Max Results**: Maximum papers to download per search (1-100)
- **Update Frequency**: How often to check for new papers
  - `daily` - Every 24 hours
  - `weekly` - Every 7 days  
  - `monthly` - Every 30 days
- **Download Path**: Where to save downloaded papers (inside container)

### Example Profile Configuration

```json
{
  "name": "AI Research",
  "categories": ["cs.AI", "cs.LG", "cs.CV"],
  "keywords": ["neural networks", "deep learning", "computer vision"],
  "authors": ["Geoffrey Hinton", "Yann LeCun"],
  "max_results": 20,
  "update_frequency": "weekly",
  "download_path": "/app/downloads/ai_papers"
}
```

## Manual Usage (Development)

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run the Application

```bash
# Start the web application
python app.py

# Or run a one-time scrape
python arxiv_scraper.py --categories "cs.AI,cs.LG" --keywords "neural networks" --max-results 10
```

## Docker Alternative

If you prefer Docker over Podman:

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run manually
docker build -t journalgrabber .
docker run -p 5000:5000 -v $(pwd)/downloads:/app/downloads journalgrabber
```

## File Structure

```
journalgrabber/
├── app.py                 # Flask web application
├── arxiv_scraper.py       # Core scraping logic
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container configuration
├── docker-compose.yml   # Multi-container setup
├── run.sh              # Container entrypoint script
├── templates/          # HTML templates
│   ├── base.html
│   ├── index.html
│   └── profiles.html
└── downloads/          # Downloaded papers (created automatically)
```

## API Usage

The application also provides a simple REST API:

### Get all profiles
```bash
curl http://localhost:5000/api/profiles
```

### Create a new profile
```bash
curl -X POST http://localhost:5000/api/profiles \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ML Papers",
    "categories": ["cs.LG"],
    "keywords": ["machine learning"],
    "max_results": 10,
    "update_frequency": "daily"
  }'
```

### Trigger manual scrape for a profile
```bash
curl -X POST http://localhost:5000/api/scrape/profile_id
```

## Customization

### Adding New Sources

To add journal sources beyond arXiv:

1. Create a new scraper module following the pattern in `arxiv_scraper.py`
2. Add source configuration to `config.py`
3. Update the web interface to include the new source options

### Custom Download Organization

Modify the `download_path` logic in `arxiv_scraper.py` to change how papers are organized:

- By date: `/downloads/2025/01/`
- By category: `/downloads/cs.AI/`
- By author: `/downloads/authors/lastname/`

## Troubleshooting

### Container Issues

```bash
# Check container logs
podman logs journalgrabber

# Restart the application
podman-compose restart

# Rebuild if needed
podman-compose down
podman-compose up --build
```

### Permission Issues

If you encounter permission issues with downloads:

```bash
# Fix permissions on download directory
chmod 755 downloads
```

### Network Issues

If arXiv requests are failing:
- Check your internet connection
- Verify arXiv is accessible: `curl https://arxiv.org/`
- Review rate limiting in `config.py`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- arXiv for providing open access to research papers
- Flask for the web framework
- The scientific community for making research accessible
