from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.tools import google_search
from google.genai import types
import json
from datetime import datetime

APP_NAME = "parallel_research_app"
USER_ID = "research_user_01"
SESSION_ID = "parallel_research_session"
GEMINI_MODEL = "gemini-2.0-flash-exp"

# --- Define New Research Agents ---

# Agent 1: Query Generation Agent
query_generation_agent = LlmAgent(
    name="QueryGenerationAgent",
    model=GEMINI_MODEL,
    instruction="""You are an AI Query Generation Assistant.
    
    Your task is to decide WHAT to search for next based on the current research goal.
    Generate a list of specific Search Engine Results Page (SERP) queries.
    
    For each query, define a researchGoal that outlines what you expect to find and potential next steps.
    
    Output a JSON object with the following structure:
    {
        "queries": [
            {
                "query": "specific search term 1",
                "researchGoal": "what I expect to find with this query and how it relates to the overall research"
            },
            {
                "query": "specific search term 2",
                "researchGoal": "what I expect to find with this query and how it relates to the overall research"
            }
        ]
    }
    
    Adapt your queries based on any accumulated knowledge from previous searches.
    """,
    description="Generates search queries based on research goals and previous learnings."
)

# Agent 2: Search and Process Agent Template
def create_search_agent(query, index):
    """Creates a search agent for a specific query"""
    return LlmAgent(
        name=f"SearchAndProcessAgent_{index}",
        model=GEMINI_MODEL,
        instruction=f"""You are an AI Search and Process Assistant.
        
        Search Query: "{query}"
        
        Your task is to:
        1. Use the Google Search tool to search for the assigned query
        2. Process the results to extract valuable information
        3. Organize the learnings in a structured way
        
        Output a JSON object with the following structure:
        {{
            "learnings": [
                "Concise fact or insight 1",
                "Concise fact or insight 2",
                "Concise fact or insight 3"
            ],
            "follow_up_questions": [
                "Specific question for further research 1",
                "Specific question for further research 2"
            ]
        }}
        
        For learnings, provide detailed, information-rich insights rather than general observations.
        Include specific data points, statistics, expert opinions, and factual findings whenever possible.
        
        Focus on extracting factual information most relevant to the research goal.
        """,
        description=f"Searches and processes results for: {query}",
        tools=[google_search]
    )

# Agent 3: Report Generator Agent
report_generator_agent = LlmAgent(
    name="ReportGeneratorAgent",
    model=GEMINI_MODEL,
    instruction="""You are an AI Report Generation Assistant tasked with creating an in-depth, comprehensive research report.
    
    Your report should be thorough, detailed, and academic in nature - similar to a well-researched white paper or policy brief.
    
    Structure your report with the following comprehensive sections:
    
    1. Executive Summary
       - A detailed overview of key findings (1-2 paragraphs)
       - The most significant implications identified in your research
    
    2. Introduction
       - Background context on the research topic
       - The significance and relevance of this topic
       - Scope of the analysis
    
    3. Methodology
       - Brief explanation of how information was gathered and synthesized
    
    4. Detailed Findings (organize into relevant subsections)
       - Economic impacts (with data points whenever available)
       - Policy implications
       - Industry-specific effects
       - Consumer impacts
       - International relations aspects
       - Short-term vs. long-term effects
    
    5. Analysis
       - Critical examination of competing perspectives
       - Evaluation of the evidence
       - Identification of knowledge gaps or limitations
    
    6. Implications
       - Broader economic, political, and social consequences
       - Potential future scenarios
    
    7. Recommendations
       - Policy suggestions based on the evidence
       - Areas requiring further research
    
    8. Conclusion
       - Synthesis of key insights
       - Final assessment of the research question
    
    Use proper Markdown formatting with:
    - Main sections as # headers
    - Subsections as ## and ### headers
    - Bullet points for lists
    - *Italics* and **bold** for emphasis on key points
    - Block quotes for important citations or observations
    
    Make the report detailed and substantive - aim for a comprehensive analysis that would satisfy an expert audience.
    
    Balance factual reporting with insightful analysis. Connect individual data points into broader patterns and narratives.
    Use an academic, professional tone while ensuring the content remains accessible.
    """,
    description="Creates a comprehensive, detailed research report based on all findings."
)

