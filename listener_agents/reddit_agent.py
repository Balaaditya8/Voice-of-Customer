import os
import praw
import redis
import time
from dotenv import load_dotenv
from common.protocol import MCPPacket

load_dotenv()

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
RAW_FEEDBACK_CHANNEL = "raw_feedback_channel"
PROCESSED_IDS_SET = "processed_reddit_ids"


def connect_to_redis_with_retry(host):
    """Tries to connect to Redis, retrying until successful."""
    print(f"Attempting to connect to Redis at {host}...")
    while True:
        try:
            r = redis.Redis(host=host, port=6379, db=0, decode_responses=True)
            r.ping() # Check if the connection is alive
            print("Successfully connected to Redis.")
            return r
        except redis.exceptions.ConnectionError as e:
            print(f"Redis connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def fetch_and_publish(redis_client, reddit_instance, subreddit_name='Notion', limit=20):
    """Fetches new comments and publishes them as MCP packets to Redis."""
    print(f"Fetching latest {limit} comments from r/{subreddit_name}...")
    subreddit = reddit_instance.subreddit(subreddit_name)
    
    new_comments_published = 0
    for comment in subreddit.comments(limit=limit):
        if not redis_client.sismember(PROCESSED_IDS_SET, comment.id):
            comment_data = {
                'id': f"reddit_{comment.id}", 'source': 'Reddit', 'text_content': comment.body,
                'author': comment.author.name if comment.author else '[deleted]',
                'timestamp': comment.created_utc, 'url_to_source': f"https://www.reddit.com{comment.permalink}"
            }
            packet = MCPPacket(
                source_agent="RedditListenerAgent", payload_type="raw_feedback", data=comment_data
            )
            redis_client.publish(RAW_FEEDBACK_CHANNEL, packet.model_dump_json())
            redis_client.sadd(PROCESSED_IDS_SET, comment.id)
            new_comments_published += 1
    
    if new_comments_published > 0:
        print(f"Published {new_comments_published} new comments.")

if __name__ == "__main__":
    print("--- Reddit Listener Agent Starting Up ---")
    
    redis_client = connect_to_redis_with_retry(REDIS_HOST)

    while True: 
        try:
            print("Initializing Reddit instance...")
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT, username=REDDIT_USERNAME, password=REDDIT_PASSWORD,
            )
            print("Successfully initialized Reddit instance.")
            
            while True:
                fetch_and_publish(redis_client, reddit)
                print(f"--- Sleeping for 15 minutes before next fetch (Local Time: {time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
                time.sleep(21600) 
        
        except Exception as e:
            print(f"An error occurred in the main loop: {e}. Retrying in 60 seconds...")
            time.sleep(60)