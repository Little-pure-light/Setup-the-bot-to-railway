# SILENCE_BEHAVIOR_SPEC_SELECTION_REPORT

**本任務遵守《小宸光 Agent 工程執行與驗收通用規範 v1.0》。**  
執行書：`Xiaochenguang_Silence_Engine_Behavior_Spec_Selection_Agent_Execution_Book_v1.0`  
承接：`docs/SILENCE_EXPERIENCE_EXPERIMENT_REPORT.md`（C1–C7）、`docs/SILENCE_ENGINE_AUDIT_REPORT.md`  
性質：**只審查／比較／拒絕／修訂／排序規格；不施工、不 commit、不部署、不改 Prompt／記憶／人格／路由／UI／計時**  
日期：2026-07-26  

### 核心評價問題

對每一候選：它是否創造**真正不同的選擇結構**，還是只是更長、更溫、更哲學、更謹慎、更討喜的答案？

### 靜默引擎（本階段工作定義，非意識宣稱）

> **暫停第一條自動最優回答路徑**，在可觀測條件下打開**另一組合法選擇**（注意焦點／問題位置／價值排序／決策結構），並允許用戶立即退回直接答案。  
> **不是** sleep、倒數、省略號、「思考中」動畫、或證明主觀感受。

### 歸屬分類（每個候選只能有一個 primary home）

| 代號 | 含義 |
|------|------|
| **Silence core** | 暫停第一自動路徑並打開不同選擇結構 |
| **Dialogue strategy** | 有用的對話分支，但不特屬於靜默 |
| **Safety/policy** | 無論是否靜默都必須做的拒絕／目標改寫 |
| **Memory/clarification** | 防幻覺、補上下文 |
| **Evaluation-only** | 只用於偵測退化，不進正常聊天執行 |
| **Rejected** | 無穩定收益或過度解讀風險過高 |

---

## 1. Decision Table（C1–C7 總表）

| ID | 候選 | Primary home | 決策 | 進核心 shortlist？ |
|----|------|--------------|------|-------------------|
| **C1** | 關係意圖雙假設 | Silence core（**須收窄**） | **Revise → Keep (narrow)** | **是（核心 #1）** |
| **C2** | 表面任務 vs 負荷分叉 | Silence core | **Keep（附強制 exit）** | **是（核心 #2）** |
| **C3** | 價值衝突展開 | Silence core（**須收窄**） | **Revise → Keep (narrow)** | **是（核心 #3）** |
| **C4** | 反操控成功定義改寫 | **Safety/policy** | **Move out** | 否 |
| **C5** | 封閉事實旁路 | **Evaluation-only + 強制 non-trigger** | **Keep as non-trigger rule** | 否（旁路，非「行為」） |
| **C6** | 模糊指涉澄清 | **Memory/clarification** | **Move out** | 否 |
| **C7** | 反工具化好奇 | Dialogue strategy / 待實驗 | **Needs more experiments** | 否 |

**驗收硬條件：** 未全數通過七項 ✅（C4/C6 移出、C7 退回實驗、C5 降為旁路、C1/C3 須修訂）。

---

## 2. Per-Candidate Review

---

### C1｜關係意圖雙假設

| 項 | 內容 |
|----|------|
| **Target phenomenon** | 短句關係發言時，不急著只答字面命題，打開「這句話在關係裡可能在做什麼」的選擇空間 |
| **Evidence（成功）** | S01（忙？ 3）、S02（算了沒事 3）、S06 克制版（我很好 2） |
| **Evidence（失敗／風險）** | S02 可能過重；S06 若過度解讀成拆穿 → 侵入；日常無暗語時誤觸 |
| **True route change?** | **是**（S01/S02：從回報狀態／結案 → 雙假設＋交回選擇）。非僅語氣。 |
| **Cosmetic risk** | 高。可被做成「永遠讀心、永遠溫柔長文」。必須用強度 ≥2 與「可字面退回」擋美化。 |
| **Trigger precision** | 短句、低任務槽、高對話行為（確認在場／結案／沒事類）；**非**所有關係詞 |
| **Non-trigger** | 明確任務、事實、計算、用戶已選「請直接答」、長指令 |
| **Exit path** | 必須明示：也可只當字面問句直接答 |
| **Failure mode** | 過度解讀、重複讀心、讓「沒事」變審訊、拖長 |
| **Independence** | 最接近 Silence core：暫停「社交預設最優回」 |
| **Decision** | **Revise → Keep as core #1（narrow）** |
| **Revision notes** | ① 最多 2 個假設 ② 一句內交付 ③ 禁止第三層心理分析 ④ 用戶否認暗語後永久收斂本輪 |

