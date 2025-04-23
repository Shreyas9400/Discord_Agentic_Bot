import asyncio
import json
import re
import uuid
from datetime import datetime

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

from searxng_client import SearXNGClient

GEMINI_MODEL = "gemini-2.0-flash-exp"
APP_NAME = "parallel_research_app"
USER_ID = "research_user_01"

searxng_client = SearXNGClient(searxng_instance="http://searxng:8080", verify_ssl=False)

def make_query_agent():
    return LlmAgent(
        name=f"QueryGen_{uuid.uuid4().hex[:8]}",
        model=GEMINI_MODEL,
        instruction="""
You are an advanced research analyst. Your job is to break down the user's research goal into 1-2 highly analytical, multi-perspective web search queries.
- Each query should target a different angle, stakeholder, or aspect of the topic (e.g., economic, political, social, technological, historical, etc).
- Avoid redundancy and ensure coverage of both factual and analytical dimensions.
Return a JSON object:
{"queries": ["query1", "query2"]}
""",
        description="Generates analytical, multi-perspective search queries."
    )

def make_search_agent(query):
    async def searxng_search(q: str) -> dict:
        """Web search using SearXNG."""
        try:
            return await asyncio.wait_for(searxng_client.search_and_scrape(q, max_results=5), timeout=30)
        except Exception as e:
            return {"error": str(e), "query": q}
    return LlmAgent(
        name=f"Search_{uuid.uuid4().hex[:8]}",
        model=GEMINI_MODEL,
        instruction=f"""
You are an expert research analyst. You have been assigned the following research query:
"{query}"

Your task:
- Carefully review the search results and their content.
- Extract not only key facts, but also analysis, competing perspectives, implications, and any controversies or debates.
- Identify trends, causal relationships, and broader context.
- **Highlight any data, statistics, numbers, percentages, dates, or quantitative evidence.**
- For each learning, if possible, include the relevant number or statistic and its context.
- Note any gaps, uncertainties, or areas needing further research.

Return a JSON object:
{{
  "learnings": [
    "Analytical insight, fact, or perspective 1 (with data: e.g. 'GDP fell by 2% in 2020')",
    "Analytical insight, fact, or perspective 2 (with data)",
    "Implication, controversy, or trend 3"
  ],
  "source_urls": [
    "https://source1.com",
    "https://source2.com"
  ]
}}
""",
        description=f"Analytical search and synthesis for: {query}",
        tools=[searxng_search]
    )

def make_report_agent():
    return LlmAgent(
        name=f"ReportGen_{uuid.uuid4().hex[:8]}",
        model=GEMINI_MODEL,
        instruction="""
You are an expert research report writer. Given a research goal, a set of analytical findings, and a list of source URLs, write a comprehensive, academic-style research report.

Your report must include the following sections:
1. Executive Summary (1-2 paragraphs summarizing the most important findings and implications)
2. Introduction (background, context, and significance of the research topic)
3. Methodology (how the research was conducted, sources used, and any limitations)
4. Detailed Findings (organized by theme or perspective, with data, analysis, and multiple viewpoints; **emphasize all numerical/statistical evidence**)
5. Analysis (synthesize findings, discuss trends, controversies, and causal relationships)
6. Implications (broader impact, policy or practical implications, future outlook)
7. Recommendations (actionable suggestions or further research directions)
8. Conclusion (summarize key insights and final thoughts)
9. Sources (list all URLs or references used, one per line)

- Use clear Markdown formatting with headings, bullet points, and block quotes for key evidence.
- **Explicitly include and highlight all numbers, statistics, percentages, and quantitative evidence found.**
- Make the report suitable for an expert or academic audience.
""",
        description="Writes a detailed, analytical research report with sources and data."
    )

def extract_json(text, key="queries"):
    # Extract JSON with the specified key from text
    try:
        match = re.search(r'```json\s*({[\s\S]*?})\s*```|({[\s\S]*})', text)
        if match:
            json_str = next(g for g in match.groups() if g)
            obj = json.loads(json_str)
            if key in obj:
                return obj[key]
        # fallback: try to parse any JSON
        obj = json.loads(text)
        if key in obj:
            return obj[key]
    except Exception:
        pass
    return []

def extract_learnings_and_urls(text):
    try:
        match = re.search(r'```json\s*({[\s\S]*?})\s*```|({[\s\S]*})', text)
        if match:
            json_str = next(g for g in match.groups() if g)
            obj = json.loads(json_str)
            learnings = obj.get("learnings", [])
            urls = obj.get("source_urls", [])
            return learnings, urls
        obj = json.loads(text)
        learnings = obj.get("learnings", [])
        urls = obj.get("source_urls", [])
        return learnings, urls
    except Exception:
        return [text[:300]], []

