# test_web_search_agent.py

import asyncio
from web_search_agent import WebSearchAgent

async def test_web_search():
    agent = WebSearchAgent()
    query = "What are the latest developments in quantum computing?"
    
    print(f"Running test for query: {query}\n")
    
    response = await agent.search(query)
    
    print("=== WebSearchAgent Response ===")
    print(response)

if __name__ == "__main__":
    asyncio.run(test_web_search())