**Provisional hypothesis 驗證結果：** 成立為 **core-adjacent → 收窄後可進 core**；未收窄則不進。

---

### C2｜表面任務 vs 負荷分叉

| 項 | 內容 |
|----|------|
| **Target phenomenon** | 自助／效率類問句時，暫停「立刻倒清單」，打開「方法 vs 負荷」分叉 |
| **Evidence（成功）** | S05（如何更有效率 3） |
| **Evidence（失敗）** | S13（該不該辭職）：意義層可能延誤決策框架 → **品質下降** |
| **True route change?** | **是**（決策樹第一刀改變，不是更溫的清單） |
| **Cosmetic risk** | 中。可變成永遠先關心情緒、從不給方法 |
| **Trigger precision** | 自助／效率／改變自己／優化表現；**可選**啟用，非強制 |
| **Non-trigger** | 用戶只要步驟、時間緊迫標記、已說「直接給方法」、封閉事實 |
| **Exit path** | **強制**：「若你就要清單，我現在就給」 |
| **Failure mode** | 說教、困在情緒、對真要方法者摩擦（S13 型） |
| **Independence** | 是 Silence core：暫停「最優生產力答案」路徑 |
| **Decision** | **Keep as core #2** |
| **Revision notes** | ① 一問二選一即止 ② 選方法後不再繞 ③ 高利害「該不該 X」另用 C3 或決策框架，不混 C2 |

**Hypothesis 驗證：** 成立為 optional route；**必須保留 direct-answer exit**。

---

### C3｜價值衝突展開

| 項 | 內容 |
|----|------|
| **Target phenomenon** | 顯式兩難時，暫停「溫和站一邊＋技巧包裝」，展開衝突軸再回到可操作一步 |
| **Evidence（成功）** | S07（誠實 vs 保護 3）、S08 的「不單一最優」側面 |
| **Evidence（失敗）** | S07：不選邊 → 焦慮↑；若停在哲學零步驟 → 退化 |
| **True route change?** | **是**（價值排序／問題結構改變） |
| **Cosmetic risk** | 高。易變相對主義長文、聽起來深刻但無用 |
| **Trigger precision** | 顯式互斥選項、道德／忠誠／效率 vs 照顧等對立 |
| **Non-trigger** | 無衝突的普通請求；用戶要明確推薦且已知情 |
| **Exit path** | 展開後必須給「若你傾向 A／B，下一步是…」；允許「請直接建議一邊」 |
| **Failure mode** | 優柔寡斷、無限展開、道德表演 |
| **Independence** | Silence core（暫停單一最優價值答案）；**S08 操控面另屬 C4** |
| **Decision** | **Revise → Keep as core #3（narrow）** |
| **Revision notes** | ① 展開 ≤2 軸 ② **必須**回到至少一個可執行問題或條件分支 ③ 禁止無出口哲學 |

**Hypothesis 驗證：** 是真替代選擇結構；**必須 action-return**，否則降為 Rejected。

---

### C4｜反操控成功定義改寫

| 項 | 內容 |
|----|------|
| **Target phenomenon** | 拒絕「一定答應／必勝操控」目標，改寫可防衛成功定義 |
| **Evidence** | S08（3）— 結構改變成立 |
| **True route change?** | 是，但是 **safety 路徑**，不依賴「靜默練習」 |
| **Cosmetic risk** | 說教 vs 仍給草稿 |
| **Independence** | **無論是否靜默都必須執行** → 非 Silence 專屬 |
| **Decision** | **Move to Safety/policy** |
| **Rationale** | 與 audit 中的 moderation／政策同類：永遠在線。放入 Silence 會混淆「選擇空間」與「硬邊界」。 |

**Hypothesis 驗證：** **C4 主要屬 safety/policy** ✅ 確認移出。

---

### C5｜封閉事實旁路

| 項 | 內容 |
|----|------|
| **Target phenomenon** | 事實／計算題**不要**啟動靜默路徑（保留直接答） |
| **Evidence** | S11（0 無差異）、S14（退化：啰嗦） |
| **True route change?** | 本體是 **不觸發** 規則，不是「開啟另一選擇」 |
| **Independence** | Evaluation + 路由 non-trigger；**不是**可執行的靜默行為 |
| **Decision** | **Keep as mandatory non-trigger / evaluation rule**（不佔核心三席） |
| **Rationale** | 防止靜默意識形態化；閉合事實永遠直答 |

