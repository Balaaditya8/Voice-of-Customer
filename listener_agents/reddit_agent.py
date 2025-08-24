import os
import praw
import psycopg2
import time
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler


load_dotenv()

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

def connect_to_db():
    """Establishes a connection to the PostgreSQL database."""
    time.sleep(5) 
    try:
        conn = psycopg2.connect(
            host="localhost", 
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            port=5432
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Could not connect to database: {e}")
        return None

def create_table_if_not_exists(conn):
    """Creates the 'feedback' table if it doesn't already exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id VARCHAR(20) PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                text_content TEXT NOT NULL,
                author VARCHAR(100),
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                url_to_source TEXT
            );
        """)
        conn.commit()
        print("Table 'feedback' is ready.")

def insert_data(conn, data):
    """Inserts a list of feedback data into the database, ignoring duplicates."""
    with conn.cursor() as cur:
        for item in data:
            cur.execute("""
                INSERT INTO feedback (id, source, text_content, author, timestamp, url_to_source)
                VALUES (%s, %s, %s, %s, TO_TIMESTAMP(%s), %s)
                ON CONFLICT (id) DO NOTHING;
            """, (item['id'], item['source'], item['text_content'], item['author'], item['timestamp'], item['url_to_source']))
        conn.commit()
    print(f"Inserted {len(data)} new items into the database.")


def fetch_reddit_data():
    """Fetches data from a specified subreddit and returns it in a structured format."""
    print("Initializing Reddit instance...")
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD,
    )

    subreddit_name = 'Notion' 
    limit = 25 

    print(f"Fetching latest {limit} comments from r/{subreddit_name}...")
    subreddit = reddit.subreddit(subreddit_name)
    
    fetched_data = []
    for comment in subreddit.comments(limit=limit):
        fetched_data.append({
            'id': f"reddit_{comment.id}",
            'source': 'Reddit',
            'text_content': comment.body,
            'author': comment.author.name if comment.author else '[deleted]',
            'timestamp': comment.created_utc,
            'url_to_source': f"https://www.reddit.com{comment.permalink}"
        })
    
    print(f"Fetched {len(fetched_data)} comments.")
    return fetched_data

def run_job():
    """The main function to be scheduled. It connects, fetches, and inserts."""
    print("\n--- Starting new job run ---")
    conn = connect_to_db()
    if conn:
        try:
            create_table_if_not_exists(conn)
            reddit_data = fetch_reddit_data()
            if reddit_data:
                insert_data(conn, reddit_data)
        finally:
            conn.close()
            print("Database connection closed.")
    else:
        print("Skipping job run due to database connection failure.")
    print("--- Job run finished ---")


if __name__ == "__main__":
    # To run the job immediately for testing, uncomment the next line:
    run_job()

    scheduler = BlockingScheduler()
    # Schedule the job to run every hour
    scheduler.add_job(run_job, 'interval', hours=1, next_run_time=None) # next_run_time=None ensures it runs on start
    print("Scheduler started. First job will run immediately. Press Ctrl+C to exit.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass