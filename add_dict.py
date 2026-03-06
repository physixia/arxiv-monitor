import requests
import unicodedata

VOICEVOX_API_URL = "http://127.0.0.1:50021"

# List of words to add or update in the user dictionary
words = [
    ("赤方偏移", "セキホウヘンイ", 6),
    ("赤方", "セキホウ", 0),
    ("降着円盤", "コウチャクエンバン", 6),
    ("活動銀河核", "カツドウギンガカク", 8),
    ("中性子星", "チュウセイシセイ", 6),
    ("keV", "ケヴ", 2),
    ("MeV", "メヴ", 2),
    ("GeV", "ジェヴ", 2),
    ("TeV", "テヴ", 2),
    ("PeV", "ペヴ", 2),
    ("EeV", "イーヴ", 2),
    ("GW", "ジーダブリュー", 4),
    ("系外惑星", "ケイガイワクセイ", 6),
    ("安定性", "アンテイセイ", 0),
    ("異方性", "イホウセイ", 0),
    ("Ly", "ライマン", 2),
    ("星間", "セイカン", 0),
    ("星風", "セイフウ", 0),
    ("HII", "エイチツー", 2),
    ("主星", "シュセイ", 0),
    ("伴星", "バンセイ", 0),
    ("本研究", "ホンケンキュウ", 2),
    ("歳差", "サイサ", 0),
]

# Function to normalize strings for consistent comparison
def normalize_string(s):
    return unicodedata.normalize('NFKC', s).lower()

res = requests.get(f"{VOICEVOX_API_URL}/user_dict")
current_dict = res.json()

# Create a mapping from normalized surface forms to their corresponding UUIDs
surface_to_uuid = {normalize_string(data["surface"]): uuid for uuid, data in current_dict.items()}

for surface, pronunciation, accent_type in words:
    params = {
        "surface": surface,
        "pronunciation": pronunciation,
        "accent_type": accent_type,
        "word_type": "PROPER_NOUN"
    }
    
    # Compare normalized surface forms to find if the word already exists in the dictionary
    normalized_surface = normalize_string(surface)
    
    try:
        if normalized_surface in surface_to_uuid:
            word_uuid = surface_to_uuid[normalized_surface]
            requests.put(f"{VOICEVOX_API_URL}/user_dict_word/{word_uuid}", params=params)
            print(f"Successfully updated: {surface}")
        else:
            requests.post(f"{VOICEVOX_API_URL}/user_dict_word", params=params)
            print(f"Successfully added: {surface}")
    except Exception as e:
        print(f"Error: {surface} - {e}")