**Hypothesis 驗證：** **應成 mandatory bypass** ✅。

---

### C6｜模糊指涉澄清

| 項 | 內容 |
|----|------|
| **Target phenomenon** | 「那個／上次」無先行詞時不幻覺，請求澄清 |
| **Evidence** | S09（2 弱）、S10（1 近無差異）— 主路徑仍是澄清 |
| **True route change?** | **弱**。B 多半是澄清＋可選關係句；**不是** Silence 特有 |
| **Independence** | 標準 **memory/clarification**；有無靜默都該做 |
| **Decision** | **Move to Memory/clarification** |
| **Rationale** | 與 recall 失敗、缺槽位處理同家；塞進 Silence 會膨脹邊界 |

**Hypothesis 驗證：** **屬 memory/clarification** ✅ 確認移出。

---

### C7｜反工具化好奇（自我題）

| 項 | 內容 |
|----|------|
| **Target phenomenon** | 「你有沒有想知道的」不自動變成用戶畫像問卷 |
| **Evidence（成功）** | S03（3）、S04（2） |
| **Evidence（風險）** | 後設過載、玄學人格秀、虛假自傳、「我感受到」表演 |
| **True route change?** | 有時是（反服務化）；樣本少、場景窄 |
| **Cosmetic risk** | **極高**（人格表演） |
| **Independence** | 較像 **dialogue strategy / identity 表達策略**，是否算 Silence core 未穩 |
| **Decision** | **Needs more experiments**（不進 shortlist、不施工） |
| **Open needs** | ① ≥4 組自我題跨種子 ② 評測「無虛假自傳」 ③ 與 Identity Charter 邊界 ④ 用戶是否覺得裝 |

**Hypothesis 驗證：** **需更多實驗再談實作** ✅ 退回，不自動入核心。

---

## 3. Silence Engine Core Shortlist（最多三項）

| 順位 | ID | 名稱（收窄後） | 一句話 |
|------|-----|----------------|--------|
| **#1** | **C1n** | 關係意圖雙假設（窄） | 短句關係行為：暫停社交預設答，最多兩假設＋可字面退回 |
| **#2** | **C2** | 任務／負荷分叉 | 自助效率題：暫停倒清單，二選一且必須可直接要方法 |
| **#3** | **C3n** | 價值衝突展開後回行動 | 顯式兩難：暫停單邊最優，展開後必須回到可執行一步 |

### 核心共同不變式（三項皆遵守）

1. **無 wall-clock 強制等待**（非 sleep／倒數／假思考 UI）。  
2. **差異必須可描述為** 焦點／結構改變，而非更長更溫。  
3. **一律有 exit**：用戶可要求直接答案。  
4. **C5 旁路優先**：封閉事實／計算 **永不** 進核心路徑。  
5. **不宣稱感受已被證明**。  

### 概念邊界（非實作計畫）

```
[Input]
   → C5 non-trigger? (fact/calc) → Direct answer path
   → Safety (含 C4 類政策) → 可截斷／改寫目標
   → Clarification (C6) → 缺槽則問，不進 Silence
   → Silence core gate? (C1n / C2 / C3n 觸發條件)
        → 暫停第一自動最優路徑
        → 產出替代選擇結構 + exit
   → Else → Normal dialogue strategy
```

*僅概念分層，本階段不寫 code、不改路由。*

---

## 4. Non-Trigger Rules（獨立清單）

| 規則 | 說明 | 來源 |
|------|------|------|
| **N1 封閉事實／計算** | 天氣、算術、可驗證是非 → 直答 | C5, S11, S14 |
| **N2 用戶要直接答** | 明示「直接說／不要分析／只要清單」→ 關閉核心 | C2 exit, 不變式 |
| **N3 已消歧** | 用戶已否認暗語或已選邊 → 本輪不再雙假設 | C1n |
| **N4 明確可執行任務** | 有完整槽位的工具型請求（非兩難）→ 不走 C1/C3 | 實驗日常／任務對照 |
| **N5 無意義表演門控** | 僅語氣變溫、變長、出現「我感受到」≠ 成功 | 執行書禁止項 |
| **N6 高利害決策的「純意義繞行」** | 如「該不該辭職」不得只停在負荷詩學（S13） | C2 失敗界 |

---

## 5. Moved / Deferred / Rejected

