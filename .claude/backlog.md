[
  {
    "id": 1,
    "title": "新增意圖分類流程以加速 RAG 搜尋",
    "status": "pending",
    "description": "在 RAG query 流程前加入意圖判斷步驟，透過 LLM 或規則分類使用者問題的法規意圖，根據分類結果縮小 ChromaDB 搜尋範圍，降低跨 collection 全量搜尋的延遲。涉及：packages/rag/src/lawrag/pipeline/、packages/api/src/autocrawler_api/routes/rag.py"
  },
  {
    "id": 2,
    "title": "前台顯示目前處理流程狀態",
    "status": "pending",
    "description": "在 LawChat 前端介面即時顯示後端處理進度（分析意圖 / 搜尋法條 / 生成回答），透過 SSE 或 streaming 附帶 step 事件推送狀態。涉及：lawchat 前台元件、FastAPI /rag/query 端點"
  },
  {
    "id": 3,
    "title": "新增歷史問題存取 DB",
    "status": "pending",
    "description": "建立歷史對話持久化機制（SQLite 或 PostgreSQL），儲存問題、回答、時間戳記、法規意圖分類。新增 GET /rag/history 端點，前台支援查看歷史紀錄並重新查詢。涉及：packages/api/、可能新增 packages/db/"
  }
]
