import feedparser
import requests
import json
import os
from datetime import datetime

## Settings
ARXIV_API = "http://export.arxiv.org/api/query?search_query=all&sortBy=submittedDate&sortOrder=descending&max_results=300"

KEYWORDS = [
    'MHD',
    'X-ray',
    'X-rays',
    'SN',
    'SNe',
    'magnetohydrodynamics',
    'TeV',
    'PeV',
    'EeV',
    'XRISM',
]

JOURNALS = [
    'ApJ',
    'MNRAS',
    'A&A',
    'Nature',
    'Science',
    'ApJL',
    'PRL',
    'Astronomy & Astrophysics',
]

SEEN_FILE = 'seen_ids.json'

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]


## Loading and saving seen arXiv IDs
def load_seen_ids():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, 'r') as f:
        return set(json.load(f))
    
def save_seen_ids(seen_ids):
    with open(SEEN_FILE, 'w') as f:
        json.dump(list(seen_ids), f)


## Keyword and journal matching
def keyword_match(title, summary):
    text = (title + ' ' + summary).lower()
    return any(k.lower() in text for k in KEYWORDS)

def journal_match(comment):
    if comment is None:
        return False
    return any(j in comment for j in JOURNALS) and (
        "submitted" in comment.lower() or
        "accepted" in comment.lower() or
        "published" in comment.lower() or
        "to" in comment.lower()
    )


##
def get_subjects(entry):
    if not hasattr(entry, 'tags'):
        return "N/A"
    return ','.join(tag['term'] for tag in entry.tags)


## Discord notification
def send_to_discord(title, link, comment, subjects):
    message = (
        f"**{title}**\n"
        f"**Subjects: {subjects}**\n"
        f"{link}\n"
        f"Comment: {comment}"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={'content': message})


## Link selection
def get_best_link(entry):
    html_link = None
    pdf_link = None

    for link in entry.links:
        if link.get("type") == "text/html":
            html_link = link.get("href")
        if link.get("type") == "application/pdf":
            pdf_link = link.get("href")
    
    return html_link if html_link else pdf_link


## Main monitoring function
def main():
    print("Fethching arXiv data...")
    feed = feedparser.parse(ARXIV_API)

    seen_ids = load_seen_ids()
    new_seen_ids = set(seen_ids)

    for entry in feed.entries:
        arxiv_id = entry.id
        title = entry.title
        summary = entry.summary
        link = get_best_link(entry)
        comment = entry.get("arxiv_comment", None)
        subjects = get_subjects(entry)

        if arxiv_id in seen_ids:
            continue

        if keyword_match(title, summary) and journal_match(comment):
            send_to_discord(title, link, comment, subjects)

        new_seen_ids.add(arxiv_id)

    save_seen_ids(new_seen_ids)
    print("Done.")


if __name__ == "__main__":
    main()