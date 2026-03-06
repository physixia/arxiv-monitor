# voice.py
import discord
import os
import json
import re
import requests
import asyncio
import io
import wave
import traceback
from pathlib import Path
from openai import OpenAI
#import deepl
from dotenv import load_dotenv
load_dotenv()


# ================= SETTINGS =================
DISCORD_VOICE_TOKEN = os.environ["DISCORD_VOICE_TOKEN"]
ABSTRACT_CHANNEL_ID = int(os.environ["CHANNEL_ABSTRACT"])
LOG_CHANNEL_ID = int(os.environ["CHANNEL_LOG"])
ERR_CHANNEL_ID = int(os.environ["CHANNEL_ERR"])

# VOICEVOX engine
VOICEVOX_API_URL = "http://127.0.0.1:50021"
SPEAKER_ID = 47  # Nurse Robot Type T

# Files for tracking seen papers and generated audio
PROCESSED_FILE = Path("processed.json")
VOICE_OUTPUT_DIR = Path("voice")
VOICE_OUTPUT_DIR.mkdir(exist_ok=True)

# Discord channels based on subjects
VOICE_CHANNELS = {
    "astro-ph.CO": int(os.environ["CHANNEL_VOICE_CO"]),
    "astro-ph.EP": int(os.environ["CHANNEL_VOICE_EP"]),
    "astro-ph.GA": int(os.environ["CHANNEL_VOICE_GA"]),
    "astro-ph.HE": int(os.environ["CHANNEL_VOICE_HE"]),
    "astro-ph.IM": int(os.environ["CHANNEL_VOICE_IM"]),
    "astro-ph.SR": int(os.environ["CHANNEL_VOICE_SR"]),
}

# DeepL
#DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")
#translator = deepl.Translator(DEEPL_API_KEY) if DEEPL_API_KEY else None

# OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client_openai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

POST_INTERVAL = 1.2  # seconds


# ================= Utility functions =================
def load_processed():
    if not PROCESSED_FILE.exists():
        return []
    try:
        with open(PROCESSED_FILE) as f:
            data = json.load(f)
            return data.get("processed_ids", [])
    except json.JSONDecodeError:
        return []

def save_processed(processed_list):
    with open(PROCESSED_FILE, "w") as f:
        json.dump({"processed_ids": processed_list[-300:]}, f)

def parse_message(message_content):
    arxiv_id_match = re.search(r'arXiv:\s*(.+)$', message_content, re.MULTILINE)
    title_match = re.search(r'Title:\s*(.+)$', message_content, re.MULTILINE)
    subjects_match = re.search(r'Subjects:\s*(.+)$', message_content, re.MULTILINE)
    truncated_match = re.search(r'Truncated:\s*(True|False)$', message_content, re.MULTILINE)
    abstract_match = re.search(r'Abstract:\s*\n([\s\S]+)', message_content, re.MULTILINE | re.DOTALL)

    parsed_message = {
        "arxiv_id": arxiv_id_match.group(1).strip() if arxiv_id_match else None,
        "title": title_match.group(1).strip() if title_match else None,
        "subjects": subjects_match.group(1).split(",")[0].strip() if subjects_match else None,
        "is_truncated": True if (truncated_match and truncated_match.group(1).strip() == "True") else False,
        "abstract": abstract_match.group(1).strip() if abstract_match else None
    }

    return parsed_message

def split_sentences(text):
    parts = re.split(r'([。！？\n])', text)
    sentences = []
    for i in range(0, len(parts)-1, 2):
        sentence = (parts[i] + parts[i+1]).strip()
        if sentence:
            sentences.append(sentence)
    if len(parts) % 2 == 1 and parts[-1].strip():
        sentences.append(parts[-1].strip())
    return sentences

# def translate(text):
#     if translator:
#         try:
#             result = translator.translate_text(
#                 text, source_lang="EN", target_lang="JA"
#             )
#             return result.text
#         except Exception as e:
#             print("Translation error:", e)
#             return text
#     else:
#         return text


