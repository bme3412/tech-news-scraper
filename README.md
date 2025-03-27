# Tech News Scraper

A comprehensive web scraping system for collecting technology, business, and investing news from major sources across North America, Europe, and Asia. The system includes multiple specialized scrapers for different regions and supports article clustering and summarization.

## Overview

The tech-scraper system consists of several components:

1. **Regional Scrapers**
   - `us-scraper.py`: Scrapes US/North American tech news sources
   - `euro-scraper.py`: Scrapes European tech news sources
   - `asia-scraper.py`: Scrapes Asian tech news sources
   - `scrape-articles.py`: Unified scraper for all regions

2. **Article Processing**
   - `article-clustering-tool.py`: Clusters similar articles using NLP techniques
   - `tech-sql-summary.py`: Generates comprehensive summaries from scraped articles

## Features

- **Multi-Region Support**: Scrapes news from major sources across North America, Europe, and Asia
- **Source Diversity**: Covers technology, business, and investing news
- **Robust Error Handling**: Implements retry mechanisms and error logging
- **Anti-Detection Measures**: Uses rotating user agents and randomized delays
- **Data Organization**: Saves articles in structured JSON format
- **Article Clustering**: Groups similar articles using NLP techniques
- **Summary Generation**: Creates comprehensive summaries using OpenAI's GPT models

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd tech-scraper
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Scraping

1. **US News Scraping**:
```bash
python us-scraper.py --output US_tech_news_YYYYMMDD --category technology
```

2. **European News Scraping**:
```bash
python euro-scraper.py --output Europe_tech_news_YYYYMMDD.json --category technology
```

3. **Asian News Scraping**:
```bash
python asia-scraper.py --output Asia_tech_news_YYYYMMDD.json --category technology
```

4. **Unified Scraping**:
```bash
python scrape-articles.py --output articles_YYYYMMDD.json --region north_america --category technology
```

### Command Line Arguments

- `--output`: Specify output file/directory path
- `--retry`: Number of retry attempts (default: 3)
- `--sources`: Limit number of sources to scrape
- `--articles`: Limit articles per source
- `--category`: Filter by category (technology, business, investing)
- `--region`: Filter by region (north_america, europe, asia)
- `--openai-key`: OpenAI API key for article summarization

### Article Clustering

To cluster similar articles:
```bash
python article-clustering-tool.py --input scraped_data/articles.json --output clustered_articles
```

### Summary Generation

To generate summaries from scraped articles:
```bash
python tech-sql-summary.py --date YYYY-MM-DD --days-range 2 --output tech_news_summaries
```

## Data Structure

### Scraped Article Format
```json
{
    "source": "Source Name",
    "category": "technology/business/investing",
    "region": "north_america/europe/asia",
    "url": "article_url",
    "title": "article_title",
    "author": "author_name",
    "description": "article_description",
    "content": "article_content",
    "date": "publication_date",
    "content_length": 1234,
    "scraped_at": "timestamp"
}
```

## Logging

The system maintains detailed logs for:
- Scraping operations (`us_scraper.log`, `europe_scraper.log`, `asia_scraper.log`)
- Article clustering (`article_clustering.log`)
- Summary generation (`tech_news_summary.log`)

## Error Handling

The system implements several error handling mechanisms:
- Retry logic for failed requests
- Graceful handling of missing content
- Detailed error logging
- Automatic saving of partial results

## Anti-Detection Measures

To avoid being blocked by websites:
- Rotating user agents
- Randomized delays between requests
- Respectful scraping practices
- Error handling and retries

## Dependencies

- Python 3.7+
- BeautifulSoup4
- Requests
- OpenAI API
- SQLite3
- NLTK
- scikit-learn
- pandas

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
