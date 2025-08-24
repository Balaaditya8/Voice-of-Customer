import os
import pandas as pd
import psycopg2
import hdbscan
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
import ollama
import re
load_dotenv()

POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

print("Initializing Sentence Transformer model for embeddings...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def connect_to_db():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(host="localhost", dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD, port=5432)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Could not connect to database: {e}")
        return None

def fetch_unprocessed_data(conn):
    df = pd.read_sql_query("SELECT id, text_content FROM feedback WHERE is_analyzed = FALSE;", conn)
    return df

def analyze_sentiment(df):
    sentiments = []
    try:
        client = ollama.Client()
    except Exception as e:
        print(f"Fatal Error: Failed to initialize Ollama client: {e}")
        df['sentiment'] = 'error'
        return df

    for index, row in df.iterrows():
        text_to_analyze = row['text_content'][:1024]
        prompt = f"""
        You are a sentiment analysis expert. Your task is to classify a customer comment as 'positive', 'negative', or 'neutral'. You must respond with only one of those three words and nothing else.

        Here are some examples:
        Comment: "I love the new update, it's so fast!"
        Classification: positive

        Comment: "My app keeps crashing after the latest version."
        Classification: negative

        Now, classify the following comment:
        Comment: "{text_to_analyze}"
        Classification:
        """

        try:
            response = client.chat(
                model='deepseek-r1:1.5b',
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.0}
            )
            result = response['message']['content'].strip().lower().replace('.', '')
            words = result.split()
            #print(result)
            sent = "neutral"
            if len(words) > 0:
                last_word = words[-1].replace('.', '') 
                #print(last_word)
                if last_word in ["positive", "negative", "neutral"]:
                    sent = last_word
            
            #print(sent)
            
            sentiments.append(sent)
                
        except Exception as e:
            print(f"Error during sentiment analysis for item {row['id']}: {e}")
            sentiments.append('error')
            
        if (index + 1) % 10 == 0:
            print(f"  ...processed sentiment for {index + 1}/{len(df)} items.")

    df['sentiment'] = sentiments
    print("Sentiment analysis complete.")
    return df
    


def classify_topics_with_llm(df):
    """Classifies each comment into a pre-defined topic using an Ollama LLM."""
    print("Classifying topics with Ollama (per-comment)...")
    
    topic_list = [
        'Bug Report',
        'Feature Request',
        'UI/UX Feedback',
        'Authentication Issue',
        'Performance',     
        'Pricing & Billing',
        'How-To Question',
        'General Praise',
        'Miscellaneous'
    ]

    themes = []
    try:
        client = ollama.Client()
    except Exception as e:
        print(f"Fatal Error: Failed to initialize Ollama client: {e}")
        df['theme'] = 'error'
        return df

    for index, row in df.iterrows():
        text_to_analyze = row['text_content'][:1024]
        
        prompt = f"""
        You are an expert at categorizing customer feedback.
        Based on the comment provided, which of the following categories does it best fit into?

        Categories: {', '.join(topic_list)}

        You must respond with ONLY the single best category name from the list and nothing else.

        Comment: "{text_to_analyze}"

        Category:
        """
        
        try:
            response = client.chat(
                model='deepseek-r1:1.5b',
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.0}
            )
            result = response['message']['content'].strip()
            #print(result)
            cleaned = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()

            if "Category:" in cleaned:
                category = cleaned.split("Category:")[-1].strip()
            else:
                category = cleaned.strip()
            #print(category)
            best_match = next((topic for topic in topic_list if topic.lower() in category.lower()), 'Miscellaneous')
            themes.append(best_match)

        except Exception as e:
            print(f"Error during topic classification for item {row['id']}: {e}")
            themes.append('error')

        if (index + 1) % 5 == 0:
            print(f"  ...classified topic for {index + 1}/{len(df)} items.")

    df['theme'] = themes
    print("Topic classification complete.")
    return df

