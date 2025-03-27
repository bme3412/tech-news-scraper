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
from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("us_scraper.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class USNewsScraper:
    def __init__(self, output_dir=None, retry_attempts=3, openai_api_key=None):
        # Set up output directory structure
        if output_dir is None:
            current_date = datetime.now().strftime('%Y%m%d')
            output_dir = f"US_tech_news_{current_date}"
        
        self.output_dir = output_dir
        # Create directory structure
        self.articles_dir = os.path.join(self.output_dir, "articles")
        self.summaries_dir = os.path.join(self.output_dir, "summaries")
        
        # Create directories if they don't exist
        os.makedirs(self.articles_dir, exist_ok=True)
        os.makedirs(self.summaries_dir, exist_ok=True)
        
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
        
        # Set up OpenAI API
        self.openai_api_key = openai_api_key
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        
        # US News Sources - Removed sources that failed in the logs
        self.sources = [
            {
                'name': 'CNBC',
                'url': 'https://www.cnbc.com/technology/',
                'article_selector': 'div.Card-standardBreakerCard',
                'title_selector': 'h1',
                'content_selector': '.ArticleBody-articleBody',
                'date_selector': 'time',
                'category': 'technology',
                'region': 'north_america'
            },
            {
                'name': 'VentureBeat',
                'url': 'https://venturebeat.com/',
                'article_selector': 'article',
                'title_selector': 'h1.article-title',
                'content_selector': '.article-content',
                'date_selector': 'time',
                'category': 'technology',
                'region': 'north_america'
            },
            {
                'name': 'Business Insider',
                'url': 'https://www.businessinsider.com/tech',
                'article_selector': '.tout-title-link',
                'title_selector': 'h1',
                'content_selector': '.content-lock-content',
                'date_selector': 'time',
                'category': 'business',
                'region': 'north_america'
            },
            {
                'name': 'MarketWatch',
                'url': 'https://www.marketwatch.com/investing',
                'article_selector': '.article__content',
                'title_selector': 'h1',
                'content_selector': '.article__body',
                'date_selector': 'time',
                'category': 'investing',
                'region': 'north_america'
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
                'Accept-Language': 'en-US,en;q=0.5',
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
            
            # More robust headers for article requests
            enhanced_headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
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
                'url': url,
                'title': title_text,
                'author': author_text,
                'description': description,
                'content': content_text,
                'date': date_text,
                'content_length': len(content_text),
                'scraped_at': datetime.now().isoformat()
            }
            
            logger.info(f"Successfully scraped article: {title_text}")
            return article_data
            
        except Exception as e:
            logger.error(f"Error scraping article {url}: {e}")
            return None

    def generate_safe_filename(self, title):
        """Generate a safe filename from article title"""
        # Remove invalid characters and limit length
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().lower()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        # Limit to 50 characters to avoid overly long filenames
        if len(safe_title) > 50:
            safe_title = safe_title[:50]
        # Add timestamp to avoid duplicates
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{safe_title}-{timestamp}"

    def save_article_to_json(self, article_data):
        """Save a single article to its own JSON file"""
        try:
            # Generate filename from title
            filename = self.generate_safe_filename(article_data['title'])
            filepath = os.path.join(self.articles_dir, f"{filename}.json")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(article_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Saved article to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving article to JSON: {e}")
            return None

    def summarize_with_openai(self, article_data):
        """Use OpenAI to summarize article content"""
        try:
            if not self.openai_api_key:
                logger.warning("OpenAI API key not provided, skipping summarization")
                return {"error": "API key not provided"}

            # Prepare content for summarization (limit length if needed)
            title = article_data['title']
            content = article_data['content']
            
            # Limit content to avoid exceeding token limits (rough estimate)
            max_content_length = 4000  # Adjust based on your API plan
            if len(content) > max_content_length:
                truncated_content = content[:max_content_length] + "..."
            else:
                truncated_content = content
            
            # Create prompt for summarization
            prompt = f"Please provide a concise summary of this article titled '{title}':\n\n{truncated_content}"
            
            # Call OpenAI API using the updated client 
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",  # or another model of your choice
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes news articles concisely."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300  # Adjust for desired summary length
                )
                
                summary = response.choices[0].message.content.strip()
                
                summary_data = {
                    "article_title": title,
                    "article_source": article_data['source'],
                    "article_url": article_data['url'],
                    "article_date": article_data['date'],
                    "summary": summary,
                    "summary_generated_at": datetime.now().isoformat()
                }
                
                logger.info(f"Generated summary for article: {title}")
                return summary_data
                
            except Exception as api_error:
                logger.error(f"OpenAI API error: {api_error}")
                return {"error": str(api_error)}
                
        except Exception as e:
            logger.error(f"Error in summarization process: {e}")
            return {"error": str(e)}

    def save_summary_to_json(self, summary_data, article_filename):
        """Save article summary to its own JSON file"""
        try:
            # Use same base filename as the article
            base_filename = os.path.splitext(os.path.basename(article_filename))[0]
            filepath = os.path.join(self.summaries_dir, f"{base_filename}_summary.json")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Saved summary to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving summary to JSON: {e}")
            return None

    def generate_report(self):
        """Generate a report about scraped articles"""
        try:
            # List all article files
            article_files = [f for f in os.listdir(self.articles_dir) if f.endswith('.json')]
            
            articles = []
            for filename in article_files:
                filepath = os.path.join(self.articles_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    articles.append(json.load(f))
                
            report = {
                "total_articles": len(articles),
                "by_source": {},
                "by_category": {
                    "technology": 0,
                    "business": 0,
                    "investing": 0
                },
                "average_content_length": 0,
                "scraped_at": datetime.now().isoformat()
            }
            
            # Count articles by source and category
            total_content_length = 0
            for article in articles:
                source = article['source']
                category = article['category']
                content_length = article.get('content_length', 0)
                
                # By source
                report["by_source"][source] = report["by_source"].get(source, 0) + 1
                
                # By category
                if category in report["by_category"]:
                    report["by_category"][category] += 1
                    
                # Content length
                total_content_length += content_length
            
            # Calculate average content length
            if articles:
                report["average_content_length"] = total_content_length / len(articles)
            
            # Generate report file
            report_file = os.path.join(self.output_dir, "scraping_report.json")
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
                        if article_data and article_data.get('title') != "" and article_data.get('content') != "Content not found":
                            # Save individual article to its own JSON file
                            article_file = self.save_article_to_json(article_data)
                            
                            # Generate summary with OpenAI if API key is provided
                            if self.openai_api_key and article_file:
                                summary_data = self.summarize_with_openai(article_data)
                                if summary_data and 'error' not in summary_data:
                                    # Save summary to its own JSON file
                                    self.save_summary_to_json(summary_data, article_file)
                            
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
        
        # Generate summary report
        self.generate_report()
        
        logger.info(f"Scraping completed. Total articles: {len(all_articles)}")
        return len(all_articles)


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrape articles from US technology, business, and investing sources')
    parser.add_argument('--output', type=str, default=None, help='Output directory path')
    parser.add_argument('--retry', type=int, default=3, help='Number of retry attempts')
    parser.add_argument('--sources', type=int, default=None, help='Number of sources to scrape (default: all)')
    parser.add_argument('--articles', type=int, default=None, help='Number of articles per source')
    parser.add_argument('--category', type=str, default=None, help='Filter sources by category (technology, business, investing)')
    parser.add_argument('--openai-key', type=str, default=None, help='OpenAI API key for summarization')
    args = parser.parse_args()
    
    # Create directory for output if it doesn't exist
    current_date = datetime.now().strftime('%Y%m%d')
    output_dir = args.output if args.output else f"US_tech_news_{current_date}"
    
    # Initialize and run the scraper
    scraper = USNewsScraper(
        output_dir=output_dir, 
        retry_attempts=args.retry,
        openai_api_key=args.openai_key
    )
    
    # Filter sources by category if specified
    if args.category:
        scraper.sources = [source for source in scraper.sources if source.get('category') == args.category]
    
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
    num_articles = scraper.run()
    
    # Print summary
    print(f"\nScraping completed. {num_articles} US articles saved to {output_dir}")
    print(f"Individual articles saved in: {os.path.join(output_dir, 'articles')}")
    print(f"Article summaries saved in: {os.path.join(output_dir, 'summaries')}")
    
    if not args.openai_key:
        print("\nNote: OpenAI API key was not provided. To generate summaries, run again with --openai-key parameter.")