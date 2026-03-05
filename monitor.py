import feedparser
import requests
import json
import os
import re
from datetime import datetime
import time

# ==== Setup ====
ARXIV_API = (
    "http://export.arxiv.org/api/query?"
    "search_query=cat:astro-ph.*"
    "&sortBy=submittedDate"
    "&sortOrder=descending"
    "&max_results=200"
)

KEYWORDS = [
    # 'MHD',
    # 'X-ray',
    # 'X-rays',
    # 'SN',
    # 'SNe',
    # 'magnetohydrodynamics',
    # 'TeV',
    # 'PeV',
    # 'EeV',
    # 'XRISM',
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

SUBJECT_ROUTING = {
    'astro-ph.CO': os.environ['CHANNEL_CO'],
    'astro-ph.EP': os.environ['CHANNEL_EP'],
    'astro-ph.GA': os.environ['CHANNEL_GA'],
    'astro-ph.HE': os.environ['CHANNEL_HE'],
    'astro-ph.IM': os.environ['CHANNEL_IM'],
    'astro-ph.SR': os.environ['CHANNEL_SR'],
}

SEEN_IDS_FILE = 'seen_ids.json'
MAX_SEEN = 2000
DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
ABSTRACT_CHANNEL_ID = os.environ["CHANNEL_ABSTRACT"]
POST_INTERVAL = 1.2  # seconds


# ==== Loading and saving seen arXiv IDs to avoid duplicates ====
def load_seen_ids():
    if not os.path.exists(SEEN_IDS_FILE):
        return []

    with open(SEEN_IDS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []
def save_seen_ids(seen_ids):
    trimmed = seen_ids[-MAX_SEEN:]
    with open(SEEN_IDS_FILE, 'w') as f:
        json.dump(list(trimmed), f)


# ==== ID extraction ====
def extract_arxiv_id(entry_id):
    if not entry_id:
        return None
    base = entry_id.split('/')[-1]
    return base.split('v')[0] if 'v' in base else base


# ==== Keyword and journal matching ====
def keyword_match(title, summary):
    if not KEYWORDS:
        return True
    text = (title + ' ' + summary).lower()
    return any(k.lower() in text for k in KEYWORDS)

def journal_match(comment):
    if comment is None:
        return False
    return any(j in comment for j in JOURNALS) and (
        "submitted" in comment.lower() or
        "accepted" in comment.lower() or
        "published" in comment.lower()
    )


# ==== Subject extraction ====
def get_subjects(entry):
    if not hasattr(entry, 'tags'):
        return "N/A"
    return ','.join(tag['term'] for tag in entry.tags)


# ==== Routing based on subjects ====
def route_by_subject(entry):
    if not hasattr(entry, 'arxiv_primary_category'):
        return None

    primary = entry.arxiv_primary_category['term']

    if not primary.startswith('astro-ph'):
        return None

    return SUBJECT_ROUTING.get(primary)


def build_abstract_message(arxiv_id, title, summary, subjects):

    MAX_TOTAL_LENGTH = 1950

    header_template = (
        f"arXiv: {arxiv_id}\n"
        f"Title: {title}\n"
        f"Subjects: {subjects}\n"
        "Truncated: {is_truncated}\n"
        "Abstract:\n"
    )

    max_summary_length = MAX_TOTAL_LENGTH - len(header_template.format(is_truncated=False))

    is_truncated = False

    if len(summary) > max_summary_length:
        is_truncated = True
        cut_summary = summary[:max_summary_length]

        matches = list(re.finditer(r'\.\s+(?=[A-Z][0-9])', cut_summary))
        if matches:
            last_match = matches[-1]
            summary = cut_summary[:last_match.start() + 1]
        else:
            last_period_idx = cut_summary.rfind('. ')
            if last_period_idx != -1:
                summary = cut_summary[:last_period_idx + 1]
            else:
                summary = cut_summary

    header = header_template.format(is_truncated=is_truncated)

    return header + summary


# ==== Discord notification ====
def send_to_discord(channel_id, arxiv_id, title, link, comment, subjects):

    time.sleep(POST_INTERVAL)  # To avoid hitting rate limits

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
    }
    separator = "─" * 40
    message = (
        f"{separator}\n"
        f"**{title}**\n"
        f"**Subjects:** {subjects}\n"
        f"**Journal Info:** {comment}\n"
        f"**arXiv ID:** `{arxiv_id}`\n"
        f"**Link:** {link}\n"
        f"{separator}"
    )
    
    response = requests.post(
        url,
        headers=headers,
        json={"content": message}
    )
    if response.status_code not in (200, 201):
        print("Discord error:", response.status_code, response.text)


def send_abstract_to_discord(arxiv_id, title, summary, subjects):

    time.sleep(POST_INTERVAL)  # To avoid hitting rate limits
    
    url = f"https://discord.com/api/v10/channels/{ABSTRACT_CHANNEL_ID}/messages"
    headers = {
        'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
    }

    message = build_abstract_message(arxiv_id, title, summary, subjects)

    response = requests.post(
        url,
        headers=headers,
        json={"content": message}
    )
    if response.status_code not in (200, 201):
        print("Discord error:", response.status_code, response.text)


# ==== Link selection ====
def get_best_link(entry):
    html_link = None
    pdf_link = None

    for link in entry.links:
        if link.get("type") == "text/html":
            html_link = link.get("href")
        if link.get("type") == "application/pdf":
            pdf_link = link.get("href")
    
    if not html_link and not pdf_link:
        return entry.id
    
    return html_link if html_link else pdf_link


# ==== Main monitoring function ====
def main():
    print("Fethching arXiv data...")
    feed = feedparser.parse(ARXIV_API)

    seen_ids = load_seen_ids()
    seen_set = set(seen_ids)
    new_seen_ids = list(seen_ids)

    for entry in feed.entries:
        arxiv_id = entry.id
        title = entry.title
        summary = entry.summary
        link = get_best_link(entry)
        comment = entry.get("arxiv_comment", None)
        subjects = get_subjects(entry)
        # webhook = route_by_subject(entry)
        channel_id = route_by_subject(entry)

        if arxiv_id in seen_set:
            continue

        new_seen_ids.append(arxiv_id)
        seen_set.add(arxiv_id)

        if not channel_id:
            continue

        if keyword_match(title, summary) and journal_match(comment) and channel_id:
            clean_id = extract_arxiv_id(arxiv_id)

            send_to_discord(channel_id, clean_id, title, link, comment, subjects)
            send_abstract_to_discord(clean_id, title, summary, subjects)

    save_seen_ids(new_seen_ids)
    print("Done.")


# ==== Entry point ====
if __name__ == "__main__":
    main()