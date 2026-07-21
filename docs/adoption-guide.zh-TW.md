---
id: DOC-adoption-guide-zh-TW
layer: doc
purpose: 提供採用者判斷是否導入可攜 harness、整合到另一個專案、撤回，以及量測本地效益的繁中指南。
read_when: 在另一個 repository 加入 harness pointer 前，或向專案負責人說明控制權與證據邊界時。
depends_on: [../SETUP.md, ../docs/runtime_activation_contract.md, ../docs/codex_harness_integration.md, ../docs/evidence.md]
used_by: [README, README.zh-TW]
tags: [adoption, onboarding, codex, hermes, rollback, evidence, zh-TW]
retrieval_keywords: [導入 harness, 整合其他專案, Codex AGENTS.md, Hermes shim, rollback marker, 量測本地效益]
---

# 在你的專案導入 harness

[English](adoption-guide.md)

當你要讓另一個 repository 使用此 harness 時，請讀本指南。不必把完整指令集複製進目標 repository；保留本 repository 作為 harness root，並在目標專案的 agent instructions 加入一段產生的 pointer 即可。

## 先判斷是否適用

| 你的任務或專案 | 是否導入？ | 原因 |
|---|---:|---|
| 長任務或多步驟工作 | 是 | 它會先分類任務，只載入需要的 route。 |
| 多 agent 或彼此衝突的輸出 | 是 | 它加入明確的責任歸屬、驗證與整合。 |
| release、completion、安全、權限、hook、CI 或 governance 工作 | 是 | 錯誤的完成聲稱代價高。 |
| 建立或維護 AI harness | 是 | adaptive review loop 可提出可量測的改善建議。 |
| 獨立問答、查詢、typo 或單檔機械修改 | 否 | 額外程序的成本大於效益。 |

它不會讓模型本身變得更聰明。它的目的，是減少不必要的 context、審慎分派工作，並使完成聲稱可被稽核。

## 你控制什麼，哪些留在內部

你可以控制何時啟用、哪些 repository 加入 pointer，以及是否接受一項建議變更。Agent 端負責 route 選擇、review gate、telemetry 與 rule lifecycle 狀態。日常使用時，你不需要閱讀或修改這些內部狀態。

| 你需要理解 | Harness 內部處理 |
|---|---|
| 這項任務值得啟用嗎？ | 要載入哪些最小 route 檔案 |
| 如何安裝或移除？ | 條件式啟用 receipt 與 telemetry |
| 哪些證據支持效益？ | candidate／active／rollback lifecycle 記錄 |
| Agent 可以自行改動 governance 嗎？ | 不可以：高風險提案一定停在人工核准前 |

## 快速開始

### 1. 驗證 harness clone

```bash
git clone https://github.com/WenyuChiou/fable-method-harness
cd fable-method-harness
python scripts/setup_harness.py
```

Setup 可重複執行，並會跑 integration checks。若沒有通過，請停止；不要把未驗證的 clone 接入另一個專案。
它也會設定此 clone 的 Git hooks path；這個刻意的本地副作用請見 [SETUP.md](../SETUP.md)。

### 2. 產生 runtime wiring

```bash
python scripts/setup_harness.py --print-wiring
```

若你使用 Codex、Cursor、OpenCode 或其他採用 `AGENTS.md` 慣例的 agent，請把產生的 pointer 貼進目標 repository 的 `AGENTS.md`（或你的全域 agent instructions）。請保持產生的路徑不變：它指向這份 harness clone，且只在合格任務上載入。

若你使用 Hermes，請把此命令產生的 target-ready `HERMES.md` shim 複製到目標 repository；若 Hermes 會直接接收 harness-maintenance 工作，再加入產生的 router row。不要把完整 harness 貼進 Hermes 的固定 prompt。

### 3. 先從一項合格任務開始

使用一項真實的多步驟、completion-sensitive 或 governance-sensitive 任務。在新的 session 中，確認 agent 會先分類任務，再載入 routed bootstrap；對日常小任務，確認它保持 inactive。

## 立即撤回

在目標 repository root 建立空白 `.fable-harness-off` 檔案。下一個原本符合條件的任務會保持 inactive，不需修改全域設定：

```bash
touch .fable-harness-off
```

若使用 PowerShell，請改用 `New-Item .fable-harness-off -ItemType File`。

刪除 marker 即可恢復自動條件式啟用。從 `AGENTS.md` 移除 repository-level pointer，可中斷該 repository 的連結；若另有安裝 global pointer，也必須另外移除。對 Hermes 而言，移除安裝的 `HERMES.md` shim 即會恢復原生 context precedence。確切行為請看[條件式啟用契約](runtime_activation_contract.md)。

## 擴大前，先量測你自己的效益

公開結果只適用於本 repository 的 frozen tasks 與 runtime bindings，並不是你的專案也會得到相同結果的承諾。請先設計小型 paired control/treatment 評估，量測 correctness、total tokens、latency 與實際 corrective work。資料完整前，規則應維持 `candidate`；只有在沒有 harmful cases 且確實有益時才升為 `active`。

目前公開證據顯示：

| Surface | 已量測結果 | 不可推論 |
|---|---|---|
| Codex 長任務 | 本 repository 的 80-trial A/B 中，input tokens 減少 27%、tool calls 減少 59%、wall-clock 減少 34% | 一般 correctness 或 capability 提升 |
| Codex adaptive loop | 一個 frozen、六組配對實驗中，總 tokens 降低 14.17%、latency 降低 32.78% | 另一個專案或任務組合也有相同效益 |
| Hermes 條件式啟用 | 正確的 activation／rollback 行為與固定 context 減少 69.9% | API-token 或速度節省；adaptive-loop 結果為 UNSCORED |

在你的 repository 提出效率聲稱前，請閱讀[證據總帳](evidence.md)。失敗、無效果與成功結果都應公開記錄。

## 安全擴充專案專屬 harness

先使用可攜 pointer，並把專案專屬規則留在本地。只有當你能清楚說出一項 route 或 rule 的 trigger、預期效益、rollback 與 verification command 時，才加入它。對 hooks、permissions、settings、CI 或 governance 的修改，應建立 proposal 並要求人工核准，不能讓 loop 自我修改。

操作細節請繼續閱讀 [Codex integration](codex_harness_integration.md) 與 [adaptive-harness skill](../.claude/skills/adaptive-harness/SKILL.md)。
