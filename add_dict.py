import requests

VOICEVOX_API_URL = "http://127.0.0.1:50021"

# List of words to add/update in the user dictionary
words = [
    ("赤方偏移", "セキホウヘンイ", 6),
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
]

# Fetch current user dictionary
res = requests.get(f"{VOICEVOX_API_URL}/user_dict")
current_dict = res.json()

# Create a mapping from surface form to UUID for existing entries
surface_to_uuid = {data["surface"]: uuid for uuid, data in current_dict.items()}

# Add or update words in the user dictionary
for surface, pronunciation, accent_type in words:
    params = {
        "surface": surface,
        "pronunciation": pronunciation,
        "accent_type": accent_type,
        "word_type": "PROPER_NOUN"
    }
    
    try:
        if surface in surface_to_uuid:
            # when the word already exists, update it (PUT)
            word_uuid = surface_to_uuid[surface]
            requests.put(f"{VOICEVOX_API_URL}/user_dict_word/{word_uuid}", params=params)
            print(f"Successfully updated: {surface}")
        else:
            # when the word does not exist, add it (POST)
            requests.post(f"{VOICEVOX_API_URL}/user_dict_word", params=params)
            print(f"Successfully added: {surface}")
    except Exception as e:
        print(f"Error: {surface} - {e}")