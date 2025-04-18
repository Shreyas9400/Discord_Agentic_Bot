import asyncio
import os
import sys
from dotenv import load_dotenv
from parallel_research_agent import run_parallel_research

# Load environment variables
load_dotenv()

# Explicitly set the Google API key for ADK
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env or environment")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY  # Required by Google ADK

# Make sure SearXNG instance is available or set custom instance
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888")
os.environ["SEARXNG_URL"] = SEARXNG_URL

async def test_parallel_research():
    """Test the parallel research agent with a complex research question"""
    
    # Choose a research topic that might be less likely to trigger rate limits
    # Avoiding highly popular topics might help reduce the chance of rate limiting
    research_goal = "Analyze the impact of tariffs on China led by Trump administration"
    
    print(f"Running parallel research for goal: {research_goal}\n")
    print("This may take a few minutes as multiple searches and LLM calls are being executed...\n")
    
    # Simple context to guide the research
    context = """
    I'm researching the economic effects of trade policies.
    Focus on the tariffs imposed on Chinese goods and their impact on both economies.
    Include information about current tariff rates if available.
    """
    
    try:
        # Execute the parallel research with a timeout
        research_report = await asyncio.wait_for(
            run_parallel_research(research_goal, context),
            timeout=300  # 5 minute timeout
        )
        
        print("\n=== RESEARCH REPORT SUMMARY ===")
        # Print just the executive summary to keep console output manageable
        if "# Executive Summary" in research_report:
            summary_start = research_report.find("# Executive Summary")
            next_section = research_report.find("#", summary_start + 1)
            if next_section > 0:
                print(research_report[summary_start:next_section])
            else:
                print(research_report[summary_start:])
        else:
            # Print first 500 characters if no executive summary found
            print(research_report[:500] + "...\n")
        
        print("\n=== Full report length: {} characters ===".format(len(research_report)))
        
        # Save the report to a file
        filename = "tariffs_research_report.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(research_report)
        print(f"Full report saved to {filename}")
        
        return research_report
        
    except asyncio.TimeoutError:
        print("Research process timed out after 5 minutes")
        return "Research timed out"
    except Exception as e:
        print(f"Error during research: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Research failed: {str(e)}"

# Alternative simpler test that doesn't use as many search queries
async def test_minimal_research():
    """A simpler test with minimal search requirements"""
    research_goal = "Analyze the impact of tariffs on China led by Trump administration, highlight the tariff rates please. Be analytical please use numbers to back your analysis"
    
    print(f"Running minimal research test for goal: {research_goal}\n")
    
    try:
        # Execute with shorter timeout
        research_report = await asyncio.wait_for(
            run_parallel_research(research_goal),
            timeout=120  # 2 minute timeout
        )
        
        print("\n=== RESEARCH SUMMARY ===")
        print(research_report[:500] + "...\n")
        
        # Save the report to a file
        filename = "ml_dl_comparison.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(research_report)
        print(f"Full report saved to {filename}")
        
        return research_report
        
    except Exception as e:
        print(f"Error during minimal research: {str(e)}")
        return f"Research failed: {str(e)}"

if __name__ == "__main__":
    # Choose which test to run
    test_type = sys.argv[1] if len(sys.argv) > 1 else "minimal"
    
    if test_type == "full":
        asyncio.run(test_parallel_research())
    else:
        asyncio.run(test_minimal_research())
