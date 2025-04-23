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
    def __init__(self, searxng_instance="http://searxng:8080"):
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
            description="Agent to perform web searches and provide detailed, analytical responses.",
            instruction="""You are an expert Web Search Assistant focused on providing comprehensive, well-structured answers.

When responding to a query:
1. Thoroughly analyze all search results and scraped content.
2. Provide an exhaustive, detailed response that covers all relevant aspects of the topic.
3. Structure your response with clear sections and subsections using Markdown.
4. When citing information, use numbered references [1], [2], etc. Do NOT include raw URLs in the main text.
5. Include specific data points, statistics, and quotes to support your analysis.

Response Structure:
- Start with a brief overview/summary
- Organize main content into relevant sections
- Use bullet points for clarity when appropriate
- Include contradicting viewpoints or controversies if they exist
- Provide quantitative data whenever available
- End with key takeaways or conclusions

Citation Guidelines:
- Cite sources as [1], [2], etc.
- Multiple pieces of information from the same source can use the same number
- Example: "According to [1], market growth reached 23% in 2023, while another analysis [2] suggests..."

The actual URLs will be automatically appended as a numbered reference list at the end of your response.
Make your response as comprehensive and informative as possible while maintaining clarity and structure.
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

        # Collect only URLs that were successfully scraped
        urls = []
        for result in search_results.get("organic", []):
            scraped = result.get("scraped_content", {})
            if scraped.get("success", False) and scraped.get("url"):
                urls.append(scraped.get("url"))
        
        # Remove duplicates while maintaining order
        urls = list(dict.fromkeys(urls))

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

        # Append sources as Markdown list at the end
        if urls:
            final_response += "\n\n## Sources\n" + "\n".join(f"- {url}" for url in urls)

        return final_response


# Example usage 
if __name__ == "__main__":
    # Test the web search agent
    async def test_agent():
        search_agent = WebSearchAgent()
        result = await search_agent.search("What are the latest developments in quantum computing?")
        print(result)
        
    asyncio.run(test_agent())