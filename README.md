# VoC Platform: A Multi-Agent AI System for Customer Feedback Analysis

This project is an end-to-end data pipeline that autonomously gathers unstructured customer feedback from the web (reddit), processes it through a multi-agent AI system, and presents the enriched, actionable insights on a real-time, interactive dashboard.

The system is built on an event-driven, microservice-based architecture where specialized AI agents communicate asynchronously using a custom communication protocol (MCP) over a message bus.

## Demo

## Features

* **Autonomous Data Ingestion:** A listener agent continuously monitors Reddit for new comments related to a specific topic.

* **Event-Driven Architecture:** Agents are fully decoupled and communicate asynchronously using Redis Pub/Sub, making the system scalable and resilient.

* **Multi-Step AI Analysis Pipeline:** A dedicated analysis agent performs a sequence of complex NLP tasks on each piece of feedback:
    * **Sentiment Analysis:** Classifies feedback as `positive`, `negative`, or `neutral`.
    * **Topic Classification:** Assigns feedback to a pre-defined category (e.g., `Bug Report`, `Feature Request`).
    * **Severity Rating:** Rates negative feedback on a scale of 1-4 to identify critical issues.

* **Local LLM Inference:** All AI analysis is performed locally using **Ollama**, ensuring privacy and zero API costs.

* **Persistent Storage:** A dedicated database agent saves all final, enriched data to a PostgreSQL database.

* **Interactive Dashboard:** A full-stack Streamlit application provides a user-friendly interface to filter, explore, and visualize the analyzed customer feedback.

## Tech Stack 
* **Backend:** Python
* **AI / ML:** Ollama (with `deepseek-r1:1.5b`), `pydantic`
* **Database:** PostgreSQL
* **Message Bus / Cache:** Redis
* **Dashboard:** Streamlit, Pandas
* **Orchestration:** Docker & Docker Compose



## Local Setup

### Prerequisites

* Git
* Python 3.10+
* Docker and Docker Compose
* Ollama (with a model pulled, e.g., `ollama pull deepseek-r1:1.5b`)

### Installation Steps
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Balaaditya8/Voice-of-Customer.git

    cd Voice-of-Customer
    ```
2. **Create the `.env` file:**

    add your Reddit API and database credentials.
    ```
    # Reddit API Credentials
    REDDIT_CLIENT_ID="your_id"
    REDDIT_CLIENT_SECRET="your_secret_pwd"
    REDDIT_USER_AGENT="agent_name"
    REDDIT_USERNAME="reddit_user_name"
    REDDIT_PASSWORD="reddit_password"

    # Database Credentials
    POSTGRES_DB=voc_db
    POSTGRES_USER=user
    POSTGRES_PASSWORD=password
    ```

3.  **Create the Python Package folder:**
The `common` directory needs to be a Python package.
    ```bash
    mkdir -p common

    touch common/__init__.py
    ```

4. **Build and start the backend services:**
    This command will start the PostgreSQL database and Redis server in the background.
    ```bash
    docker-compose up -d db redis
    ```

5.  **Create and activate the Python virtual environment:**
    ```bash
    python -m venv venv

    source venv/bin/activate
    ```

6.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```


## How to Run

The application is composed of three main parts: the Ollama server, the backend agents, and the frontend dashboard. Each needs to be run in its own terminal.

**Terminal 1: Start the Ollama Server**
```bash
# This command makes Ollama accessible from inside Docker
OLLAMA_HOST=0.0.0.0 ollama serve
```

**Terminal 2:  Start the Backend Agents**
```bash
docker-compose up --build
```
**Terminal 3:  Launch the Streamlit Dashboard**
```bash
source venv/bin/activate

streamlit run dashboard/app.py

```