# ================= Translation using OpenAI (fallback) =================
def translate(title, abstract):
    if not client_openai:
        raise ValueError("OpenAI API key is missing.")

    prompt = f"""
You are a professional scientific translator specializing in astrophysics papers.

Translate the following title and abstract into Japanese.

Strict rules:
- Translate faithfully. Do NOT summarize, interpret, or omit any information.
- Preserve the exact scientific meaning.
- Do not add explanations or commentary.

Scientific notation rules:
- Keep equations, variables, and mathematical symbols unchanged.
- Keep element and molecule names unchanged (e.g., Fe, CO, H2).
- Keep units unchanged (e.g., km s^-1, M⊙).
- Keep redshift notation such as z = 2.3 unchanged.
- Keep standard astrophysical abbreviations unchanged (e.g., AGN, CMB, SNR).

Japanese style rules:
- Use natural Japanese suitable for text-to-speech.
- Use polite tone (です / ます).
- Avoid extremely long sentences when possible while preserving meaning.
- Use Japanese punctuation (、。).

Output format:
Return ONLY a valid JSON object with the keys "title" and "abstract". 
Do not include any markdown formatting such as ```json.

Text:
Title: {title}
Abstract: {abstract}
"""

    response = client_openai.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        timeout=30
    )

    result = json.loads(response.choices[0].message.content)
    return result.get("title", title), result.get("abstract", abstract)


# ================= VOICEVOX =================
def synthesise_text(text):
    q = requests.post(
        f"{VOICEVOX_API_URL}/audio_query",
        params={"text": text, "speaker": SPEAKER_ID}
    ).json()

    q["postPhonemeLength"] += 0.5

    r = requests.post(
        f"{VOICEVOX_API_URL}/synthesis",
        params={"speaker": SPEAKER_ID},
        json=q
    )
    r.raise_for_status()
    return r.content
    

def combine_wave_bytes(wav_bytes_list):
    valid_wavs = [wb for wb in wav_bytes_list if wb]
    if not valid_wavs:
        return b""
    
    with wave.open(io.BytesIO(valid_wavs[0]), 'rb') as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())

    for wb in valid_wavs[1:]:
        with wave.open(io.BytesIO(wb), 'rb') as w:
            frames += w.readframes(w.getnframes())

    out_io = io.BytesIO()
    with wave.open(out_io, 'wb') as w:
        w.setparams(params)
        w.writeframes(frames)
    
    return out_io.getvalue()

    
def synthesise(title, subjects_ja, is_truncated, abstract):
    # input texts should be translated to Japanese
    ms_header = "新しいアーカイブ論文が投稿されました。"
    ms_title = f"タイトルは「{title}」です。"
    ms_subjects = f"この論文は「{subjects_ja}」に属しています。"
    ms_truncated = "以下にアブストラクトの冒頭を読み上げます。" if is_truncated else "以下にアブストラクトを読み上げます。"

    wav_list = []
    wav_list.append(synthesise_text(ms_header))
    wav_list.append(synthesise_text(ms_title))
    wav_list.append(synthesise_text(ms_subjects))
    wav_list.append(synthesise_text(ms_truncated))

    for s in split_sentences(abstract):
        if not s.strip():
            continue
        s = s.replace('$', '')
        wav_list.append(synthesise_text(s))

    return combine_wave_bytes(wav_list)


def save_audio(audio_data, output_file):
    with open(output_file, "wb") as f:
        f.write(audio_data)