async def run_parallel_research(research_goal, context="", on_progress=None):
    session_id = str(uuid.uuid4())
    session_service = InMemorySessionService()
    session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    # 1. Generate queries
    prompt = f"{context}\n\nResearch Goal: {research_goal}\nGenerate search queries."
    query_agent = make_query_agent()
    runner = Runner(agent=query_agent, app_name=APP_NAME, session_service=session_service)
    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    query_response = await asyncio.to_thread(
        lambda: next(
            e.content.parts[0].text
            for e in runner.run(
                user_id=USER_ID,
                session_id=session_id,
                new_message=content
            )
            if e.is_final_response()
        )
    )
    queries = extract_json(query_response, key="queries")
    if not queries:
        queries = [research_goal]
    # Limit to 2 queries to avoid quota exhaustion
    queries = queries[:2]

    progress = {
        "currentDepth": 1,
        "totalDepth": 1,
        "currentBreadth": len(queries),
        "totalBreadth": len(queries),
        "currentQuery": "",
        "totalQueries": len(queries),
        "completedQueries": 0,
    }
    if on_progress:
        await maybe_await(on_progress(progress))

    # 2. Parallel search
    search_agents = [make_search_agent(q) for q in queries]
    parallel_agent = ParallelAgent(name=f"Parallel_{uuid.uuid4().hex[:8]}", sub_agents=search_agents)
    search_runner = Runner(agent=parallel_agent, app_name=APP_NAME, session_service=session_service)
    search_content = types.Content(role='user', parts=[types.Part(text="Do your assigned search and summarize findings.")])
    search_results = await asyncio.to_thread(
        lambda: [
            e.content.parts[0].text
            for e in search_runner.run(
                user_id=USER_ID,
                session_id=session_id,
                new_message=search_content
            )
            if e.is_final_response()
        ]
    )

    # Progress update after search
    progress["completedQueries"] = len(queries)
    if on_progress:
        await maybe_await(on_progress(progress))

    # 3. Collect learnings and source URLs (only from successfully scraped content)
    all_learnings = []
    all_urls = set()  # Use set to automatically handle duplicates
    
    for result_text in search_results:
        # Extract learnings and URLs from the agent's response
        learnings, potential_urls = extract_learnings_and_urls(result_text)
        all_learnings.extend(learnings)

        # Check if the result text contains scraped content info
        try:
            result_data = json.loads(result_text)
            if isinstance(result_data, dict):
                # Extract URLs from scraped content
                if "organic" in result_data:
                    for item in result_data["organic"]:
                        if isinstance(item, dict):
                            scraped = item.get("scraped_content", {})
                            if scraped.get("success", False) and scraped.get("url"):
                                all_urls.add(scraped["url"])
        except json.JSONDecodeError:
            pass

        # Also add any URLs from the agent's response that were successfully scraped
        for url in potential_urls:
            try:
                result_data = json.loads(result_text)
                if isinstance(result_data, dict) and "organic" in result_data:
                    for item in result_data["organic"]:
                        if isinstance(item, dict):
                            scraped = item.get("scraped_content", {})
                            if (scraped.get("success", False) and 
                                scraped.get("url") == url):
                                all_urls.add(url)
            except json.JSONDecodeError:
                pass

    # Convert set back to sorted list
    all_urls = sorted(u for u in all_urls if u)

    # 4. Synthesize report (pass URLs as well)
    report_input = (
        f"Research Goal: {research_goal}\n\n"
        f"Findings:\n" + "\n".join(f"- {l}" for l in all_learnings)
    )
    report_agent = make_report_agent()
    report_runner = Runner(agent=report_agent, app_name=APP_NAME, session_service=session_service)
    report_content = types.Content(role='user', parts=[types.Part(text=report_input)])
    report = await asyncio.to_thread(
        lambda: next(
            e.content.parts[0].text
            for e in report_runner.run(
                user_id=USER_ID,
                session_id=session_id,
                new_message=report_content
            )
            if e.is_final_response()
        )
    )
    # Always append sources as Markdown list at the end
    if all_urls:
        report += "\n\n## Sources\n" + "\n".join(f"- {url}" for url in all_urls)
    return report

# Utility to support both sync and async progress callbacks
async def maybe_await(result):
    if asyncio.iscoroutine(result):
        await result

# Stubs for compatibility
async def deep_research_agent(*args, **kwargs):
    return {"learnings": [], "visited_urls": [], "error": "deep_research_agent not implemented"}

async def write_final_report(*args, **kwargs):
    return "Final report generation is not implemented."

if __name__ == "__main__":
    async def main():
        report = await run_parallel_research("Impact of tariffs on China led by Trump, also explain about the current tariff rates")
        print(report)
    asyncio.run(main())
