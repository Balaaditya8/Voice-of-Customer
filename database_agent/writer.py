import os
import redis
import json
import psycopg2
import time
from dotenv import load_dotenv
from common.protocol import MCPPacket

load_dotenv()
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
SUB_CHANNEL = "analyzed_feedback_channel"

def connect_to_db_with_retry(host, dbname, user, password):
    """Tries to connect to the database, retrying until successful."""
    print(f"--- DB Writer: Attempting to connect to database at {host} ---")
    conn = None
    while conn is None:
        try:
            conn = psycopg2.connect(host=host, dbname=dbname, user=user, password=password, port=5432)
            print("--- DB Writer: Database connection successful. ---")
        except psycopg2.OperationalError as e:
            print(f"--- DB Writer: Could not connect to database: {e}. Retrying in 5 seconds... ---")
            time.sleep(5)
    return conn

def create_table_if_not_exists(conn):
    """Creates the 'feedback' table if it doesn't already exist. THIS IS THE FIX."""
    print("--- DB Writer: Ensuring 'feedback' table exists... ---")
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id VARCHAR(30) PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                text_content TEXT NOT NULL,
                author VARCHAR(100),
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                url_to_source TEXT,
                sentiment VARCHAR(20),
                theme VARCHAR(100),
                severity INTEGER,
                is_analyzed BOOLEAN DEFAULT FALSE
            );
        """)
        conn.commit()
    print("--- DB Writer: Table 'feedback' is ready. ---")

def upsert_data(conn, data):
    """Inserts a new record or updates an existing one with analysis data."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO feedback (id, source, text_content, author, timestamp, url_to_source, sentiment, theme, severity, is_analyzed)
            VALUES (%s, %s, %s, %s, TO_TIMESTAMP(%s), %s, %s, %s, %s, TRUE)
            ON CONFLICT (id) DO UPDATE SET
                sentiment = EXCLUDED.sentiment, theme = EXCLUDED.theme,
                severity = EXCLUDED.severity, is_analyzed = TRUE;
        """, (
            data.get('id'), data.get('source'), data.get('text_content'),
            data.get('author'), data.get('timestamp'), data.get('url_to_source'),
            data.get('sentiment'), data.get('theme'), data.get('severity')
        ))
        conn.commit()

if __name__ == "__main__":
    print("--- Database Writer Agent Starting Up ---")
    db_conn = connect_to_db_with_retry(DB_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
    
    create_table_if_not_exists(db_conn)

    print(f"--- DB Writer: Connecting to Redis at {REDIS_HOST} ---")
    redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0)
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(SUB_CHANNEL)
    print(f"--- DB Writer: Subscribed to '{SUB_CHANNEL}'. Listening for messages... ---")

    for message in pubsub.listen():
        try:
            packet = MCPPacket.model_validate_json(message['data'])
            print(f"--- DB Writer: Received analyzed feedback ID: {packet.data.get('id')} ---")
            upsert_data(db_conn, packet.data)
            print(f"--- DB Writer: Successfully saved feedback ID: {packet.data.get('id')} to PostgreSQL. ---")
        except Exception as e:
            if db_conn.closed:
                print("--- DB Writer: Database connection lost. Reconnecting... ---")
                db_conn = connect_to_db_with_retry(DB_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
            print(f"--- DB Writer: An error occurred while writing to DB: {e} ---")