import asyncio
from datetime import datetime

async def get_conversation_context(query, user_id, message_history=None, mem0_instance=None):
    """
    Get conversation context from both Mem0 and recent message history, formatted for user-friendly and memory-friendly prompts.
    
    Args:
        query: The current user query
        user_id: The user's ID
        message_history: List of recent messages (optional)
        mem0_instance: The memory instance (optional)
        
    Returns:
        String containing formatted context
    """
    context = "👋 Hi! Here's some context to help our conversation feel more natural and personal.\n\n"

    # Part 1: Add recent message history (last 5 messages)
    if message_history and len(message_history) > 0:
        context += "🗨️ **Recent Conversation (last 5 messages):**\n"
        recent_messages = message_history[-5:] if len(message_history) >= 5 else message_history
        for msg in recent_messages:
            if 'role' in msg and 'content' in msg:
                context += f"- {msg['role'].capitalize()}: {msg['content']}\n"
    else:
        context += "🗨️ No recent conversation history found.\n"

    # Part 2: Get relevant memories from Mem0 (up to 5)
    if mem0_instance:
        try:
            relevant_memories = await asyncio.to_thread(
                mem0_instance.search, 
                query=query, 
                limit=5,
                user_id=user_id
            )
            if relevant_memories:
                context += "\n🧠 **Relevant Memories:**\n"
                for mem in relevant_memories:
                    if isinstance(mem, dict) and 'content' in mem:
                        context += f"- {mem['content']}\n"
                    elif isinstance(mem, dict) and 'role' in mem and 'content' in mem:
                        context += f"- {mem['role'].capitalize()}: {mem['content']}\n"
                    elif isinstance(mem, list):
                        for item in mem:
                            if isinstance(item, dict) and 'role' in item and 'content' in item:
                                context += f"- {item['role'].capitalize()}: {item['content']}\n"
                    else:
                        context += f"- Memory: {str(mem)[:100]}...\n"
            else:
                context += "\n🧠 No relevant long-term memories found.\n"
        except Exception as e:
            context += f"\nNote: Could not retrieve memories: {str(e)}\n"
    else:
        context += "\n🧠 No relevant long-term memories found.\n"

    # Optionally, add current date/time for context
    context += f"\nToday's date: {datetime.now().strftime('%Y-%m-%d')}\nCurrent time: {datetime.now().strftime('%H:%M:%S')}\n"

    return context
