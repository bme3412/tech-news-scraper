import requests
import json
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime
import os
import re
import logging
from urllib.parse import urlparse, urljoin

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("europe_scraper.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class EuropeNewsScraper:
    def __init__(self, output_file=None, retry_attempts=3):
        # Generate a better filename with Europe and date if not provided
        if output_file is None:
            current_date = datetime.now().strftime('%Y%m%d')
            output_file = f"Europe_tech_news_{current_date}.json"
            
        self.output_file = output_file
        self.retry_attempts = retry_attempts
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        # Rotating user agents to avoid blocking
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        ]
        
        # European News Sources - Keeping only successful sources from the log
        self.sources = [
            {
                'name': 'The Register',
                'url': 'https://www.theregister.com/',
                'article_selector': 'article',
                'title_selector': 'h1',
                'content_selector': '.article_copy',
                'date_selector': 'time',
                'category': 'technology',
                'region': 'europe',
                'country': 'uk'
            },
            {
                'name': 'El País Tecnología',
                'url': 'https://elpais.com/tecnologia/',
                'article_selector': 'article',
                'title_selector': 'h1',
                'content_selector': '.articulo__contenedor',
                'date_selector': 'time',
                'category': 'technology',
                'region': 'europe',
                'country': 'spain'
            },
            {
                'name': 'Financial Times Tech',
                'url': 'https://www.ft.com/technology',
                'article_selector': '.o-teaser',
                'title_selector': 'h1',
                'content_selector': '.article-body',
                'date_selector': 'time',
                'category': 'business',
                'region': 'europe',
                'country': 'uk'
            }
        ]

    def get_article_links(self, source):
        """Get links to articles from a source's homepage"""
        try:
            logger.info(f"Getting article links from {source['name']}")
            
            # Add more robust headers to avoid 403/401 errors
            enhanced_headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': source.get('country', 'uk') == 'uk' and 'en-GB,en;q=0.5' or 
                                  source.get('country', '') == 'germany' and 'de-DE,de;q=0.9,en;q=0.8' or
                                  source.get('country', '') == 'france' and 'fr-FR,fr;q=0.9,en;q=0.8' or
                                  source.get('country', '') == 'spain' and 'es-ES,es;q=0.9,en;q=0.8' or 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/'
            }
            
            session = requests.Session()
            response = session.get(source['url'], headers=enhanced_headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.select(source['article_selector'])
            
            links = []
            for article in articles[:15]:  # Limit to 15 articles per source
                # Try multiple methods to find links
                link = None
                
                # Method 1: Direct link in the article container
                link_tag = article.find('a')
                if link_tag and link_tag.get('href'):
                    link = link_tag.get('href')
                
                # Method 2: Look for headline links
                if not link:
                    headline = article.select_one('h2 a, h3 a, .headline a, .title a')
                    if headline and headline.get('href'):
                        link = headline.get('href')
                
                # Method 3: Check if the article itself is an anchor tag
                if not link and article.name == 'a' and article.get('href'):
                    link = article.get('href')
                
                if link:
                    # Handle relative URLs
                    if link.startswith('/'):
                        domain = re.match(r'(https?://[^/]+)', source['url']).group(1)
                        link = domain + link
                    elif not link.startswith('http'):
                        domain = re.match(r'(https?://[^/]+)', source['url']).group(1)
                        link = domain + '/' + link.lstrip('/')
                    
                    # Avoid duplicates and non-article links
                    if link not in links and not link.endswith('#'):
                        links.append(link)
            
            logger.info(f"Found {len(links)} article links from {source['name']}")
            return links
            
        except Exception as e:
            logger.error(f"Error getting article links from {source['name']}: {e}")
            return []

    def scrape_article(self, url, source):
        """Scrape content from an article URL"""
        try:
            logger.info(f"Scraping article: {url}")
            
            # More robust headers for article requests with appropriate language settings
            enhanced_headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': source.get('country', 'uk') == 'uk' and 'en-GB,en;q=0.5' or 
                                  source.get('country', '') == 'germany' and 'de-DE,de;q=0.9,en;q=0.8' or
                                  source.get('country', '') == 'france' and 'fr-FR,fr;q=0.9,en;q=0.8' or
                                  source.get('country', '') == 'spain' and 'es-ES,es;q=0.9,en;q=0.8' or 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'Referer': source['url'],
            }
            
            session = requests.Session()
            response = session.get(url, headers=enhanced_headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple selectors for title if needed
            title = soup.select_one(source['title_selector'])
            if not title:
                title = soup.select_one('h1, .headline, .article-title, .title')
            title_text = title.get_text().strip() if title else "Title not found"
            
            # Try to find content with multiple selectors if needed
            content = soup.select_one(source['content_selector'])
            if not content:
                content = soup.select_one('.article-body, .content, .entry-content, article, [itemprop="articleBody"]')
            
            # Extract paragraphs from the content
            if content:
                paragraphs = content.find_all('p')
                content_text = ' '.join([p.get_text().strip() for p in paragraphs])
                # If no paragraphs found, try to get direct text
                if not content_text:
                    content_text = content.get_text().strip()
            else:
                content_text = "Content not found"
            
            # Try multiple selectors for date
            date = soup.select_one(source['date_selector'])
            if not date:
                date = soup.select_one('time, .date, .timestamp, [itemprop="datePublished"]')
            date_text = date.get_text().strip() if date else datetime.now().strftime("%Y-%m-%d")
            
            # Try to extract author information
            author = soup.select_one('.author, [rel="author"], [itemprop="author"], .byline')
            author_text = author.get_text().strip() if author else "Author not found"
            
            # Extract any available meta description
            meta_desc = soup.select_one('meta[name="description"]')
            description = meta_desc['content'] if meta_desc and meta_desc.get('content') else ""
            
            article_data = {
                'source': source['name'],
                'category': source['category'],
                'region': source['region'],
                'country': source.get('country', ''),
                'url': url,
                'title': title_text,
                'author': author_text,
                'description': description,
                'content': content_text,
                'date': date_text,
                'content_length': len(content_text),
                'language': source.get('country', 'uk') == 'uk' and 'en' or 
                           source.get('country', '') == 'germany' and 'de' or
                           source.get('country', '') == 'france' and 'fr' or
                           source.get('country', '') == 'spain' and 'es' or 'en',
                'scraped_at': datetime.now().isoformat()
            }
            
            logger.info(f"Successfully scraped article: {title_text}")
            return article_data
            
        except Exception as e:
            logger.error(f"Error scraping article {url}: {e}")
            return None

    def save_to_json(self, articles):
        """Save articles data to a JSON file"""
        try:
            # Make sure directory exists
            output_dir = os.path.dirname(self.output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved {len(articles)} articles to {self.output_file}")
        except Exception as e:
            logger.error(f"Error saving to JSON: {e}")
            
    def generate_report(self):
        """Generate a report about scraped articles"""
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                articles = json.load(f)
                
            report = {
                "total_articles": len(articles),
                "by_source": {},
                "by_country": {},
                "by_category": {
                    "technology": 0,
                    "business": 0,
                    "investing": 0
                },
                "by_language": {
                    "en": 0,
                    "de": 0,
                    "fr": 0,
                    "es": 0
                },
                "average_content_length": 0,
                "scraped_at": datetime.now().isoformat()
            }
            
            # Count articles by source and category
            total_content_length = 0
            for article in articles:
                source = article['source']
                category = article['category']
                country = article.get('country', '')
                language = article.get('language', 'en')
                content_length = article.get('content_length', 0)
                
                # By source
                report["by_source"][source] = report["by_source"].get(source, 0) + 1
                
                # By country
                if country:
                    report["by_country"][country] = report["by_country"].get(country, 0) + 1
                
                # By category
                if category in report["by_category"]:
                    report["by_category"][category] += 1
                
                # By language
                if language in report["by_language"]:
                    report["by_language"][language] += 1
                    
                # Content length
                total_content_length += content_length
            
            # Calculate average content length
            if articles:
                report["average_content_length"] = total_content_length / len(articles)
            
            # Generate report file
            report_file = self.output_file.replace('.json', '_report.json')
            try:
                with open(report_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=4)
                logger.info(f"Generated report saved to {report_file}")
            except Exception as e:
                logger.error(f"Error saving report: {e}")
                
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None

    def run(self):
        """Run the scraper for all sources"""
        all_articles = []
        
        for source in self.sources:
            logger.info(f"Processing source: {source['name']}")
            
            # Try multiple times if needed
            for attempt in range(self.retry_attempts):
                try:
                    # Choose a random user agent for each source
                    self.headers['User-Agent'] = random.choice(self.user_agents)
                    
                    article_links = self.get_article_links(source)
                    
                    if article_links:
                        break
                    else:
                        logger.warning(f"No article links found for {source['name']} on attempt {attempt+1}")
                        if attempt < self.retry_attempts - 1:
                            # Wait longer between retries
                            time.sleep(3 + attempt * 2)
                except Exception as e:
                    logger.error(f"Error on attempt {attempt+1} for {source['name']}: {e}")
                    if attempt < self.retry_attempts - 1:
                        time.sleep(3 + attempt * 2)
            
            # Randomize delay between requests to avoid detection
            for link in article_links:
                # Random delay between 1.5 and 3.5 seconds
                time.sleep(1.5 + random.random() * 2)
                
                # Change user agent for each article
                self.headers['User-Agent'] = random.choice(self.user_agents)
                
                # Try multiple times for each article if needed
                for attempt in range(self.retry_attempts):
                    try:
                        article_data = self.scrape_article(link, source)
                        if article_data and article_data.get('title') != "Title not found" and article_data.get('content') != "Content not found":
                            all_articles.append(article_data)
                            break
                        else:
                            logger.warning(f"Failed to scrape article {link} on attempt {attempt+1}")
                            if attempt < self.retry_attempts - 1:
                                time.sleep(2 + attempt)
                    except Exception as e:
                        logger.error(f"Error scraping article {link} on attempt {attempt+1}: {e}")
                        if attempt < self.retry_attempts - 1:
                            time.sleep(2 + attempt)
            
            logger.info(f"Completed scraping from {source['name']}")
            
            # Save after each source to avoid losing all data if something goes wrong
            self.save_to_json(all_articles)
            logger.info(f"Saved {len(all_articles)} articles so far")
        
        # Final save with all articles
        self.save_to_json(all_articles)
        logger.info(f"Scraping completed. Total articles: {len(all_articles)}")
        
        # Generate report
        self.generate_report()
        
        return all_articles


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrape articles from European technology, business, and investing sources')
    parser.add_argument('--output', type=str, default=None, help='Output file path')
    parser.add_argument('--retry', type=int, default=3, help='Number of retry attempts')
    parser.add_argument('--sources', type=int, default=None, help='Number of sources to scrape (default: all)')
    parser.add_argument('--articles', type=int, default=None, help='Number of articles per source')
    parser.add_argument('--category', type=str, default=None, help='Filter sources by category (technology, business, investing)')
    parser.add_argument('--country', type=str, default=None, help='Filter sources by country (uk, spain)')
    args = parser.parse_args()
    
    # Create directory for output if it doesn't exist
    output_dir = "scraped_data"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Set output file path with better naming
    if args.output:
        output_file = args.output
    else:
        current_date = datetime.now().strftime('%Y%m%d')
        output_file = os.path.join(output_dir, f"Europe_tech_news_{current_date}.json")
    
    # Initialize and run the scraper
    scraper = EuropeNewsScraper(output_file=output_file, retry_attempts=args.retry)
    
    # Filter sources by category if specified
    if args.category:
        scraper.sources = [source for source in scraper.sources if source.get('category') == args.category]
        
    # Filter sources by country if specified
    if args.country:
        scraper.sources = [source for source in scraper.sources if source.get('country') == args.country]
    
    # Limit sources if specified
    if args.sources:
        scraper.sources = scraper.sources[:args.sources]
    
    # Limit articles per source if specified
    if args.articles:
        # Monkey patch the get_article_links method
        original_get_article_links = scraper.get_article_links
        def limited_get_article_links(source):
            links = original_get_article_links(source)
            return links[:args.articles]
        scraper.get_article_links = limited_get_article_links
    
    # Run the scraper
    articles = scraper.run()
    
    # Print summary
    print(f"\nScraping completed. {len(articles)} European articles saved to {output_file}")