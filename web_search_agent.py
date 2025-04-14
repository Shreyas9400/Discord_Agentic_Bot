from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from shared_utils import get_conversation_context
from datetime import datetime
import asyncio
import json
from searxng_client import SearXNGClient

class WebSearchAgent:
    """
    Agent that performs web searches using SearXNG
    """
    def __init__(self, searxng_instance="http://localhost:8888"):
        """
        Initialize the web search agent
        
        Args:
            searxng_instance: URL of the SearXNG instance to use
        """
        self.APP_NAME = "web_search_agent"
        self.USER_ID = "discord_user"
        self.SESSION_ID = "discord_session"
        
        # Create SearXNG client
        self.searxng_client = SearXNGClient(searxng_instance)
        
        # Create the agent
        self.agent = Agent(
            name="web_search_agent",
            model="gemini-2.0-flash",
            description="Agent to perform web searches and provide informative responses.",
            instruction="""You are a helpful Web Search Assistant.
            
            When the user asks a question:
            1. Use SearXNG Search to find relevant information
            2. Read the scraped content from each result to get detailed information
            3. Synthesize the information into a clear, concise answer
            4. Cite your sources when providing information
            5. If search results are insufficient, explain what you know and what you don't know
            6. Consider any conversation context provided when formulating your response
            
            Provide factual answers based on search results rather than assumptions.
            """
        )
        
        # Set up session and runner
        self.session_service = InMemorySessionService()
        self.session = self.session_service.create_session(
            app_name=self.APP_NAME, 
            user_id=self.USER_ID, 
            session_id=self.SESSION_ID
        )
        self.runner = Runner(
            agent=self.agent, 
            app_name=self.APP_NAME, 
            session_service=self.session_service
        )
    
    async def search(self, query, user_id=None, message_history=None):
        """
        Perform a web search with context
        
        Args:
            query: String containing the search query
            user_id: User identifier for retrieving memories
            message_history: List of recent messages
            
        Returns:
            String containing the search results
        """
        # Get context if user_id is provided
        context = ""
        if user_id:
            context = await get_conversation_context(query, user_id, message_history)
        
        # Perform SearXNG search and scrape results
        search_results = await self.searxng_client.search_and_scrape(query)
        
        # Format search results for the agent
        results_str = json.dumps(search_results, indent=2)
        
        # Create prompt with context, query, and search results
        prompt = f"""
{context}

Current date: {datetime.now().strftime('%Y-%m-%d')}
Current time: {datetime.now().strftime('%H:%M:%S')}

User search query: {query}

Search results from SearXNG:
{results_str}

Please analyze these search results, including the scraped content, and provide a comprehensive answer to the user's query.
Take into account any relevant context.
"""
        
        content = types.Content(role='user', parts=[types.Part(text=prompt)])
        events = self.runner.run(
            user_id=self.USER_ID, 
            session_id=self.SESSION_ID, 
            new_message=content
        )
        
        # Get the final response
        final_response = None
        all_responses = []

        for event in events:
            if hasattr(event, 'content') and hasattr(event.content, 'parts') and event.content.parts:
                response_text = event.content.parts[0].text
                all_responses.append(response_text)
                
            if event.is_final_response():
                final_response = event.content.parts[0].text

        # If we didn't get a final response but got other responses, use those
        if final_response is None and all_responses:
            final_response = "\n".join(all_responses)
        elif final_response is None:
            final_response = "Sorry, I couldn't find any information on that topic."

        return final_response


# Example usage 
if __name__ == "__main__":
    # Test the web search agent
    async def test_agent():
        search_agent = WebSearchAgent()
        result = await search_agent.search("What are the latest developments in quantum computing?")
        print(result)
        
    asyncio.run(test_agent())