def rate_severity_with_llm(df):
    """
    Rates the severity of negative feedback using an Ollama LLM.
    Assigns a score from 1 (Low) to 4 (Critical).
    Positive/Neutral feedback gets a score of 0.
    """
    print("Rating severity for negative feedback with Ollama...")
    
    df['severity'] = 0
    
    negative_df = df[df['sentiment'] == 'negative']
    
    if negative_df.empty:
        print("No negative feedback to rate. Skipping severity rating.")
        return df

    print(f"Found {len(negative_df)} negative items to rate for severity...")
    
    try:
        client = ollama.Client()
    except Exception as e:
        print(f"Fatal Error: Failed to initialize Ollama client: {e}")
        return df # Return df with default severity

    severity_prompt_template = """
    You are an expert at prioritizing customer feedback. Your task is to rate the severity of a customer issue on a scale from 1 to 4.
    You must respond with ONLY the number (1, 2, 3, or 4) and nothing else.

    Here is the severity scale:
    1 - Low: A minor issue, typo, or suggestion with no impact on functionality. Basic problem or mostly opinion of the user.
    2 - Medium: A user experience issue or a non-critical bug that has a workaround. An issue that is not very vital but might need some looking at.
    3 - High: A major feature is broken or functionality is significantly impaired. An issue that is worth looking at by the company.
    4 - Critical: A complete service outage, data loss, or security vulnerability. An issue that the company must work on for sure!

    Here are some examples:
    Comment: "There's a spelling mistake on the pricing page."
    Severity: 1

    Comment: "The new save button is in a really weird spot, it's hard to find."
    Severity: 2
    
    Comment: "The app crashes every time I try to save my work. I have to restart it."
    Severity: 3
    
    Comment: "I can't log in at all, the whole system seems to be down for everyone!"
    Severity: 4

    ---
    Now, Think on behalf of the company and rate the severity of this new comment:
    Comment: "{text_to_analyze}"
    Severity:
    """

    severities = {}
    for index, row in negative_df.iterrows():
        text_to_analyze = row['text_content'][:1024]
        prompt = severity_prompt_template.format(text_to_analyze=text_to_analyze)

        try:
            response = client.chat(
                model='deepseek-r1:1.5b',
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.0}
            )
            result = response['message']['content'].strip()
            print(result)
            cleaned = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()

            if "Severity:" in cleaned:
                severity = cleaned.split("Severity:")[-1].strip()
            else:
                severity = cleaned.strip()
            print(severity)
            severity_score = int(severity)
            if 1 <= severity_score <= 4:
                severities[row['id']] = severity_score
            else:
                severities[row['id']] = 2 # Default to Medium if output is unexpected
        except (ValueError, IndexError, Exception) as e:
            print(f"Error rating severity for item {row['id']}: {e}")
            severities[row['id']] = 2 # Default to Medium on error

    df['severity'] = df['id'].map(severities).fillna(df['severity']).astype(int)
    print("Severity rating complete.")
    return df

def update_data(conn, df_results):
    """Updates the database with analysis results."""
    print(f"Updating {len(df_results)} items in the database...")
    with conn.cursor() as cur:
        for index, row in df_results.iterrows():
            cur.execute(
                "UPDATE feedback SET sentiment = %s, theme = %s, severity = %s, is_analyzed = TRUE WHERE id = %s",
                (row['sentiment'], row['theme'], row['severity'], row['id'])
            )
        conn.commit()
    print("Database update complete.")




if __name__ == "__main__":
    conn = connect_to_db()
    if conn:
        try:
            df = fetch_unprocessed_data(conn)
            if not df.empty:
                df_sentiment = analyze_sentiment(df)
                df_with_severity = rate_severity_with_llm(df_sentiment)
                df_final = classify_topics_with_llm(df_with_severity)
                #print(df_final)
                update_data(conn, df_final)
            else:
                print("No new data to process.")
        finally:
            conn.close()