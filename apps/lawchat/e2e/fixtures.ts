import { Page } from '@playwright/test'

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

export const MOCK_DOCUMENTS = {
  documents: [
    { law_name: '建築法', chunk_count: 120, ingested_at: '2024-01-01T00:00:00Z' },
    { law_name: '建築師法', chunk_count: 45, ingested_at: '2024-01-01T00:00:00Z' },
    { law_name: '都市計畫法', chunk_count: 80, ingested_at: '2024-01-01T00:00:00Z' },
  ],
  count: 3,
}

export const MOCK_SOURCES = [
  {
    law_name: '建築法',
    article_number: '第 28 條',
    chapter: '第二章',
    text: '建造執照之申請，應備左列文件：一、申請書。二、土地權利證明文件。',
    score: 0.12,
  },
  {
    law_name: '建築師法',
    article_number: '第 16 條',
    chapter: '第三章',
    text: '建築師受委託人之委託，辦理建築物及其實質環境之調查、測量、設計。',
    score: 0.25,
  },
]

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------

function buildSSE(events: object[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
}

export function sourcesSSE(): string {
  return buildSSE([
    { type: 'sources', sources: MOCK_SOURCES, retrieved_chunk_count: 2 },
    { type: 'token', text: '申請建造執照需要準備' },
    { type: 'token', text: '申請書及土地權利證明文件。' },
    { type: 'done', model: 'claude-sonnet-4-6', provider: 'anthropic' },
  ])
}

export function errorSSE(): string {
  return buildSSE([{ type: 'error', message: '查詢失敗，請稍後再試' }])
}

// ---------------------------------------------------------------------------
// Route mock helpers
// ---------------------------------------------------------------------------

export async function mockDocuments(page: Page, documents = MOCK_DOCUMENTS) {
  await page.route('/api/documents', (route) =>
    route.fulfill({ json: documents }),
  )
}

export async function mockQueryStream(page: Page, body = sourcesSSE()) {
  await page.route('/api/query-stream', (route) =>
    route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body,
    }),
  )
}

export async function mockQueryError(page: Page) {
  await page.route('/api/query-stream', (route) =>
    route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      body: errorSSE(),
    }),
  )
}

export async function mockApiDown(page: Page) {
  await page.route('/api/query-stream', (route) =>
    route.fulfill({ status: 500, body: JSON.stringify({ detail: 'Internal Server Error' }) }),
  )
}

// ---------------------------------------------------------------------------
// Setup: mock both endpoints and navigate to /
// ---------------------------------------------------------------------------

export async function setupPage(page: Page) {
  await mockDocuments(page)
  await mockQueryStream(page)
  await page.goto('/')
}
