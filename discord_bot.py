import discord
from discord.ext import commands
import asyncio
import os
import re
from typing import Tuple, Dict, Any
from dotenv import load_dotenv
import logging
from datetime import datetime

# Import agents
from parallel_research_agent import run_parallel_research
from web_search_agent import WebSearchAgent
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import Mem0 for memory capabilities
from Memory import ensure_qdrant_collection, initialize_mem0
from shared_utils import get_conversation_context

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set Google API Key in environment
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)  # Disable default help command

# Global memory instance
mem0_instance = initialize_mem0()

class QueryDispatcher:
    """
    Agent that determines how to handle user queries
    """
    def __init__(self):
        """Initialize the dispatcher agent"""
        self.APP_NAME = "query_dispatcher"
        self.USER_ID = "discord_dispatcher"
        self.SESSION_ID = "dispatcher_session"
        
        # Create the dispatcher agent
        self.agent = Agent(
            name="query_dispatcher",
            model="gemini-2.0-flash",
            description="Agent that determines how to handle user queries.",
            instruction="""You are a Query Dispatcher that determines the best way to handle a user's query.

For each user query, analyze it and classify into ONE of these categories:
1. KNOWLEDGE_BASE: Questions that can be answered using your existing knowledge
2. WEB_SEARCH: Questions about current events, specific facts, or that need up-to-date information
3. RESEARCH: Complex topics requiring in-depth analysis, multiple perspectives, or comprehensive reports
4. CHAT: Personal conversations, greetings, opinions, or casual dialogue that primarily need memory of past interactions

Output ONLY the category name followed by a brief explanation:
<CATEGORY>: explanation of why this category is appropriate

Examples:
- "Who was the first president of the United States?" -> "KNOWLEDGE_BASE: This is a basic historical fact that doesn't require current information."
- "What happened in the news today?" -> "WEB_SEARCH: This requires current information that needs to be retrieved from the web."
- "What are the long-term economic impacts of tariffs on China?" -> "RESEARCH: This is a complex topic requiring in-depth analysis from multiple perspectives."
- "How are you doing today?" -> "CHAT: This is a casual conversational query that benefits from memory of past interactions."

Only output one of the four categories. Do not suggest multiple options.
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
    
    def dispatch(self, query: str) -> Tuple[str, str]:
        """
        Determine how to handle the given query
        
        Args:
            query: String containing the user query
            
        Returns:
            Tuple of (category, explanation)
        """
        content = types.Content(role='user', parts=[types.Part(text=query)])
        events = self.runner.run(
            user_id=self.USER_ID, 
            session_id=self.SESSION_ID, 
            new_message=content
        )
        
        # Get the final response
        final_response = None
        for event in events:
            if event.is_final_response():
                final_response = event.content.parts[0].text
        
        # Extract the category and explanation
        match = re.match(r"(KNOWLEDGE_BASE|WEB_SEARCH|RESEARCH|CHAT):\s*(.*)", final_response, re.DOTALL)
        if match:
            category = match.group(1)
            explanation = match.group(2).strip()
            return category, explanation
        else:
            # Default to chat if parsing fails
            return "CHAT", "Default handling as chat interaction."


# Initialize the dispatcher agent
dispatcher = QueryDispatcher()

# Create a direct knowledge agent for answering from knowledge base
# Modified KnowledgeBaseAgent with context support
class KnowledgeBaseAgent:
    """
    Agent that answers questions using its own knowledge base
    """
    def __init__(self):
        """Initialize the knowledge base agent"""
        self.APP_NAME = "knowledge_base_agent"
        self.USER_ID = "discord_kb_user"
        self.SESSION_ID = "kb_session"
        
        # Create the agent
        self.agent = Agent(
            name="knowledge_base_agent",
            model="gemini-2.0-flash",
            description="Agent to answer questions using its built-in knowledge.",
            instruction="""You are a knowledgeable assistant that answers questions based on your existing knowledge.
            
            Provide clear, concise, and accurate responses to user questions.
            If a topic is outside your knowledge base or requires current information, acknowledge the limitations.
            When context from previous conversations is provided, consider it in your response.
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
    
    async def answer(self, query, user_id=None, message_history=None):
        """
        Answer a question using knowledge base with context
        
        Args:
            query: String containing the user question
            user_id: User identifier for retrieving memories
            message_history: List of recent messages
            
        Returns:
            String containing the answer
        """
        # Get context if user_id is provided
        context = await get_conversation_context(query, user_id, message_history)
        
        # Create prompt with context and query
        prompt = f"""
{context}

Current date: {datetime.now().strftime('%Y-%m-%d')}
Current time: {datetime.now().strftime('%H:%M:%S')}

User query: {query}

Please provide a knowledgeable response, taking into account any relevant context.
"""
        
        content = types.Content(role='user', parts=[types.Part(text=prompt)])
        events = self.runner.run(
            user_id=self.USER_ID, 
            session_id=self.SESSION_ID, 
            new_message=content
        )
        
        # Get the final response
        final_response = None
        for event in events:
            if event.is_final_response():
                final_response = event.content.parts[0].text
        
        return final_response

# Initialize the web search agent
search_agent = WebSearchAgent()

# Initialize the knowledge base agent
kb_agent = KnowledgeBaseAgent()

class ChatAgent:
    """
    Agent that handles conversational queries with memory
    """
    def __init__(self, mem0_instance):
        """Initialize the chat agent"""
        self.APP_NAME = "chat_agent"
        self.USER_ID = "discord_chat_user"
        self.SESSION_ID = "chat_session"
        self.mem0 = mem0_instance
        
        # Create the agent
        self.agent = Agent(
            name="chat_agent",
            model="gemini-2.0-flash",
            description="Agent to engage in natural conversations with memory.",
            instruction="""You are a conversational assistant that maintains context through memory.
            
            Engage in natural, helpful conversations with users while remembering past interactions.
            Be friendly, empathetic, and personable while providing helpful responses.
            When relevant, refer to past conversations and user preferences that are provided in your context.
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
    
    async def chat(self, query: str, user_id: str) -> str:
        """
        Engage in a conversation using memory for context
        
        Args:
            query: String containing the user query
            user_id: String identifier for the user
            
        Returns:
            String containing the response
        """
        try:
            # Use improved context utility
            context = await get_conversation_context(
                query,
                user_id,
                message_history=user_message_history.get(user_id, []),
                mem0_instance=self.mem0
            )

            prompt = f"""{context}
User says: "{query}"

Please respond as a friendly, helpful assistant. Use both the recent conversation and any relevant long-term memories above to make your reply feel personal, context-aware, and natural. If you remember something useful from the user's history, feel free to mention it!
"""

            # Generate response using the agent
            content = types.Content(role='user', parts=[types.Part(text=prompt)])
            events = self.runner.run(
                user_id=self.USER_ID, 
                session_id=self.SESSION_ID, 
                new_message=content
            )
            
            # Get the final response
            response = None
            for event in events:
                if event.is_final_response():
                    response = event.content.parts[0].text
            
            # Add interaction to memory
            messages = [
                {"role": "user", "content": query},
                {"role": "assistant", "content": response}
            ]
            
            await asyncio.to_thread(self.mem0.add, messages, user_id=user_id)
            
            return response
        
        except Exception as e:
            logger.error(f"Error in chat agent: {e}")
            import traceback
            traceback.print_exc()
            return f"I'm sorry, I encountered an error while processing your request: {str(e)}"

@bot.event
async def on_ready():
    """Event handler for when the bot is ready"""
    global mem0_instance
    
    logger.info(f'{bot.user.name} has connected to Discord!')
    
    # Initialize Mem0
    # mem0_instance = initialize_mem0()
    # if mem0_instance:
    #     logger.info("Memory system initialized successfully")
    # else:
    #     logger.error("Failed to initialize memory system")

# Dictionary to store chat agents for different users
chat_agents = {}

def get_chat_agent(user_id):
    """Get or create a chat agent for a user"""
    global chat_agents, mem0_instance
    
    if user_id not in chat_agents and mem0_instance:
        chat_agents[user_id] = ChatAgent(mem0_instance)
    
    return chat_agents.get(user_id)

# Add a dictionary to store message history by user
user_message_history = {}

@bot.command(name='ask')
async def ask(ctx, *, query):
    """
    Smart query handler - determines the best agent to handle the query
    Usage: !ask [your question]
    """
    # Send initial response
    initial_msg = await ctx.send(f"Processing your query: '{query}'...")
    
    try:
        # Format user ID for Mem0
        discord_user_id = f"discord_{ctx.author.id}"
        
        # Get user's display name
        user_name = ctx.author.display_name
        
        # Initialize or get message history for this user
        if discord_user_id not in user_message_history:
            user_message_history[discord_user_id] = []
        
        # Add current query to history
        user_message_history[discord_user_id].append({
            "role": "user",
            "content": query
        })
        
        # Limit history to last 10 messages
        if len(user_message_history[discord_user_id]) > 10:
            user_message_history[discord_user_id] = user_message_history[discord_user_id][-10:]
        
        # Show typing indicator while processing
        async with ctx.typing():
            # Determine which agent should handle this query
            loop = asyncio.get_event_loop()
            category, explanation = await loop.run_in_executor(None, dispatcher.dispatch, query)
            
            # Logging the decision
            logger.info(f"Query from {user_name}: '{query}' categorized as {category}: {explanation}")
            
            # Handle the query based on the category
            if category == "KNOWLEDGE_BASE":
                # Update the initial message
                await initial_msg.edit(content=f"Answering from knowledge base...")
                
                # Pass context to the knowledge base agent
                response = await kb_agent.answer(
                    query, 
                    user_id=discord_user_id, 
                    message_history=user_message_history[discord_user_id]
                )
                await send_chunked_message(ctx, response)
                
                # Add response to history
                user_message_history[discord_user_id].append({
                    "role": "assistant",
                    "content": response
                })
                
                # Store this interaction in memory too
                if mem0_instance:
                    messages = [
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": response}
                    ]
                    await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
                
            elif category == "WEB_SEARCH":
                # Update the initial message
                await initial_msg.edit(content=f"Searching the web for information...")

                # Use improved context utility for rephrasing
                context = await get_conversation_context(
                    query,
                    discord_user_id,
                    message_history=user_message_history.get(discord_user_id, []),
                    mem0_instance=mem0_instance
                )
                rephrased_query = f"""Given the following context, rephrase the user's question to be as clear and specific as possible for a web search. If the context is helpful, incorporate it into the query. Otherwise, just use the user's question.

{context}

User's original question: "{query}"

Rephrased web search query:"""
                # Use the knowledge base agent to rephrase (or optionally a dedicated rephraser)
                rephrased = await kb_agent.answer(rephrased_query)
                # Use the rephrased query for web search
                response = await search_agent.search(
                    rephrased,
                    user_id=discord_user_id,
                    message_history=user_message_history[discord_user_id]
                )
                await send_chunked_message(ctx, response)
                
                # Add response to history
                user_message_history[discord_user_id].append({
                    "role": "assistant",
                    "content": response
                })
                
                # Store this interaction in memory too
                if mem0_instance:
                    messages = [
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": response}
                    ]
                    await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
                
            elif category == "RESEARCH":
                # Update the initial message
                await initial_msg.edit(content=f"Initiating comprehensive research... (this may take several minutes)")
                
                # Get context for research
                context = await get_conversation_context(query, discord_user_id, user_message_history[discord_user_id])
                
                try:
                    # Pass context to research function with a timeout
                    final_report = await asyncio.wait_for(run_parallel_research(query, context), timeout=180)  # Timeout after 60 seconds
                    
                    await send_chunked_message(ctx, final_report)
                    
                    # Add response to history (shortened version)
                    user_message_history[discord_user_id].append({
                        "role": "assistant",
                        "content": "I've completed a comprehensive research report for you. Here's a summary: " + final_report[:200] + "..."
                    })
                    
                    # Store this interaction in memory too
                    if mem0_instance:
                        messages = [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": "I've completed a comprehensive research report for you. Here's a summary: " + final_report[:200] + "..."}
                        ]
                        await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
                except asyncio.TimeoutError:
                    await ctx.send("Research timed out after 60 seconds. Please try a shorter query or provide more context.")
                    return
                
            elif category == "CHAT":
                # Update the initial message
                await initial_msg.edit(content=f"Let me think about that...")
                
                # Get or create a chat agent for this user
                chat_agent = get_chat_agent(discord_user_id)
                
                if chat_agent:
                    response = await chat_agent.chat(query, discord_user_id)
                    await send_chunked_message(ctx, response)
                    
                    # Add response to history
                    user_message_history[discord_user_id].append({
                        "role": "assistant",
                        "content": response
                    })
                else:
                    # Fallback if chat agent is not available
                    response = await kb_agent.answer(
                        query, 
                        user_id=discord_user_id, 
                        message_history=user_message_history[discord_user_id]
                    )
                    await send_chunked_message(ctx, response)
                    
                    # Add response to history
                    user_message_history[discord_user_id].append({
                        "role": "assistant",
                        "content": response
                    })
                    
                    # Store interaction even in fallback mode if memory is available
                    if mem0_instance:
                        messages = [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": response}
                        ]
                        await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
            
            else:
                # Should not happen given our dispatcher design, but just in case
                await initial_msg.edit(content=f"Using default handling method...")
                
                response = await kb_agent.answer(
                    query, 
                    user_id=discord_user_id, 
                    message_history=user_message_history[discord_user_id]
                )
                await send_chunked_message(ctx, response)
                
                # Add response to history
                user_message_history[discord_user_id].append({
                    "role": "assistant",
                    "content": response
                })
                
                # Store this interaction in memory too
                if mem0_instance:
                    messages = [
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": response}
                    ]
                    await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
    
    except Exception as e:
        await ctx.send(f"An error occurred while processing your query: {str(e)}")
        logger.error(f"Error processing query: {e}")
        import traceback
        traceback.print_exc()

async def send_chunked_message(ctx, message):
    """
    Sends a message in chunks to avoid Discord's 2000 character limit
    """
    if not message:
        await ctx.send("No response generated.")
        return
        
    if len(message) <= 1900:
        await ctx.send(message)
    else:
        # Split into multiple messages
        chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
        await ctx.send(f"Response (part 1/{len(chunks)}):")
        await ctx.send(chunks[0])
        
        for i, chunk in enumerate(chunks[1:], 2):
            await ctx.send(f"Part {i}/{len(chunks)}:")
            await ctx.send(chunk)

@bot.command(name='force_search')
async def force_search(ctx, *, query):
    """
    Force the bot to use the web search agent
    Usage: !force_search [query]
    """
    await ctx.send(f"Searching the web for: {query}...")
    
    try:
        # Format user ID for Mem0
        discord_user_id = f"discord_{ctx.author.id}"
        
        # Initialize or get message history for this user
        if discord_user_id not in user_message_history:
            user_message_history[discord_user_id] = []
        
        # Add current query to history
        user_message_history[discord_user_id].append({
            "role": "user",
            "content": f"[Web search] {query}"
        })
        
        # Use improved context utility for rephrasing
        context = await get_conversation_context(
            query,
            discord_user_id,
            message_history=user_message_history.get(discord_user_id, []),
            mem0_instance=mem0_instance
        )
        rephrased_query = f"""Given the following context, rephrase the user's question to be as clear and specific as possible for a web search. If the context is helpful, incorporate it into the query. Otherwise, just use the user's question.

{context}

User's original question: "{query}"

Rephrased web search query:"""
        rephrased = await kb_agent.answer(rephrased_query)
        search_result = await search_agent.search(
            rephrased,
            user_id=discord_user_id,
            message_history=user_message_history[discord_user_id]
        )
        await send_chunked_message(ctx, search_result)
        
        # Add response to history
        user_message_history[discord_user_id].append({
            "role": "assistant",
            "content": search_result
        })
        
        # Store this interaction in memory
        if mem0_instance:
            messages = [
                {"role": "user", "content": f"[Web search query] {query}"},
                {"role": "assistant", "content": search_result[:500] + "..." if len(search_result) > 500 else search_result}
            ]
            await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
    
    except Exception as e:
        await ctx.send(f"An error occurred during web search: {str(e)}")

@bot.command(name='force_research')
async def force_research(ctx, *, research_goal):
    """
    Force the bot to use the research agent
    Usage: !force_research [research goal]
    """
    await ctx.send(f"Starting research on: {research_goal}\nThis may take a few minutes...")
    
    try:
        # Format user ID for Mem0
        discord_user_id = f"discord_{ctx.author.id}"
        
        # Initialize or get message history for this user
        if discord_user_id not in user_message_history:
            user_message_history[discord_user_id] = []
        
        # Add current query to history
        user_message_history[discord_user_id].append({
            "role": "user",
            "content": f"[Research] {research_goal}"
        })
        
        # Get context for research
        context = await get_conversation_context(research_goal, discord_user_id, user_message_history[discord_user_id])
        
        # Pass context to research function
        final_report = await run_parallel_research(research_goal, context)
        await send_chunked_message(ctx, final_report)
        
        # Add response to history (shortened version)
        user_message_history[discord_user_id].append({
            "role": "assistant",
            "content": "I've completed a comprehensive research report for you. Here's a summary: " + final_report[:200] + "..."
        })
        
        # Store this interaction in memory
        if mem0_instance:
            messages = [
                {"role": "user", "content": f"[Research request] {research_goal}"},
                {"role": "assistant", "content": "I've completed a comprehensive research report for you. Here's a summary: " + final_report[:200] + "..."}
            ]
            await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
    
    except Exception as e:
        await ctx.send(f"An error occurred during research: {str(e)}")

@bot.command(name='force_knowledge')
async def force_knowledge(ctx, *, query):
    """
    Force the bot to use the knowledge base agent
    Usage: !force_knowledge [query]
    """
    await ctx.send(f"Answering from knowledge base...")
    
    try:
        # Format user ID for Mem0
        discord_user_id = f"discord_{ctx.author.id}"
        
        # Initialize or get message history for this user
        if discord_user_id not in user_message_history:
            user_message_history[discord_user_id] = []
        
        # Add current query to history
        user_message_history[discord_user_id].append({
            "role": "user",
            "content": query
        })
        
        # Use knowledge base agent with context
        response = await kb_agent.answer(
            query, 
            user_id=discord_user_id, 
            message_history=user_message_history[discord_user_id]
        )
        await send_chunked_message(ctx, response)
        
        # Add response to history
        user_message_history[discord_user_id].append({
            "role": "assistant",
            "content": response
        })
        
        # Store this interaction in memory
        if mem0_instance:
            messages = [
                {"role": "user", "content": query},
                {"role": "assistant", "content": response}
            ]
            await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
    
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command(name='direct_chat')
async def direct_chat(ctx):
    """
    Enable direct chat mode in the current channel (no command prefix needed)
    """
    channel_id = ctx.channel.id
    await ctx.send("Direct chat mode activated in this channel. Just type normally to chat with the bot. Use commands with the ! prefix if needed.")
    
    @bot.listen('on_message')
    async def direct_chat_handler(message):
        # Only process messages in the activated channel that aren't from the bot
        if message.channel.id != channel_id or message.author == bot.user:
            return
        
        # Ignore messages that start with ! (commands)
        if message.content.startswith('!'):
            return
            
        # Process the message as a query
        async with message.channel.typing():
            # Format user ID for Mem0
            discord_user_id = f"discord_{message.author.id}"
            
            # Initialize or get message history for this user
            if discord_user_id not in user_message_history:
                user_message_history[discord_user_id] = []
            
            # Add current query to history
            query = message.content
            user_message_history[discord_user_id].append({
                "role": "user",
                "content": query
            })
            
            # Limit history to last 10 messages
            if len(user_message_history[discord_user_id]) > 10:
                user_message_history[discord_user_id] = user_message_history[discord_user_id][-10:]
            
            # Use the ask command's logic
            try:
                # Determine which agent should handle this query
                loop = asyncio.get_event_loop()
                category, explanation = await loop.run_in_executor(None, dispatcher.dispatch, query)
                
                # Handle based on category (similar to ask command)
                if category == "CHAT":
                    chat_agent = get_chat_agent(discord_user_id)
                    if chat_agent:
                        response = await chat_agent.chat(query, discord_user_id)
                    else:
                        response = await kb_agent.answer(
                            query, 
                            user_id=discord_user_id, 
                            message_history=user_message_history[discord_user_id]
                        )
                        # Store interaction in fallback mode
                        if mem0_instance:
                            messages = [
                                {"role": "user", "content": query},
                                {"role": "assistant", "content": response}
                            ]
                            await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
                
                elif category == "KNOWLEDGE_BASE":
                    response = await kb_agent.answer(
                        query, 
                        user_id=discord_user_id, 
                        message_history=user_message_history[discord_user_id]
                    )
                    # Store interaction
                    if mem0_instance:
                        messages = [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": response}
                        ]
                        await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
                
                elif category == "WEB_SEARCH":
                    response = await search_agent.search(
                        query, 
                        user_id=discord_user_id, 
                        message_history=user_message_history[discord_user_id]
                    )
                    # Store interaction
                    if mem0_instance:
                        messages = [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": response}
                        ]
                        await asyncio.to_thread(mem0_instance.add, messages, user_id=discord_user_id)
                
                elif category == "RESEARCH":
                    await message.reply("This query requires in-depth research. Please use the `!ask` or `!force_research` command instead.")
                    return
                
                # Add response to message history
                user_message_history[discord_user_id].append({
                    "role": "assistant",
                    "content": response
                })
                
                # Send the response in chunks
                if len(response) <= 1900:
                    await message.reply(response)
                else:
                    chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await message.reply(f"{chunk}\n(1/{len(chunks)})")
                        else:
                            await message.channel.send(f"{chunk}\n({i+1}/{len(chunks)})")
            
            except Exception as e:
                await message.reply(f"An error occurred: {str(e)}")
                logger.error(f"Error in direct chat: {e}")
                import traceback
                traceback.print_exc()

@bot.command(name='memory_status')
async def memory_status(ctx):
    """
    Check the status of the memory system
    """
    # Format user ID for Mem0
    discord_user_id = f"discord_{ctx.author.id}"
    
    # Check Mem0 status
    if mem0_instance:
        try:
            # Get memory count for this user from Mem0
            memory_count = await asyncio.to_thread(
                mem0_instance.search, 
                query="status check", 
                limit=100, 
                user_id=discord_user_id
            )
            
            # Check recent message history
            recent_messages_count = 0
            if discord_user_id in user_message_history:
                recent_messages_count = len(user_message_history[discord_user_id])
            
            status_message = "Memory System Status:\n"
            status_message += f"- Long-term memory (Mem0): {len(memory_count) if memory_count else 0} memories\n"
            status_message += f"- Recent message history: {recent_messages_count} messages\n"
            
            await ctx.send(status_message)
        except Exception as e:
            await ctx.send(f"Memory system is active but encountered an error: {str(e)}")
    else:
        await ctx.send("Memory system is not active ❌")

@bot.command(name='clear_memory')
async def clear_memory(ctx):
    """
    Clear the memory for the current user
    """
    # Format user ID for Mem0
    discord_user_id = f"discord_{ctx.author.id}"
    
    # Clear message history
    if discord_user_id in user_message_history:
        user_message_history[discord_user_id] = []
        message = "Recent message history cleared. "
    else:
        message = "No recent message history found. "
    
    # Try to clear Mem0 memories
    if mem0_instance:
        try:
            # Note: If Mem0 supports a delete operation by user_id, use it here
            # This is a placeholder - implement based on actual Mem0 API
            await ctx.send(f"{message}Long-term memory (Mem0) clearing is not yet implemented.")
            
        except Exception as e:
            await ctx.send(f"{message}Failed to clear long-term memory: {str(e)}")
    else:
        await ctx.send(f"{message}Long-term memory system is not active.")

@bot.command(name='bot_help')
async def bot_help(ctx):
    """Provides help information for the bot commands"""
    help_text = """
**Smart Research Bot with Memory Commands**

**!ask [query]**
Main command - automatically selects the best agent for your query
Example: `!ask What are the economic implications of tariffs?`

**!force_search [query]**
Forces the use of the web search agent
Example: `!force_search current weather in New York`

**!force_research [topic]**
Forces the use of the research agent for in-depth reports
Example: `!force_research Impact of AI on healthcare`

**!force_knowledge [query]**
Forces the use of the knowledge base agent
Example: `!force_knowledge Who was Marie Curie?`

**!direct_chat**
Enables conversation mode in the current channel (no need for command prefix)

**!memory_status**
Checks the status of your conversation memory (both recent and long-term)

**!clear_memory**
Clears your recent conversation history

**!bot_help**
Shows this help message

**Context Awareness**
The bot remembers your conversation history for more natural interactions:
- Recent context: Last 3 messages in the current conversation
- Long-term memory: Important information from past conversations
"""
    await ctx.send(help_text)

# Run the bot
def main():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