# --- Main execution function ---
def run_parallel_research(research_goal, context=""):
    """
    Main function to execute the parallel research process
    
    Args:
        research_goal: The research question or goal
        context: Optional conversation context to include
    """
    session_service = InMemorySessionService()
    session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    
    # Initialize state
    all_learnings = []
    query_research_goals = {}
    
    # Add context to the research goal if provided
    if context:
        research_prompt = f"""
{context}

Current date: {datetime.now().strftime('%Y-%m-%d')}
Current time: {datetime.now().strftime('%H:%M:%S')}

Research Goal: {research_goal}

Please conduct research based on this goal, taking into account any relevant context.
"""
    else:
        research_prompt = f"Research Goal: {research_goal}\n\nGenerate search queries to help research this topic thoroughly."

    # Step 1: Generate initial queries
    initial_content = types.Content(
        role='user', 
        parts=[types.Part(text=research_prompt)]
    )
    
    # Create initial ParallelAgent with just the query generator
    parallel_agent = ParallelAgent(
        name="ParallelWebResearchAgent",
        sub_agents=[query_generation_agent]
    )
    
    runner = Runner(agent=parallel_agent, app_name=APP_NAME, session_service=session_service)
    
    # Run query generation and capture response
    query_generation_response = None
    events = runner.run(
        user_id=USER_ID, 
        session_id=SESSION_ID, 
        new_message=initial_content
    )
    
    for event in events:
        if event.is_final_response():
            query_generation_response = event.content.parts[0].text
            print("Query Generator Response:", query_generation_response)
    
    # Extract generated queries from response
    queries = []
    try:
        # Try to find JSON in the response
        import re
        json_match = re.search(r'({[\s\S]*})', query_generation_response)
        if json_match:
            query_result = json.loads(json_match.group(1))
            queries = query_result.get("queries", [])
            
            # Store research goals for each query
            for query_item in queries:
                if isinstance(query_item, dict) and "query" in query_item and "researchGoal" in query_item:
                    query_research_goals[query_item["query"]] = query_item["researchGoal"]
    except Exception as e:
        print(f"Error extracting queries: {e}")
        # Fallback - create some default queries
        queries = [
            {"query": f"{research_goal} overview"},
            {"query": f"{research_goal} analysis"},
            {"query": f"{research_goal} impact"}
        ]
    
    # Step 2: For each query, create a specific search agent instance and execute
    search_results_by_query = {}
    for i, query_item in enumerate(queries):
        query = query_item.get("query") if isinstance(query_item, dict) else query_item
        
        # Create specific search agent for this query
        search_agent = create_search_agent(query, i)
        
        # Create new ParallelAgent with just this search agent
        search_parallel_agent = ParallelAgent(
            name="SingleSearchAgent",
            sub_agents=[search_agent]
        )
        
        search_runner = Runner(
            agent=search_parallel_agent, 
            app_name=APP_NAME, 
            session_service=session_service
        )
        
        # Run the search
        search_content = types.Content(
            role='user', 
            parts=[types.Part(text=f"Search for: {query} related to the research goal: {research_goal}")]
        )
        
        search_result_text = None
        search_events = search_runner.run(
            user_id=USER_ID, 
            session_id=SESSION_ID, 
            new_message=search_content
        )
        
        for event in search_events:
            if event.is_final_response():
                search_result_text = event.content.parts[0].text
                print(f"Search Agent {i} Response:", search_result_text[:100] + "..." if len(search_result_text) > 100 else search_result_text)
        
        # Extract learnings from the search response
        try:
            # Try to find JSON in the response
            import re
            json_match = re.search(r'({[\s\S]*})', search_result_text)
            if json_match:
                search_result = json.loads(json_match.group(1))
                if "learnings" in search_result:
                    # Store the learnings by query for better organization
                    search_results_by_query[query] = search_result["learnings"]
                    all_learnings.extend(search_result["learnings"])
            else:
                # If no JSON found, extract text as is
                learning = f"From search '{query}': {search_result_text[:200]}..."
                search_results_by_query[query] = [learning]
                all_learnings.append(learning)
        except Exception as e:
            print(f"Error extracting learnings from search {i}: {e}")
            # Add the raw text as a fallback
            if search_result_text:
                learning = f"From search '{query}': {search_result_text[:200]}..."
                search_results_by_query[query] = [learning]
                all_learnings.append(learning)
    
    # Step 3: Generate final report
    # Prepare a message with all the accumulated learnings in an organized fashion
    
    # Build a structured report input with organized learnings by topic/query
    report_input = f"""
# Research Report Input: {research_goal}

## Research Questions and Findings

"""
    
    # Add each query and its findings in an organized way
    for query, learnings in search_results_by_query.items():
        research_goal_text = query_research_goals.get(query, "")
        report_input += f"### Query: {query}\n"
        if research_goal_text:
            report_input += f"**Research Goal**: {research_goal_text}\n\n"
        report_input += "**Findings**:\n"
        for learning in learnings:
            report_input += f"- {learning}\n"
        report_input += "\n"
    
    # Add context to the final report generation if provided
    if context:
        final_prompt = f"""
{context}

Create a comprehensive, detailed research report on the following topic:

RESEARCH GOAL: {research_goal}

The report should be thorough, academic in style, and cover all relevant aspects of this topic.
Please synthesize the following research findings into a cohesive, well-structured report while considering the context provided:

{report_input}

Your report should be substantial and comprehensive, covering the topic from multiple angles.
Balance factual reporting with insightful analysis and provide a nuanced perspective on the topic.
"""
    else:
        final_prompt = f"""
Create a comprehensive, detailed research report on the following topic:

RESEARCH GOAL: {research_goal}

The report should be thorough, academic in style, and cover all relevant aspects of this topic.
Please synthesize the following research findings into a cohesive, well-structured report:

{report_input}

Your report should be substantial and comprehensive, covering the topic from multiple angles.
Balance factual reporting with insightful analysis and provide a nuanced perspective on the topic.
"""
    
    final_content = types.Content(
        role='user', 
        parts=[types.Part(text=final_prompt)]
    )
    
    final_parallel_agent = ParallelAgent(
        name="FinalReportAgent",
        sub_agents=[report_generator_agent]
    )
    
    final_runner = Runner(
        agent=final_parallel_agent, 
        app_name=APP_NAME, 
        session_service=session_service
    )
    
    final_report = None
    final_events = final_runner.run(
        user_id=USER_ID, 
        session_id=SESSION_ID, 
        new_message=final_content
    )
    
    for event in final_events:
        if event.is_final_response():
            final_report = event.content.parts[0].text
            print("Report Generator Response Length:", len(final_report))
    
    return final_report

# Example usage
if __name__ == "__main__":
    research_goal = "Impact of tariffs on China led by Trump, also explain about the current tariff rates"
    final_report = run_parallel_research(research_goal)
    print("\nFINAL RESEARCH REPORT:")
    print(final_report)
