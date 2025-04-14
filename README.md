# Discord Agentic Bot with Memory

This Discord bot leverages multiple AI agents (Knowledge Base, Web Search, Research, Chat) to intelligently handle user queries. It features persistent memory using Mem0 and Qdrant, allowing for context-aware conversations.

## Features

*   **Intelligent Query Dispatching:** Automatically routes queries to the most appropriate agent (Knowledge Base, Web Search, Research, Chat).
*   **Knowledge Base Agent:** Answers questions based on its internal knowledge.
*   **Web Search Agent:** Fetches up-to-date information from the web.
*   **Research Agent:** Performs in-depth analysis on complex topics using parallel processing.
*   **Chat Agent:** Engages in natural conversation, remembering past interactions using Mem0.
*   **Persistent Memory:** Utilizes Mem0 and Qdrant to store and retrieve conversation history for context.
*   **Forced Agent Commands:** Allows users to explicitly invoke specific agents (`!force_search`, `!force_research`, `!force_knowledge`).
*   **Direct Chat Mode:** Allows interaction without command prefixes in a specific channel (`!direct_chat`).
*   **Memory Management:** Check memory status (`!memory_status`) and clear recent history (`!clear_memory`).

## Prerequisites

*   **Python 3.8+**
*   **Discord Bot Token:** Get one from the [Discord Developer Portal](https://discord.com/developers/applications).
*   **Google API Key:** Get one from the [Google AI Studio](https://aistudio.google.com/app/apikey) or Google Cloud Console, enabled for the Gemini API.
*   **Qdrant:** A running instance of the Qdrant vector database. You can run it locally using Docker:
    ```bash
    docker run -p 6333:6333 qdrant/qdrant
    ```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

2.  **Configure environment variables:**
    *   Create a file named `.env` in the project root.
    *   Add your Discord token and Google API key:
        ```env
        DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN_HERE
        GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY_HERE
        ```

3.  **Run the bot using Docker Compose (Recommended):**
    *   Make sure you have Docker and Docker Compose installed.
    *   From the project root, run:
        ```bash
        docker-compose up --build
        ```
    *   This will build the Docker image, start the bot, and also start a Qdrant instance, ensuring Qdrant is healthy before starting the bot. The Docker Compose file includes healthchecks to ensure both the bot and Qdrant are running correctly, using the `qdrant_client` library to verify their status.

**Troubleshooting Docker:**

If you encounter the error "Bind for 0.0.0.0:6333 failed: port is already allocated", it means that another application is already using port 6333, which Qdrant needs. To resolve this:

1.  **Stop the Existing Process:** Identify and stop the process that is using port 6333.
2.  **Change the Port Mapping:** Modify the `docker-compose.yml` file to use a different port for Qdrant (e.g., `6334:6333`).
3.  **Remove Existing Container:** Run `docker-compose down` to stop and remove all containers, then try `docker-compose up --build` again.

4.  **Alternative: Manual Setup (for development or if you don't want to use Docker):**
    *   Create a virtual environment (recommended):
        ```bash
        python -m venv venv
        # On Windows
        .\venv\Scripts\activate
        # On macOS/Linux
        source venv/bin/activate
        ```
    *   Install dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    *   Ensure Qdrant is running:
        *   Start your local Qdrant instance if it's not already running (see Prerequisites). The bot expects it to be available at `localhost:6333`.
    *   Run the bot:
        ```bash
        python discord_bot.py
        ```

## Usage

Invite the bot to your Discord server. You can interact with it using the following commands:

*   **`!ask [your query]`**: The primary command. The bot determines the best way to answer.
*   **`!force_search [query]`**: Forces a web search.
*   **`!force_research [topic]`**: Forces in-depth research.
*   **`!force_knowledge [query]`**: Forces an answer from the knowledge base.
*   **`!direct_chat`**: Activates prefix-less chat mode in the current channel.
*   **`!memory_status`**: Shows memory usage for your user ID.
*   **`!clear_memory`**: Clears recent message history for your user ID.
*   **`!bot_help`**: Displays the help message.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

## License

This project is licensed under the terms of the LICENSE file.
