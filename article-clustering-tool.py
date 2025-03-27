import os
import json
from datetime import datetime
import logging
import glob
from openai import OpenAI
import argparse
from collections import defaultdict
import re
import html

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("article_clustering.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class ArticleClusteringTool:
    def __init__(self, input_dir, output_dir=None, openai_api_key=None):
        self.input_dir = input_dir
        
        # Set default output directory if not provided
        if output_dir is None:
            current_date = datetime.now().strftime('%Y%m%d')
            output_dir = f"clustered_articles_{current_date}"
        
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up OpenAI API client
        self.openai_api_key = openai_api_key
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            logger.error("OpenAI API key not provided. Clustering will not be available.")
            self.openai_client = None
    
    def load_articles(self):
        """Load all article JSON files from the input directory"""
        articles_path = os.path.join(self.input_dir, "articles")
        article_files = glob.glob(os.path.join(articles_path, "*.json"))
        
        articles = []
        for file_path in article_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    article_data = json.load(f)
                    articles.append(article_data)
            except Exception as e:
                logger.error(f"Error loading article from {file_path}: {e}")
        
        logger.info(f"Loaded {len(articles)} articles for processing")
        return articles
    
    def extract_article_metadata(self, articles):
        """Extract key metadata from articles for clustering"""
        metadata_list = []
        for article in articles:
            # Extract metadata fields for clustering
            metadata = {
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'category': article.get('category', ''),
                'date': article.get('date', ''),
                'description': article.get('description', ''),
                'content_length': article.get('content_length', 0),
                'content_snippet': article.get('content', '')[:500] + "..." if article.get('content', '') else '',
                'full_article': article  # Keep reference to full article
            }
            metadata_list.append(metadata)
        
        return metadata_list
    
    def cluster_articles_by_theme(self, article_metadata):
        """Use OpenAI to identify themes and cluster articles"""
        if not self.openai_client:
            logger.error("OpenAI client not initialized. Cannot perform clustering.")
            return None
        
        # Prepare data for OpenAI
        metadata_for_openai = []
        for i, metadata in enumerate(article_metadata):
            metadata_for_openai.append({
                'id': i,
                'title': metadata['title'],
                'description': metadata['description'],
                'content_snippet': metadata['content_snippet'][:300]  # Limit size for API call
            })
        
        try:
            # Create a prompt for OpenAI to identify themes and cluster articles
            prompt = f"""
            I have {len(metadata_for_openai)} news articles that I need to cluster by themes or topics.
            Here are the articles (shown with ID, title, and a snippet):
            
            {json.dumps(metadata_for_openai, indent=2)}
            
            Please analyze these articles and:
            1. Identify 3-7 main themes or topics that these articles cover
            2. Assign each article to one or more of these themes
            3. Return your analysis in the following JSON format:
            
            {{
              "themes": [
                {{
                  "name": "Theme Name",
                  "description": "Brief description of this theme",
                  "article_ids": [list of article IDs that belong to this theme]
                }},
                // More themes...
              ]
            }}
            
            Only return the JSON, no other explanations.
            """
            
            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo-16k",  # Using 16k model for larger context
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes news articles and identifies themes and topics."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower temperature for more deterministic results
            )
            
            # Extract JSON response
            try:
                result_text = response.choices[0].message.content.strip()
                # Clean the response if it has markdown JSON formatting
                if result_text.startswith("```json"):
                    result_text = result_text.split("```json")[1]
                if "```" in result_text:
                    result_text = result_text.split("```")[0]
                
                result = json.loads(result_text)
                logger.info(f"Successfully clustered articles into {len(result.get('themes', []))} themes")
                
                # Map the results back to full articles
                clustered_data = {
                    "themes": [],
                    "metadata": {
                        "total_articles": len(article_metadata),
                        "clustering_timestamp": datetime.now().isoformat()
                    }
                }
                
                for theme in result.get('themes', []):
                    theme_data = {
                        "name": theme.get('name', 'Unnamed Theme'),
                        "description": theme.get('description', ''),
                        "articles": []
                    }
                    
                    for article_id in theme.get('article_ids', []):
                        if 0 <= article_id < len(article_metadata):
                            theme_data["articles"].append(article_metadata[article_id]["full_article"])
                    
                    # Only add themes that have articles
                    if theme_data["articles"]:
                        clustered_data["themes"].append(theme_data)
                
                return clustered_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding OpenAI JSON response: {e}")
                logger.error(f"Raw response: {result_text}")
                return None
                
        except Exception as e:
            logger.error(f"Error during OpenAI API call for clustering: {e}")
            return None
    
    def generate_article_summaries(self, clustered_data):
        """Skip generating summaries as requested"""
        logger.info("Skipping theme summaries and key takeaways generation as requested")
        return clustered_data
    
    def generate_html(self, clustered_data):
        """Generate HTML report from clustered data with expandable article content"""
        if not clustered_data:
            logger.error("No clustered data to generate HTML from")
            return None
        
        # Prepare CSS styles for the HTML report
        css = """
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f7f7f7;
            }
            .container {
                background-color: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }
            header {
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 1px solid #eaeaea;
            }
            h1 {
                font-size: 2.2em;
                color: #2c3e50;
                margin-bottom: 10px;
            }
            h2 {
                font-size: 1.8em;
                color: #3498db;
                margin-top: 40px;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 1px solid #eaeaea;
            }
            h3 {
                font-size: 1.4em;
                color: #2c3e50;
                margin-top: 25px;
                margin-bottom: 15px;
            }
            h4 {
                font-size: 1.1em;
                color: #555;
                margin-top: 20px;
                margin-bottom: 10px;
                font-weight: bold;
            }
            .article-card {
                background-color: white;
                border: 1px solid #ddd;
                border-left: 5px solid #3498db;
                border-radius: 4px;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .article-title {
                font-weight: bold;
                font-size: 1.2em;
                margin-bottom: 8px;
                cursor: pointer;
                color: #3498db;
                display: flex;
                align-items: center;
            }
            .article-title:hover {
                text-decoration: underline;
            }
            .article-title:after {
                content: "▼";
                font-size: 0.8em;
                margin-left: 8px;
                transition: transform 0.3s ease;
            }
            .article-title.active:after {
                transform: rotate(180deg);
            }
            .article-source {
                color: #666;
                font-size: 0.9em;
                margin-bottom: 8px;
            }
            .article-description {
                margin-bottom: 10px;
                color: #555;
                font-style: italic;
            }
            .article-content {
                display: none;
                background-color: #f9f9f9;
                border-top: 1px solid #eaeaea;
                padding: 15px;
                margin-top: 15px;
                font-size: 0.95em;
                max-height: 500px;
                overflow-y: auto;
                line-height: 1.7;
            }
            .article-content p {
                margin-bottom: 15px;
                text-align: justify;
            }
            .article-content h4 {
                margin-top: 20px;
                margin-bottom: 10px;
                color: #2c3e50;
            }
            .theme-meta {
                display: flex;
                justify-content: space-between;
                margin-bottom: 20px;
                font-size: 0.9em;
                color: #666;
            }
            .theme-count {
                background-color: #3498db;
                color: white;
                border-radius: 20px;
                padding: 3px 10px;
                font-size: 0.8em;
            }
            footer {
                text-align: center;
                margin-top: 50px;
                padding-top: 20px;
                border-top: 1px solid #eaeaea;
                color: #777;
                font-size: 0.9em;
            }
            a {
                color: #3498db;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
        """
        
        # Add JavaScript for toggling article content
        javascript = """
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const articleTitles = document.querySelectorAll('.article-title');
                
                articleTitles.forEach(title => {
                    title.addEventListener('click', function() {
                        const content = this.parentNode.querySelector('.article-content');
                        if (content.style.display === 'block') {
                            content.style.display = 'none';
                            this.classList.remove('active');
                        } else {
                            content.style.display = 'block';
                            this.classList.add('active');
                        }
                    });
                });
            });
        </script>
        """
        
        # Generate the HTML content
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        total_articles = clustered_data.get("metadata", {}).get("total_articles", 0)
        theme_count = len(clustered_data.get("themes", []))
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>News Article Clusters</title>
            {css}
            {javascript}
        </head>
        <body>
            <div class="container">
                <header>
                    <h1>News Article Analysis</h1>
                    <p>Clustered by themes and topics - Generated on {now}</p>
                    <div class="theme-meta">
                        <span>Total Articles: {total_articles}</span>
                        <span>Themes Identified: <span class="theme-count">{theme_count}</span></span>
                    </div>
                </header>
                
                <section id="themes">
        """
        
        # Add each theme and its articles
        for i, theme in enumerate(clustered_data.get("themes", []), 1):
            theme_name = html.escape(theme.get("name", f"Theme {i}"))
            theme_description = html.escape(theme.get("description", ""))
            articles = theme.get("articles", [])
            
            html_content += f"""
                    <section id="theme-{i}">
                        <h2>{theme_name} <small>({len(articles)} articles)</small></h2>
                        <p>{theme_description}</p>
                        
                        <h3>Articles in this Theme</h3>
            """
            
            # Add each article in the theme with expandable content
            for article in articles:
                title = html.escape(article.get("title", ""))
                source = html.escape(article.get("source", ""))
                url = html.escape(article.get("url", "#"))
                description = html.escape(article.get("description", "No description available"))
                date = html.escape(article.get("date", ""))
                
                # Get the full article content and escape HTML special characters
                article_content = html.escape(article.get("content", "Full content not available"))
                
                # Format the content nicely with paragraphs and styling
                formatted_content = ""
                if article_content:
                    # Split into paragraphs and format
                    paragraphs = article_content.strip().split('\n')
                    
                    for para in paragraphs:
                        if para.strip():
                            # Check if it might be a headline or section title (shorter than 100 chars, no periods)
                            if len(para) < 100 and '.' not in para and para.strip().endswith(':'):
                                formatted_content += f"<h4>{para}</h4>"
                            else:
                                formatted_content += f"<p>{para}</p>"
                else:
                    formatted_content = "<p>Full content not available</p>"
                
                html_content += f"""
                        <div class="article-card">
                            <div class="article-title">{title}</div>
                            <div class="article-source">{source} - {date}</div>
                            <div class="article-description">{description}</div>
                            <div class="article-content">{formatted_content}</div>
                        </div>
                """
            
            html_content += """
                    </section>
            """
        
        # Close the HTML document
        html_content += """
                </section>
                
                <footer>
                    <p>Generated using AI clustering and summarization</p>
                    <p><small>Click on any article title to view its full content</small></p>
                </footer>
            </div>
        </body>
        </html>
        """
        
        # Save the HTML file
        output_file = os.path.join(self.output_dir, "clustered_articles_report.html")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"HTML report generated and saved to {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error saving HTML report: {e}")
            return None
    
    def save_clustered_data(self, clustered_data):
        """Save the clustered data to a JSON file for reference"""
        if not clustered_data:
            return
        
        output_file = os.path.join(self.output_dir, "clustered_data.json")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(clustered_data, f, ensure_ascii=False, indent=4)
            logger.info(f"Clustered data saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving clustered data: {e}")
    
    def run(self):
        """Main method to run the entire process"""
        # Load articles
        articles = self.load_articles()
        if not articles:
            logger.error("No articles found to process")
            return None
        
        # Extract metadata
        article_metadata = self.extract_article_metadata(articles)
        
        # Cluster articles by theme
        clustered_data = self.cluster_articles_by_theme(article_metadata)
        if not clustered_data:
            logger.error("Failed to cluster articles")
            return None
        
        # Generate summaries for each theme
        clustered_data = self.generate_article_summaries(clustered_data)
        
        # Save the clustered data as JSON
        self.save_clustered_data(clustered_data)
        
        # Generate and save HTML report
        html_file = self.generate_html(clustered_data)
        
        return html_file


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Cluster news articles by themes and generate an HTML report')
    parser.add_argument('--input', type=str, required=True, help='Input directory containing the scraped articles')
    parser.add_argument('--output', type=str, default=None, help='Output directory for the HTML report')
    parser.add_argument('--openai-key', type=str, required=True, help='OpenAI API key')
    args = parser.parse_args()
    
    # Check if input directory exists
    if not os.path.exists(args.input):
        print(f"Error: Input directory '{args.input}' does not exist")
        exit(1)
    
    # Run the clustering tool
    tool = ArticleClusteringTool(
        input_dir=args.input,
        output_dir=args.output,
        openai_api_key=args.openai_key
    )
    
    html_file = tool.run()
    
    if html_file:
        print(f"\nHTML report generated: {html_file}")
        print("Open this file in a web browser to view the clustered articles")
    else:
        print("\nFailed to generate HTML report. Check the logs for details.")