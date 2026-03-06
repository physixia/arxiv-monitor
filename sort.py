import os
import requests
import time
import traceback


# ================= SETUP =================
DISCORD_SORT_TOKEN = os.environ["DISCORD_SORT_TOKEN"]
CHECK_EMOJI_URL = "%E2%9C%85"
CHECK_EMOJI_UNICODE = "✅"

REACTION_ROUTING = {
    "AGN": os.environ["CHANNEL_DEST_AGN"],
    "SNR": os.environ["CHANNEL_DEST_SNR"],
    "BH": os.environ["CHANNEL_DEST_BH"],
    "highZ": os.environ["CHANNEL_DEST_HIGHZ"],
    "DM": os.environ["CHANNEL_DEST_DM"],
    "GW": os.environ["CHANNEL_DEST_GW"],
}

SOURCE_CHANNELS = [
    os.environ["CHANNEL_CO"],
    os.environ["CHANNEL_EP"],
    os.environ["CHANNEL_GA"],
    os.environ["CHANNEL_HE"],
    os.environ["CHANNEL_IM"],
    os.environ["CHANNEL_SR"],
]

LOG_CHANNEL_ID = os.environ["CHANNEL_LOG"]
ERR_CHANNEL_ID = os.environ["CHANNEL_ERR"]

HEADERS = {
    "Authorization": f"Bot {DISCORD_SORT_TOKEN}",
    "Content-Type": "application/json"
}

POST_INTERVAL = 1.2  # seconds


# ================= API Functions =================
def get_recent_messages(channel_id, limit=100):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch messages from channel {channel_id}: {response.status_code} - {response.text}")
        return []

def send_message(channel_id, content):
    time.sleep(POST_INTERVAL)

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    response = requests.post(url, headers=HEADERS, json={"content": content})
    if response.status_code not in (200, 201):
        print(f"Failed to send message to channel {channel_id}: {response.status_code} - {response.text}")

def add_reaction(channel_id, message_id, emoji):
    time.sleep(POST_INTERVAL)

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
    response = requests.put(url, headers=HEADERS)
    if response.status_code != 204:
        print(f"Failed to add reaction to message {message_id} in channel {channel_id}: {response.status_code} - {response.text}")


# ================= Logging and Error Reporting =================
def send_log_to_discord(total_processed, category_counts):
    time.sleep(POST_INTERVAL)

    if total_processed > 0:
        breakdown = '\n'.join([f"・ Project {cat}: {count}件" for cat, count in category_counts.items() if count > 0])
        
        message = (
            f"💼 **[arXiv セクレタリ | 業務報告]**\n"
            f"指定された論文の振り分け作業が完了しました。\n"
            f"承認マークが確認できた **{total_processed}** 件の資料を、各プロジェクトの専用フォルダへ転送しています。\n\n"
            f"**【転送ログ】**\n{breakdown}\n\n"
            f"本日のタスクは以上です。後ほど、転送先の資料への目通しをお忘れなく。"
        )
    else:
        message = (
            f"💼 **[arXiv セクレタリ | 業務報告]**\n"
            f"定期チェックを行いましたが、新たに承認された資料はありませんでした。\n"
            f"次のチェック時刻まで待機状態に移行します。"
        )

    url = f"https://discord.com/api/v10/channels/{LOG_CHANNEL_ID}/messages"
    requests.post(url, headers=HEADERS, json={"content": message})

def send_error_to_discord(error_details):
    time.sleep(POST_INTERVAL)

    user_id = "1115026252156391558"

    message = (
        f"🚨 **[arXiv セクレタリ | 緊急事態]**\n"
        f"<@{user_id}> システムの稼働中に予期せぬエラーが発生し、処理が中断されました。\n"
        f"至急、以下のログを確認し対応をお願いします。放置すれば業務に支障が出るおそれがあります。\n\n"
        f"**【エラー詳細】**\n```\n{error_details}\n```"
    )

    url = f"https://discord.com/api/v10/channels/{ERR_CHANNEL_ID}/messages"
    try:
        requests.post(url, headers=HEADERS, json={"content": message})
    except Exception as e:
        print(f"Failed to send error message to Discord: {e}")


# ================= Main Logic =================
def main():
    print("Starting reaction scan...")

    total_processed = 0
    category_counts = {cat: 0 for cat in REACTION_ROUTING.keys()}

    for source_channel in SOURCE_CHANNELS:
        messages = get_recent_messages(source_channel)

        for msg in messages:
            COURIER_BOT_ID = "1478743012711600321"
            if msg.get("author", {}).get("id") != COURIER_BOT_ID:
                continue

            reactions = msg.get("reactions", [])
            if not reactions:
                continue

            already_processed = any(
                r.get("emoji", {}).get("name") == CHECK_EMOJI_UNICODE and r.get("me") is True
                for r in reactions
            )
            if already_processed:
                continue

            processed_in_this_run = False
            for reaction in reactions:
                emoji_name = reaction.get("emoji", {}).get("name")

                if emoji_name in REACTION_ROUTING:
                    dest_channel = REACTION_ROUTING[emoji_name]

                    msg_link = f"https://discord.com/channels/{msg.get('guild_id', '@me')}/{source_channel}/{msg['id']}"
                    forward_content = (
                        f"**【📎 分類: {emoji_name}】**\n"
                        f"{msg.get('content', '')}\n"
                        f"*(元メッセージ: {msg_link})*"
                    )

                    send_message(dest_channel, forward_content)
                    processed_in_this_run = True

            if processed_in_this_run:
                add_reaction(source_channel, msg["id"], CHECK_EMOJI_URL)

    print("Scan completed.")
    send_log_to_discord(total_processed, category_counts)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err_trace = traceback.format_exc()
        print(f"Critical error occurred: {e}")
        send_error_to_discord(err_trace)
        raise
