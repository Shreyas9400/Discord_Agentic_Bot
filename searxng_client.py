import aiohttp
import asyncio
from newspaper import Article
from typing import List, Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearXNGClient:
    """Client for searching with SearXNG and scraping results with newspaper."""
    
    def __init__(self, searxng_instance: str = "https://searx.be"):
        """
        Initialize the SearXNG client.
        
        Args:
            searxng_instance: URL of the SearXNG instance to use
        """
        self.searxng_instance = searxng_instance
        self.search_endpoint = f"{searxng_instance}/search"
    
    async def search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Perform a search using SearXNG.
        
        Args:
            query: The search query
            num_results: Maximum number of results to return
            
        Returns:
            Dictionary containing search results in a format similar to Serper
        """
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": "en",
            "time_range": "",
            "safesearch": 1,
            "pageno": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.search_endpoint, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_results(data, num_results)
                    else:
                        logger.error(f"SearXNG search failed with status code: {response.status}")
                        return {"error": f"Search failed with status code: {response.status}"}
        except Exception as e:
            logger.error(f"Error during SearXNG search: {str(e)}")
            return {"error": str(e)}
    
    def _format_results(self, data: Dict[str, Any], num_results: int) -> Dict[str, Any]:
        """
        Format SearXNG results to match the expected format.
        
        Args:
            data: Raw data from SearXNG
            num_results: Maximum number of results to return
            
        Returns:
            Formatted results dictionary
        """
        organic_results = []
        
        for result in data.get("results", [])[:num_results]:
            organic_result = {
                "title": result.get("title", ""),
                "link": result.get("url", ""),
                "snippet": result.get("content", ""),
                "source": result.get("engine", ""),
                "position": len(organic_results) + 1
            }
            organic_results.append(organic_result)
        
        return {
            "searchParameters": {
                "q": data.get("query", ""),
                "engine": "searxng"
            },
            "organic": organic_results,
            "serpapi_pagination": {
                "current": data.get("page", 1),
                "next_link": None
            }
        }
    
    async def scrape_url(self, url: str) -> Dict[str, str]:
        """
        Scrape content from a URL using newspaper.
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary containing the scraped content
        """
        try:
            article = Article(url)
            await asyncio.to_thread(article.download)
            await asyncio.to_thread(article.parse)
            
            return {
                "url": url,
                "title": article.title,
                "text": article.text,
                "authors": article.authors,
                "publish_date": str(article.publish_date) if article.publish_date else None,
                "top_image": article.top_image,
                "success": True
            }
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {str(e)}")
            return {
                "url": url,
                "error": str(e),
                "success": False
            }
    
    async def search_and_scrape(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Search and scrape results in parallel.
        
        Args:
            query: Search query
            max_results: Maximum number of results to scrape
            
        Returns:
            Dictionary containing search results and scraped content
        """
        # First perform the search
        search_results = await self.search(query, max_results)
        
        if "error" in search_results:
            return search_results
        
        # Extract URLs to scrape
        urls_to_scrape = [result["link"] for result in search_results.get("organic", [])]
        
        # Scrape URLs in parallel
        scrape_tasks = [self.scrape_url(url) for url in urls_to_scrape]
        scraped_results = await asyncio.gather(*scrape_tasks)
        
        # Add scraped content to search results
        for i, scrape_result in enumerate(scraped_results):
            if i < len(search_results.get("organic", [])):
                search_results["organic"][i]["scraped_content"] = scrape_result
        
        return search_results


async def test_searxng_client():
    """Test function for SearXNG client."""
    client = SearXNGClient()
    results = await client.search_and_scrape("current US tariffs on China 2025")
    print(f"Found {len(results.get('organic', []))} results")
    for i, result in enumerate(results.get("organic", [])):
        print(f"Result {i+1}: {result['title']}")
        scraped = result.get("scraped_content", {})
        if scraped.get("success", False):
            print(f"  Scraped {len(scraped.get('text', '').split())} words")
        else:
            print(f"  Scraping failed: {scraped.get('error')}")
    return results

if __name__ == "__main__":
    asyncio.run(test_searxng_client())