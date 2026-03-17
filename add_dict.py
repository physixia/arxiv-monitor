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
    ("等方性", "トウホウセイ", 0),
    ("異方的", "イホウテキ", 0),
    ("等方的", "トウホウテキ", 0),
    ("Ly", "ライマン", 2),
    ("星間", "セイカン", 0),
    ("星風", "セイフウ", 0),
    ("HII", "エイチツー", 4),
    ("主星", "シュセイ", 0),
    ("伴星", "バンセイ", 0),
    ("本研究", "ホンケンキュウ", 2),
    ("歳差", "サイサ", 0),
    ("ESPRESSO", "エスプレッソ", 6),
    ("遠赤外線", "エンセキガイセン", 2),
    ("近赤外線", "キンセキガイセン", 2),
    ("遠赤外", "エンセキガイ", 5),
    ("近赤外", "キンセキガイ", 5),
    ("系統的", "ケイトウテキ", 0),
    ("赤色巨星分枝", "セキショクキョセイブンシ", 9),
    ("ハッブル宇宙望遠鏡", "ハッブルウチュウボウエンキョウ", 3),
    ("フォトメトリー", "フォトメトリー", 4),
    ("z", "ゼット", 3),
    ("=", "イコール", 0),
    ("<", "ショウナリ", 0),
    (">", "ダイナリ", 0),
    ("Myr", "ミリオンイヤーズ", 6),
    ("FirstLight", "ファーストライト", 6),
    ("深宇宙", "シンウチュウ", 4),
    ("原始星", "ゲンシセイ", 4),
    ("気体相", "キタイソウ", 3),
    ("AGN", "エイジイエヌ", 6),
    ("共存", "キョウゾン", 0),
    ("QPO", "キューピーオー", 4),
    ("Fermi-LAT", "フェルミラット", 6),
    ("上方", "ジョウホウ", 0),
    ("赤色巨星", "セキショクキョセイ", 6),
    ("分枝", "ブンシ", 2),
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