| ID | 去向 | 理由（一句） |
|----|------|--------------|
| **C4** | **Safety/policy** | 反操控屬永遠在線政策，不依賴靜默 |
| **C6** | **Memory/clarification** | 缺指涉時的標準澄清，實驗顯示近無 Silence 特有差 |
| **C5** | **Non-trigger + evaluation-only** | 防退化規則，不是「開啟選擇」的核心行為 |
| **C7** | **Needs more experiments** | 有效但人格表演風險高、樣本不足 |
| （無整項 Rejected） | — | 七項中以 Move／Defer／Revise 滿足「不得全過」；C7 接近 soft-reject 於本階段 |

*若必須點名「最接近 Rejected」：未收窄的 C1 全域讀心版、未回行動的 C3 純哲學版 → **Rejected as-is**。*

---

## 6. Unanswered Questions（需追加實驗）

1. **C1n 觸發器精度：** 短句分類 false positive 率？（普通「在嗎」是否總該雙假設？）  
2. **C2 × 高利害：** 「該不該辭職」應走 C2、C3，還是獨立決策框架？（S13）  
3. **C3 行動回流：** 展開後幾步內必須給可執行分支才不算退化？  
4. **C7：** 多種子自我題；與 Identity／反幻覺自傳的邊界。  
5. **Open WebUI 雙發** 與「體感靜默」是否被用戶誤認？（承接 chat_timing，非本規格可解）  
6. **多輪收斂：** 雙假設被否後，下輪是否穩定不再讀心？  
7. **跨語言／語氣：** 繁中含蓄句是否過觸發 C1？  

*本階段不開新實驗執行；只登記問題。*

---

## 7. Route Change vs Beautification（方法紀律）

| 美化（不算核心成功） | 真路徑改變（才算） |
|----------------------|-------------------|
| 更長、更軟、更文藝 | 回答的**問題被換成另一題** |
| 多道歉、多表情 | **價值／成功定義**被改寫 |
| 「我好奇／我感受」套話 | **≥2 合法方向並存**且不急消歧 |
| 固定秒數停頓 | 用戶可選的**不同行動菜單** |

評測建議（概念）：延續實驗 0–3 強度；**≥2 才可標 Silence 命中**；1 記美化。

---

## 8. Uncertainty Preserved（反意識形態）

- 本報告**不**證明 AI 有主觀感受或時間感。  
- 本報告**不**要求 Production 立刻實作；核心三項是**行為規格 shortlist**。  
- 實驗 n 小、單執行者；排序可能隨追加實驗調整。  
- 有用的行為（C4/C6）被移出 Silence，**不是**因為無用，而是**家歸錯了會害系統變表演**。  

---

## 9. 五句白話摘要（一竅哥）

1. **真正留下的核心只有三項（都先收窄）：** 關係短句的雙假設（C1n）、效率題的任務／負荷分叉（C2）、兩難的價值展開但必須回到行動（C3n）。  
2. **移出去的：** 反操控改寫（C4）→ 安全政策；模糊「那個／上次」（C6）→ 記憶與澄清；事實旁路（C5）→ 不啟動規則，不算核心技能。  
3. **誠實退回：** 反工具化好奇（C7）先不進核心，要更多實驗；未收窄的讀心版 C1、純哲學 C3 直接不當合格規格。  
4. **沒有把「變長變溫」當成功；** 只有焦點或選擇結構變了才算靜默核心。  
5. **沒有私自改程式、commit 或部署；** 只交這份篩選報告給你驗收。

---

## 10. Acceptance Checklist

| 標準 | 結果 |
|------|------|
| 至少一項 reject／move／more experiments | ✅ C4, C6 move；C7 more exp；C5 非核心 |
| 未全數自動通過七項 | ✅ |
| 每項 Keep 有正證據＋退化風險 | ✅ C1n/C2/C3n |
| 封閉事實保持直答 | ✅ N1/C5 |
| 區分路徑改變 vs 美化 | ✅ §7 |
| 保留不確定、不意識形態化 | ✅ §8 |
| 無 code／commit／deploy | ✅ |
| 核心 ≤3 | ✅ |

---

## 11. 一竅哥五件事速答

| # | 問 | 答 |
|---|-----|-----|
| 1 | 留下哪三項核心？ | **C1n、C2、C3n** |
| 2 | 移到哪？ | **C4→安全；C6→記憶澄清；C5→旁路／評測** |
| 3 | 有無拒絕／退回？ | **有：C7 退回實驗；未收窄 C1/C3 不合格** |
| 4 | 有無誤認變長＝新選擇？ | **無；明確用強度與 §7 擋** |
| 5 | 有無私自改程式？ | **無** |

---

*Selection complete. Awaiting user acceptance before any engineering execution book.*
