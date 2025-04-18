import aiohttp
import asyncio
from newspaper import Article
from typing import List, Dict, Any, Optional
import logging
import os
import ssl
import random
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearXNGClient:
    """Client for searching with SearXNG and scraping results with newspaper."""
    
    def __init__(self, searxng_instance: str = None, verify_ssl: bool = False):
        """
        Initialize the SearXNG client.
        
        Args:
            searxng_instance: URL of the SearXNG instance to use
                              If None, tries to get from environment variable SEARXNG_URL
                              Otherwise defaults to localhost:8080
            verify_ssl: Whether to verify SSL certificates (set to False to disable verification)
        """
        # Get SearXNG URL from environment variable or use provided instance or default
        self.searxng_instance = (
            searxng_instance or 
            os.environ.get("SEARXNG_URL") or 
            "http://searxng:8080"
        )
        self.verify_ssl = verify_ssl
        logger.info(f"Initializing SearXNG client with instance: {self.searxng_instance}, SSL verification: {self.verify_ssl}")
        self.search_endpoint = f"{self.searxng_instance}/search"
        
        # List of search engines to try when the primary engine fails
        # Excluding Google since it's rate-limiting
        self.fallback_engines = [
            "duckduckgo", "bing", "brave", "ecosia", "startpage", 
            "yahoo", "qwant", "mojeek", "wikipedia"
        ]
    
    async def search(self, query: str, num_results: int = 10, engines: List[str] = None) -> Dict[str, Any]:
        """
        Perform a search using SearXNG.
        
        Args:
            query: The search query
            num_results: Maximum number of results to return
            engines: Specific engines to use (defaults to None which uses SearXNG defaults)
            
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
        
        # Add engines parameter if specified
        if engines:
            params["engines"] = ",".join(engines)
        
        try:
            logger.info(f"Sending search request to {self.search_endpoint} with query: {query}")
            
            # Create SSL context that doesn't verify certificates if verify_ssl is False
            ssl_context = None
            if not self.verify_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create a client session with the appropriate SSL context
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(self.search_endpoint, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Received {len(data.get('results', []))} results from SearXNG")
                        return self._format_results(data, num_results)
                    else:
                        error_text = await response.text()
                        logger.error(f"SearXNG search failed with status code: {response.status}, response: {error_text[:200]}")
                        return {"error": f"Search failed with status code: {response.status}"}
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error to SearXNG instance at {self.searxng_instance}: {str(e)}")
            return {"error": f"Cannot connect to SearXNG at {self.searxng_instance}. Please check if the service is running."}
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
        
        # Include search debug info
        engines_with_errors = []
        for engine, error in data.get("unresponsive_engines", []):
            engines_with_errors.append(f"{engine}: {error}")
            
        return {
            "searchParameters": {
                "q": data.get("query", ""),
                "engine": "searxng",
                "engines_used": data.get("engines", []),
                "engines_with_errors": engines_with_errors
            },
            "organic": organic_results,
            "serpapi_pagination": {
                "current": data.get("page", 1),
                "next_link": None
            }
        }
    
    async def scrape_url(self, url: str) -> Dict[str, str]:
        try:
            logger.info(f"Scraping URL: {url}")
            
            # Configure newspaper to not verify SSL certificates
            config = {}
            if not self.verify_ssl:
                config = {'verify': False}
            
            article = Article(url)
            
            # Use more robust error handling during download and parse
            try:
                await asyncio.to_thread(article.download)
                await asyncio.to_thread(article.parse)
            except Exception as e:
                return {
                    "url": url,
                    "error": f"Article processing error: {str(e)}",
                    "success": False
                }
            
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
    
    async def search_and_scrape(self, query: str, max_results: int = 30) -> Dict[str, Any]:
        """
        Search and scrape results in parallel.
        
        Args:
            query: Search query
            max_results: Maximum number of results to scrape
            
        Returns:
            Dictionary containing search results and scraped content
        """
        # First try default search (which includes Google)
        search_results = await self.search(query, max_results)
        
        # If error or no results, try with specific engines (excluding Google)
        if "error" in search_results or not search_results.get("organic", []):
            logger.warning("Default search failed, trying with alternative engines")
            # Pick 3 random engines from the fallback list
            engines_to_try = random.sample(self.fallback_engines, min(3, len(self.fallback_engines)))
            logger.info(f"Trying search with engines: {engines_to_try}")
            search_results = await self.search(query, max_results, engines=engines_to_try)
        
        if "error" in search_results:
            logger.warning(f"Search error: {search_results['error']}")
            return search_results
        
        # Extract URLs to scrape
        urls_to_scrape = [result["link"] for result in search_results.get("organic", [])]
        
        if not urls_to_scrape:
            logger.warning("No URLs found to scrape")
            return search_results
            
        logger.info(f"Scraping {len(urls_to_scrape)} URLs")
        
        # Scrape URLs in parallel with small delay to avoid overwhelming the network
        scrape_tasks = []
        for url in urls_to_scrape:
            # Add a small random delay between scrapes to avoid overwhelming the network
            await asyncio.sleep(random.uniform(0.1, 0.5))
            scrape_tasks.append(self.scrape_url(url))
            
        # Use gather with return_exceptions=True to prevent one failure from stopping all scrapes
        scraped_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        
        # Add scraped content to search results
        for i, scrape_result in enumerate(scraped_results):
            if i < len(search_results.get("organic", [])):
                # Handle the case where gather returned an exception instead of a result
                if isinstance(scrape_result, Exception):
                    search_results["organic"][i]["scraped_content"] = {
                        "url": search_results["organic"][i]["link"],
                        "error": str(scrape_result),
                        "success": False
                    }
                else:
                    search_results["organic"][i]["scraped_content"] = scrape_result
        
        return search_results


async def test_searxng_client():
    """Test function for SearXNG client."""
    # Use environment variable or default to localhost
    searxng_url = os.environ.get("SEARXNG_URL", "http://localhost:8080")
    
    logger.info(f"Testing SearXNG client with instance: {searxng_url}")
    # Create client with SSL verification disabled
    client = SearXNGClient(searxng_url, verify_ssl=False)
    
    try:
        # Test with specific engines that are less likely to be rate limited
        test_query = "current US tariffs on China 2025"
        logger.info(f"Testing with query: {test_query}")
        
        # Try first with DuckDuckGo specifically (usually more reliable)
        results = await client.search(test_query, engines=["duckduckgo"])
        
        if "error" in results or not results.get("organic", []):
            logger.warning("DuckDuckGo search failed, trying with fallback engines")
            results = await client.search_and_scrape(test_query)
        else:
            # If search succeeded, also scrape the content
            urls_to_scrape = [result["link"] for result in results.get("organic", [])]
            scrape_tasks = [client.scrape_url(url) for url in urls_to_scrape]
            scraped_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
            
            for i, scrape_result in enumerate(scraped_results):
                if i < len(results.get("organic", [])):
                    if isinstance(scrape_result, Exception):
                        results["organic"][i]["scraped_content"] = {
                            "url": results["organic"][i]["link"],
                            "error": str(scrape_result),
                            "success": False
                        }
                    else:
                        results["organic"][i]["scraped_content"] = scrape_result
        
        if "error" in results:
            logger.error(f"Search error: {results['error']}")
            return results
            
        logger.info(f"Found {len(results.get('organic', []))} results")
        
        for i, result in enumerate(results.get("organic", [])):
            print(f"Result {i+1}: {result['title']} (source: {result.get('source', 'unknown')})")
            scraped = result.get("scraped_content", {})
            if scraped.get("success", False):
                print(f"  Scraped {len(scraped.get('text', '').split())} words")
            else:
                print(f"  Scraping failed: {scraped.get('error')}")
        return results
    except Exception as e:
        logger.error(f"Test failed with exception: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    asyncio.run(test_searxng_client())