# ================= Discord =================
async def send_error_to_discord(error_summary, error_details):
    err_channel = client.get_channel(ERR_CHANNEL_ID)
    if err_channel:
        bot_name = "ナースロボ＿タイプarXiv"
        mention = "<@&1115026252156391558>"  # Maintenance role mention

        message = (
            f"🚨 **[{bot_name} | エラーレポート]** 🚨\n"
            f"{mention} システムに異常が発生しました。\n\n"
            f"**【状況報告】**\n{error_summary}\n\n"
            f"**【異常の詳細】**\n```\n{error_details}\n```"
            f"至急、メンテナンスをお願いします。お大事に……。"
        )
        await err_channel.send(message)
    else:
        print(f"Error: Error channel with ID {ERR_CHANNEL_ID} not found. Cannot send error message.")


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    
    if getattr(client, "has_run", False):
        return
    client.has_run = True

    print("Nurse Robot Type T is ready!")

    processed_list = load_processed()
    processed_set = set(processed_list)

    try:
        channel = client.get_channel(ABSTRACT_CHANNEL_ID)

        if channel is None:
            print(f"Error: Channel with ID {ABSTRACT_CHANNEL_ID} not found. Check authentication and channel ID.")
            await client.close()
            return

        # Fetch recent messages and process
        recent_messages = [msg async for msg in channel.history(limit=150)]
        recent_messages.reverse()  # Process from oldest to newest

        processed_count = 0
        MAX_PROCESS = 5
        for msg in recent_messages:
            if str(msg.id) in processed_set:
                continue

            parsed = parse_message(msg.content)
            if not parsed["arxiv_id"] or not parsed["title"] or not parsed["subjects"] or not parsed["abstract"]:
                continue

            print(f"Processing {parsed['arxiv_id']} ...")

            # Translation
            try:
                title_ja, abstract_ja = await asyncio.to_thread(translate, parsed["title"], parsed["abstract"])
            except Exception as e:
                err_trace = traceback.format_exc()
                await send_error_to_discord(f"翻訳エラー： {parsed['arxiv_id']} の翻訳の失敗。\nタイトルおよびアブストラクトは英語で返されます。", err_trace)
                title_ja, abstract_ja = parsed["title"], parsed["abstract"]

            subjects_mapping = {
                "astro-ph.CO": "宇宙論及び銀河を除く天体物理学",
                "astro-ph.EP": "地球物理学および惑星物理学",
                "astro-ph.GA": "銀河天体物理学",
                "astro-ph.HE": "高エネルギー天体物理学",
                "astro-ph.IM": "検出器と測定手法",
                "astro-ph.SR": "太陽物理学および恒星物理学"
            }
            subjects_ja = subjects_mapping.get(parsed["subjects"], parsed["subjects"])

            # Synthesis
            output_file = VOICE_OUTPUT_DIR / f"{parsed['arxiv_id'].replace('/', '_')}.wav"
            try:
                audio_data = await asyncio.to_thread(synthesise, title_ja, subjects_ja, parsed["is_truncated"], abstract_ja)
                save_audio(audio_data, output_file)
            except Exception as e:
                err_trace = traceback.format_exc()
                await send_error_to_discord(f"音声合成エラー： {parsed['arxiv_id']} の音声合成の失敗。\n処理はスキップされます", err_trace)
                continue

            print(f"Processed {parsed['arxiv_id']} - saved to {output_file}")

            # Post to voice channel
            try:
                voice_channel_id = VOICE_CHANNELS.get(parsed["subjects"])
                if voice_channel_id:
                    vc = client.get_channel(voice_channel_id)
                    if vc:
                        text_translated = f"**【{parsed['arxiv_id']}】{title_ja}**\n\n{abstract_ja}"
                        if len(text_translated) > 1990:
                            text_translated = text_translated[:1990] + "..."
                        await vc.send(text_translated, file=discord.File(output_file))
                    else:
                        raise ValueError(f"Voice channel with ID {voice_channel_id} not found.")
            except Exception as e:
                err_trace = traceback.format_exc()
                await send_error_to_discord(f"ボイスチャンネル送信エラー： {parsed['arxiv_id']} のボイスチャンネルへの送信の失敗。", err_trace)
                
            processed_list.append(str(msg.id))
            processed_set.add(str(msg.id))
            save_processed(processed_list)  # Save after each message to avoid data loss

            processed_count += 1
            if processed_count >= MAX_PROCESS:
                print(f"Reached the maximum limit of {MAX_PROCESS} papers. Stopping for now.")
                break

            await asyncio.sleep(POST_INTERVAL)  # To avoid hitting rate limits

        remaining_count = 0
        for msg in recent_messages:
            if str(msg.id) not in processed_set:
                parsed = parse_message(msg.content)
                if parsed["arxiv_id"] and parsed["title"] and parsed["subjects"] and parsed["abstract"]:
                    remaining_count += 1

        log_channel = client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            bot_name = "ナースロボ＿タイプarXiv"
            
            if remaining_count > 0:
                report_msg = (
                    f"🎙️ **[{bot_name} | 音声変換レポート]**\n"
                    f"お疲れ様です。当機による音声化処理が完了しました。今回処理した論文は **{processed_count}** 件です。\n"
                    f"まだ未変換のアブストラクトが **{remaining_count}** 件残っています。引き続き、適度な休憩を挟みつつ確認をお願いします。"
                )
            else:
                report_msg = (
                    f"🎙️ **[{bot_name} | 音声変換レポート]**\n"
                    f"お疲れ様です。当機による音声化処理が完了しました。今回処理した論文は **{processed_count}** 件です。\n"
                    f"現在のところ、未変換のアブストラクトはありません。本日の業務は終了ですね。お休みなさい、お大事に。"
                )
            await log_channel.send(report_msg)
        else:
            print(f"Error: Log channel with ID {LOG_CHANNEL_ID} not found. Cannot send log message.")
        
        save_processed(processed_list)  # Final save
        print("All done. Processed IDs saved.")
    except Exception as e:
        err_trace = traceback.format_exc()
        print(f"Critical error during processing: {e}\n")
        await send_error_to_discord("音声変換プログラム（voice.py）の実行中に致命的なエラーが発生しました。", err_trace)

    finally:
        await client.close()  # Close the client after processing


# ================== Entry point =================
if __name__ == "__main__":
    client.run(DISCORD_VOICE_TOKEN)