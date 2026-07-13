# import_conv1.py
# 功能：從 JSON 匯入對話 → 產生 1536 維嵌入 → 寫入 Supabase + Pinecone
# 依賴：pip install --upgrade python-dotenv tqdm openai supabase pinecone

導入作業系統
導入系統
導入 json
導入 uuid
從 datetime 導入 datetime、timezone
from dotenv import load_dotenv
from tqdm import tqdm
from supabase import create_client
from openai import OpenAI
來自松果進口松果

# =====設定=====
TABLE_NAME = "xiaochenguang_reflections"
EMBED_MODEL = "text-embedding-3-small" # 1536 維
預期維度 = 1536

# =====讀取ENV =====
load_dotenv()
REQ = ["SUPABASE_URL"、"SUPABASE_KEY"、"OPENAI_API_KEY"、"PINECONE_API_KEY"、"PINECONE_INDEX_NAME"]
miss = [k for k in REQ if not os.getenv(k)]
如果錯過：
    print(f"❌缺少必要環境變數：{', '.join(miss)}")
    sys.exit(1)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# =====初始化客戶端=====
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
松果索引 = pc.Index(PINECONE_INDEX_NAME)

# ===== 輔助函式 =====
def _get_timestamp() -> str:
    返回 datetime.now(timezone.utc).isoformat()

def _build_content(conv: dict) -> str:
    rc = (conv.get("reflection_content") or "").strip()
    如果 rc：
        返回 rc
    u = (conv.get("user_message") or "").strip()
    a = (conv.get("assistant_message") or "").strip()
    如果你或a：
        return f"用戶：{u}\nAI：{a}".strip()
    返回 ””

def _embed(text: str) -> list[float]:
    res = openai_client.embeddings.create(model=EMBED_MODEL, input=text)
    返回 res.data[0].embedding

# =====主流程=====
def import_from_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        conversations = json.load(f)

    print(f"📦 匯入 {len(conversations)} 筆對話，開始寫入...")
    ok_sb = ok_pc = 已跳過 = 0

    for tqdm(conversations, desc="匯入細節",unit="筆")中的轉換：
        嘗試：
            content = _build_content(conv)
            如果沒有內容：
                跳過 += 1
                繼續

            emb = _embed(content)
            如果 emb 不為空或 len(emb) 不等於 EXPECTED_DIM：
                print(f"⚠️嵌入長度異常（{len(emb) if emb else 'None'}），已跳過。")
                跳過 += 1
                繼續

            rec_id = conv.get("id", str(uuid.uuid4()))
            記錄 = {
                "id": rec_id,
                "user_id": conv.get("user_id", "system-import"),
                "conversation_id": conv.get("conversation_id", str(uuid.uuid4())),
                "reflection_content": 內容，
                "reflection_level": conv.get("reflection_level", []),
                "confidence_score": float(conv.get("confidence_score", 1.0)),
                「嵌入」：emb，
                "metadata": conv.get("metadata", {}),
                "created_at": conv.get("created_at", _get_timestamp()),
                "updated_at": _get_timestamp()
            }

            # 寫入Supabase
            supabase_client.table(TABLE_NAME).upsert(record).execute()
            ok_sb += 1

            # 寫入 Pinecone
            松果索引.upsert(vectors=[{
                "id": rec_id,
                “值”：emb，
                "元資料": {
                    "user_id": record["user_id"],
                    "conversation_id": record["conversation_id"],
                    "reflection_content": content[:500], # 限制長度
                    "created_at": record["created_at"]
                }
            }])
            ok_pc += 1

        除異常 e 外：
            print(f"\n❌ 處理失敗：{e}")
            跳過 += 1

    print(f"\n✅ 完成！Supabase: {ok_sb} 筆 | 松果: {ok_pc} 筆 | 跳過: {skipped} 筆")

# ===== 入口 =====
如果 __name__ == "__main__":
    如果 len(sys.argv) < 2：
        print(" 方法：python import_conv1.py <your_conversations.json>")
        sys.exit(1)
    import_from_json(sys.argv[1])