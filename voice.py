# voice.py
import discord
import os
import json
import re
import requests
import asyncio
import io
import wave
from pathlib import Path
import deepl
from dotenv import load_dotenv
load_dotenv()


# ================= SETTINGS =================
DISCORD_VOICE_TOKEN = os.environ["DISCORD_VOICE_TOKEN"]
ABSTRACT_CHANNEL_ID = int(os.environ["CHANNEL_ABSTRACT"])

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
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")
translator = deepl.Translator(DEEPL_API_KEY) if DEEPL_API_KEY else None

POST_INTERVAL = 1.2  # seconds


# ================= Utility functions =================
def load_processed():
    if not PROCESSED_FILE.exists():
        return set()
    with open(PROCESSED_FILE) as f:
        data = json.load(f)
        return set(data.get("processed_ids", []))

def save_processed(processed_ids):
    with open(PROCESSED_FILE, "w") as f:
        json.dump({"processed_ids": list(processed_ids)}, f)

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

def translate(text):
    if translator:
        try:
            result = translator.translate_text(
                text, source_lang="EN", target_lang="JA"
            )
            return result.text
        except Exception as e:
            print("Translation error:", e)
            return text
    else:
        return text


# ================= VOICEVOX =================
def synthesise_text(text):
    try:
        q = requests.post(
            f"{VOICEVOX_API_URL}/audio_query",
            params={"text": text, "speaker": SPEAKER_ID}
        ).json()

        r = requests.post(
            f"{VOICEVOX_API_URL}/synthesis",
            params={"speaker": SPEAKER_ID},
            json=q
        )
        r.raise_for_status()
        return r.content
    except Exception as e:
        print("Voice synthesis error:", e)
        return b""
    

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
        wav_list.append(synthesise_text(s))

    return combine_wave_bytes(wav_list)


def save_audio(audio_data, output_file):
    with open(output_file, "wb") as f:
        f.write(audio_data)


# ================= Discord =================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print("Nurse Robot Type T is ready!")

    processed = load_processed()
    channel = client.get_channel(ABSTRACT_CHANNEL_ID)
    new_processed = set(processed)

    if channel is None:
        print(f"Error: Channel with ID {ABSTRACT_CHANNEL_ID} not found. Check authentication and channel ID.")
        await client.close()
        return

    recent_messages = [msg async for msg in channel.history(limit=150)]
    recent_messages.reverse()  # Process from oldest to newest
    async for msg in recent_messages:
        if str(msg.id) in processed:
            continue

        parsed = parse_message(msg.content)
        if not parsed["arxiv_id"] or not parsed["title"] or not parsed["subjects"] or not parsed["abstract"]:
            continue

        print(f"Processing {parsed['arxiv_id']} ...")

        # Translation
        title_ja = translate(parsed["title"])
        abstract_ja = translate(parsed["abstract"])
        subjects_mapping = {
            "astro-ph.CO": "宇宙論及び銀河を除く天体物理学",
            "astro-ph.EP": "地球物理学および惑星物理学",
            "astro-ph.GA": "銀河天体物理学",
            "astro-ph.HE": "高エネルギー天体物理学",
            "astro-ph.IM": "検出器と測定手法",
            "astro-ph.SR": "太陽物理学および恒星系物理学"
        }
        subjects_ja = subjects_mapping.get(parsed["subjects"], parsed["subjects"])

        # Synthesis
        output_file = VOICE_OUTPUT_DIR / f"{parsed['arxiv_id'].replace('/', '_')}.wav"
        audio_data = synthesise(title_ja, subjects_ja, parsed["is_truncated"], abstract_ja)
        save_audio(audio_data, output_file)

        print(f"Processed {parsed['arxiv_id']} - saved to {output_file}")

        # Post to voice channel
        voice_channel_id = VOICE_CHANNELS.get(parsed["subjects"])
        if voice_channel_id:
            vc = client.get_channel(voice_channel_id)
            if vc:
                await vc.send(file=discord.File(output_file))
            else:
                print(f"Error: Voice channel with ID {voice_channel_id} not found.")

        new_processed.add(str(msg.id))
        await asyncio.sleep(POST_INTERVAL)  # To avoid hitting rate limits

    save_processed(new_processed)
    print("All done. Processed IDs saved.")
    await client.close()


# ================== Entry point =================
if __name__ == "__main__":
    client.run(DISCORD_VOICE_TOKEN)