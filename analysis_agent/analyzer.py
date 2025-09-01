import os
import redis
import json
import ollama
import re
from dotenv import load_dotenv
from common.protocol import MCPPacket

print("--- Analysis Agent Starting Up ---")
load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0)

SUB_CHANNEL = "raw_feedback_channel"
PUB_CHANNEL = "analyzed_feedback_channel"


def analyze_sentiment(client, text_to_analyze):
    """Analyzes sentiment for a single piece of text."""
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
    response = client.chat(
        model='deepseek-r1:1.5b',
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.0}
    )
    result = response['message']['content'].strip().lower().replace('.', '')
    words = result.split()
    if len(words) > 0:
        last_word = words[-1].replace('.', '')
        if last_word in ["positive", "negative", "neutral"]:
            return last_word
    return "neutral"

def classify_topic(client, text_to_analyze):
    """Classifies a single piece of text into a pre-defined topic."""
    topic_list = [
        'Bug Report', 'Feature Request', 'UI/UX Feedback', 'Authentication Issue',
        'Performance', 'Pricing & Billing', 'How-To Question', 'General Praise', 'Miscellaneous'
    ]
    prompt = f"""
    You are an expert at categorizing customer feedback. Based on the comment provided, which of the following categories does it best fit into?
    Categories: {', '.join(topic_list)}
    You must respond with ONLY the single best category name from the list and nothing else.
    Comment: "{text_to_analyze}"
    Category:
    """
    response = client.chat(
        model='deepseek-r1:1.5b',
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.0}
    )
    result = response['message']['content'].strip()
    cleaned = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
    category = cleaned.split("Category:")[-1].strip() if "Category:" in cleaned else cleaned.strip()
    return next((topic for topic in topic_list if topic.lower() in category.lower()), 'Miscellaneous')

def rate_severity(client, text_to_analyze, sentiment):
    """Rates the severity of a single piece of negative feedback."""
    if sentiment != 'negative':
        return 0
    
    severity_prompt_template = """
    You are an expert at prioritizing customer feedback. Your task is to rate the severity of a customer issue on a scale from 1 to 4. You must respond with ONLY the number (1, 2, 3, or 4) and nothing else.
    Severity Scale:
    1 - Low: A minor issue, typo, or suggestion.
    2 - Medium: A user experience issue or a non-critical bug with a workaround.
    3 - High: A major feature is broken or functionality is significantly impaired.
    4 - Critical: A complete service outage, data loss, or security vulnerability.
    Examples:
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
    prompt = severity_prompt_template.format(text_to_analyze=text_to_analyze)
    response = client.chat(
        model='deepseek-r1:1.5b',
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.0}
    )
    result = response['message']['content'].strip()
    cleaned = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
    severity_str = cleaned.split("Severity:")[-1].strip() if "Severity:" in cleaned else cleaned.strip()
    try:
        severity_score = int(severity_str)
        return severity_score if 1 <= severity_score <= 4 else 2
    except (ValueError, IndexError):
        return 2

# --- 3. MAIN SERVICE LOOP ---
if __name__ == "__main__":
    print(f"Connecting to Redis at {REDIS_HOST}...")
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(SUB_CHANNEL)
    print(f"Subscribed to '{SUB_CHANNEL}'. Listening for messages...")

    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
    print(f"Connecting to Ollama at {OLLAMA_HOST}...")
    ollama_client = ollama.Client(host=OLLAMA_HOST)

    for message in pubsub.listen():
        try:
            packet = MCPPacket.model_validate_json(message['data'])
            print(f"Received raw feedback ID: {packet.data.get('id')}")
            
            text = packet.data.get('text_content', '')

            sentiment = analyze_sentiment(ollama_client, text)
            topic = classify_topic(ollama_client, text)
            severity = rate_severity(ollama_client, text, sentiment)

            packet.data['sentiment'] = sentiment
            packet.data['theme'] = topic
            packet.data['severity'] = severity

            packet.source_agent = "AnalysisAgent"
            packet.payload_type = "analyzed_feedback"
            redis_client.publish(PUB_CHANNEL, packet.model_dump_json())
            print(f"Published analyzed feedback ID: {packet.data.get('id')} to '{PUB_CHANNEL}'")

        except Exception as e:
            print(f"An error occurred during analysis: {e}")