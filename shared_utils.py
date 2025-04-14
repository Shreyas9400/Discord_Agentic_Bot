import asyncio
from datetime import datetime  # Add this import

async def get_conversation_context(query, user_id, message_history=None, mem0_instance=None):
    """
    Get conversation context from both Mem0 and recent message history
    
    Args:
        query: The current user query
        user_id: The user's ID
        message_history: List of recent messages (optional)
        mem0_instance: The memory instance (optional)
        
    Returns:
        String containing formatted context
    """
    context = "Previous conversation context:\n"
    
    # Part 1: Get relevant memories from Mem0
    if mem0_instance:
        try:
            relevant_memories = await asyncio.to_thread(
                mem0_instance.search, 
                query=query, 
                limit=3,  # Get 3 most relevant memories
                user_id=user_id
            )
            
            if relevant_memories:
                context += "\nRelevant memory context:\n"
                for mem in relevant_memories:
                    # Check for the structure of the returned memory
                    if isinstance(mem, dict) and 'content' in mem:
                        context += f"- {mem['content']}\n"
                    elif isinstance(mem, dict) and 'role' in mem and 'content' in mem:
                        context += f"- {mem['role']}: {mem['content']}\n"
                    elif isinstance(mem, list):
                        for item in mem:
                            if isinstance(item, dict) and 'role' in item and 'content' in item:
                                context += f"- {item['role']}: {item['content']}\n"
                    else:
                        context += f"- Memory: {str(mem)[:100]}...\n"
        except Exception as e:
            context += f"\nNote: Could not retrieve memories: {str(e)}\n"
    
    # Part 2: Add recent message history (last 3 messages)
    if message_history and len(message_history) > 0:
        context += "\nRecent conversation history:\n"
        # Get the last 3 messages (or fewer if not available)
        recent_messages = message_history[-3:] if len(message_history) >= 3 else message_history
        for msg in recent_messages:
            if 'role' in msg and 'content' in msg:
                context += f"- {msg['role']}: {msg['content']}\n"
    
    return context
