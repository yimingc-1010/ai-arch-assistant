import { test, expect } from '@playwright/test'
import {
  setupPage,
  mockDocuments,
  mockQueryStream,
  mockQueryError,
  mockApiDown,
  sourcesSSE,
} from './fixtures'

// Sidebar law buttons are scoped to <aside> to avoid matching preset card text
// (e.g. "→違反建築法規的罰則是什麼？" contains "建築法" via substring)
const sidebar = (page: ReturnType<typeof import('@playwright/test').test.info>) => page

// ---------------------------------------------------------------------------
// Page load
// ---------------------------------------------------------------------------

test.describe('Page load', () => {
  test('renders page without errors', async ({ page }) => {
    await setupPage(page)
    await expect(page).toHaveTitle(/建築法規/)
  })

  test('shows empty state on first load', async ({ page }) => {
    await setupPage(page)
    await expect(page.getByRole('heading', { name: '建築法規 AI 助手' })).toBeVisible()
    await expect(page.getByText('輸入問題，即時查詢相關法條與解釋')).toBeVisible()
  })

  test('shows all 6 preset cards', async ({ page }) => {
    await setupPage(page)
    const cards = page.locator('button:has-text("→")')
    await expect(cards).toHaveCount(6)
  })
})

// ---------------------------------------------------------------------------
// Sidebar — law list
// ---------------------------------------------------------------------------

test.describe('Sidebar', () => {
  // Force desktop viewport — sidebar is always visible (not off-screen).
  // Mobile-specific sidebar behaviour is covered in "Mobile hamburger" describe.
  test.use({ viewport: { width: 1280, height: 900 } })

  test('loads law list from /api/documents', async ({ page }) => {
    await setupPage(page)
    // Scope to <aside> to avoid ambiguity with preset card text
    await expect(page.locator('aside').getByRole('button', { name: '建築法', exact: true })).toBeVisible()
    await expect(page.locator('aside').getByRole('button', { name: '建築師法', exact: true })).toBeVisible()
    await expect(page.locator('aside').getByRole('button', { name: '都市計畫法', exact: true })).toBeVisible()
  })

  test('全部法規 is selected by default', async ({ page }) => {
    await setupPage(page)
    const allBtn = page.locator('aside').getByRole('button', { name: '全部法規', exact: true })
    await expect(allBtn).toHaveClass(/bg-\[#1A1A1A\]/)
  })

  test('selecting a law highlights it and updates header label', async ({ page }) => {
    await setupPage(page)
    await page.locator('aside').getByRole('button', { name: '建築法', exact: true }).click()
    await expect(page.locator('aside').getByRole('button', { name: '建築法', exact: true })).toHaveClass(/bg-\[#EBF5FF\]/)
    // Header scope label shows selected law name (exact match excludes "建築法規 AI 助手")
    await expect(page.locator('header').getByText('建築法', { exact: true })).toBeVisible()
  })

  test('selecting multiple laws shows count in header', async ({ page }) => {
    await setupPage(page)
    await page.locator('aside').getByRole('button', { name: '建築法', exact: true }).click()
    await page.locator('aside').getByRole('button', { name: '建築師法', exact: true }).click()
    await expect(page.getByText(/等 2 部法規/)).toBeVisible()
  })

  test('deselecting returns to 全部法規', async ({ page }) => {
    await setupPage(page)
    await page.locator('aside').getByRole('button', { name: '建築法', exact: true }).click()
    await page.locator('aside').getByRole('button', { name: '建築法', exact: true }).click()
    await expect(page.locator('aside').getByRole('button', { name: '全部法規', exact: true })).toHaveClass(/bg-\[#1A1A1A\]/)
  })

  test('clicking 清除 resets selection', async ({ page }) => {
    await setupPage(page)
    await page.locator('aside').getByRole('button', { name: '建築法', exact: true }).click()
    // 清除 button is in the header, only visible when a law is selected
    await page.locator('header').getByRole('button', { name: '清除' }).click()
    await expect(page.locator('aside').getByRole('button', { name: '全部法規', exact: true })).toHaveClass(/bg-\[#1A1A1A\]/)
  })

  test('search filters law list', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('搜尋法規...').fill('建築師')
    await expect(page.locator('aside').getByRole('button', { name: '建築師法', exact: true })).toBeVisible()
    await expect(page.locator('aside').getByRole('button', { name: '都市計畫法', exact: true })).not.toBeVisible()
  })

  test('search with no match shows empty hint', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('搜尋法規...').fill('不存在的法規XYZ')
    await expect(page.getByText('找不到相符法規')).toBeVisible()
  })

  test('shows only 全部法規 when no documents loaded', async ({ page }) => {
    await mockDocuments(page, { documents: [], count: 0 })
    await mockQueryStream(page)
    await page.goto('/')
    await expect(page.locator('aside').getByRole('button', { name: '全部法規', exact: true })).toBeVisible()
    // No specific law buttons should exist in sidebar
    await expect(page.locator('aside').getByRole('button', { name: '建築法', exact: true })).toHaveCount(0)
  })
})

// ---------------------------------------------------------------------------
// Header controls
// ---------------------------------------------------------------------------

test.describe('Header', () => {
  test('format toggle defaults to 問答', async ({ page }) => {
    await setupPage(page)
    await expect(page.getByRole('button', { name: '問答', exact: true })).toHaveClass(/bg-white/)
  })

  test('switching to 清單 activates that button', async ({ page }) => {
    await setupPage(page)
    await page.getByRole('button', { name: '清單', exact: true }).click()
    await expect(page.getByRole('button', { name: '清單', exact: true })).toHaveClass(/bg-white/)
    await expect(page.getByRole('button', { name: '問答', exact: true })).not.toHaveClass(/bg-white/)
  })

  test('city selector defaults to 全部縣市', async ({ page }) => {
    await setupPage(page)
    await expect(page.getByRole('combobox')).toHaveValue('')
  })

  test('selecting a city changes combobox value', async ({ page }) => {
    await setupPage(page)
    await page.getByRole('combobox').selectOption('台北市')
    await expect(page.getByRole('combobox')).toHaveValue('台北市')
  })
})

// ---------------------------------------------------------------------------
// Mobile hamburger
// ---------------------------------------------------------------------------

test.describe('Mobile hamburger', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('sidebar hidden on mobile by default', async ({ page }) => {
    await setupPage(page)
    await expect(page.locator('aside')).toHaveClass(/-translate-x-full/)
  })

  test('hamburger button is visible on mobile', async ({ page }) => {
    await setupPage(page)
    await expect(page.getByRole('button', { name: '開啟選單' })).toBeVisible()
  })

  test('hamburger opens sidebar', async ({ page }) => {
    await setupPage(page)
    await page.getByRole('button', { name: '開啟選單' }).click()
    // Opened: -translate-x-full is removed
    await expect(page.locator('aside')).not.toHaveClass(/-translate-x-full/)
  })

  test('overlay closes sidebar on tap', async ({ page }) => {
    await setupPage(page)
    await page.getByRole('button', { name: '開啟選單' }).click()
    await page.locator('.fixed.inset-0').click()
    await expect(page.locator('aside')).toHaveClass(/-translate-x-full/)
  })

  test('sidebar closes after law selection', async ({ page }) => {
    await setupPage(page)
    await page.getByRole('button', { name: '開啟選單' }).click()
    await page.locator('aside').getByRole('button', { name: '建築法', exact: true }).click()
    await expect(page.locator('aside')).toHaveClass(/-translate-x-full/)
  })
})

// ---------------------------------------------------------------------------
// Input bar
// ---------------------------------------------------------------------------

test.describe('Input bar', () => {
  test('send button is disabled when input is empty', async ({ page }) => {
    await setupPage(page)
    await expect(page.getByRole('button', { name: '送出' })).toBeDisabled()
  })

  test('send button enables when input has text', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('測試問題')
    await expect(page.getByRole('button', { name: '送出' })).toBeEnabled()
  })

  test('Enter key submits question', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('建造執照文件')
    await page.keyboard.press('Enter')
    // User message bubble appears
    await expect(page.locator('.flex.justify-end').getByText('建造執照文件')).toBeVisible()
  })

  test('clicking 送出 submits question', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('建造執照文件')
    await page.getByRole('button', { name: '送出' }).click()
    await expect(page.locator('.flex.justify-end').getByText('建造執照文件')).toBeVisible()
  })

  test('input clears after submit', async ({ page }) => {
    await setupPage(page)
    const input = page.getByPlaceholder('請輸入法規相關問題...')
    await input.fill('建造執照文件')
    await page.keyboard.press('Enter')
    await expect(input).toHaveValue('')
  })

  test('preset chips appear after first message', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('申請建造執照需要準備')).toBeVisible({ timeout: 10_000 })
    // Chips are in the input bar area (rounded-full style)
    await expect(page.locator('button.rounded-full').first()).toBeVisible()
  })

  test('clicking a preset chip submits that question', async ({ page }) => {
    await setupPage(page)
    await page.locator('button:has-text("→")').first().click()
    await expect(page.getByText('申請建造執照需要準備')).toBeVisible({ timeout: 10_000 })
    await page.locator('button.rounded-full').filter({ hasText: '建築物竣工後的驗收程序為何？' }).click()
    await expect(page.locator('.flex.justify-end').getByText('建築物竣工後的驗收程序為何？')).toBeVisible()
  })
})

// ---------------------------------------------------------------------------
// Chat flow
// ---------------------------------------------------------------------------

test.describe('Chat flow', () => {
  test('clicking preset card sends that question', async ({ page }) => {
    await setupPage(page)
    await page.locator('button:has-text("→")').first().click()
    // User message bubble (black, right-aligned)
    await expect(page.locator('.flex.justify-end').getByText('申請建造執照需要哪些文件？')).toBeVisible()
  })

  test('shows retrieving spinner then response', async ({ page }) => {
    await mockDocuments(page)
    await page.route('/api/query-stream', async (route) => {
      await new Promise((r) => setTimeout(r, 300))
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
        body: sourcesSSE(),
      })
    })
    await page.goto('/')
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('正在搜尋相關法條...')).toBeVisible()
    await expect(page.getByText('申請建造執照需要準備')).toBeVisible({ timeout: 10_000 })
  })

  test('user message appears in right-aligned bubble', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.locator('.flex.justify-end').getByText('問題')).toBeVisible()
  })

  test('bot response card appears with sources', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('申請建造執照需要準備')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('引用 2 條法條')).toBeVisible()
  })

  test('sources accordion is hidden by default', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('引用 2 條法條')).toBeVisible({ timeout: 10_000 })
    // The source text content is hidden (only visible after expanding)
    await expect(page.getByText('建造執照之申請，應備左列文件')).not.toBeVisible()
  })

  test('clicking sources accordion expands it', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('引用 2 條法條')).toBeVisible({ timeout: 10_000 })
    await page.getByText('引用 2 條法條').click()
    await expect(page.getByText('第 28 條')).toBeVisible()
    await expect(page.getByText('第 16 條')).toBeVisible()
  })

  test('source card expands to show text', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('引用 2 條法條')).toBeVisible({ timeout: 10_000 })
    await page.getByText('引用 2 條法條').click()
    await page.getByText('第 28 條').click()
    await expect(page.getByText('建造執照之申請，應備左列文件')).toBeVisible()
  })

  test('multiple messages accumulate in chat', async ({ page }) => {
    await setupPage(page)
    const input = page.getByPlaceholder('請輸入法規相關問題...')
    await input.fill('第一個問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('申請建造執照需要準備')).toBeVisible({ timeout: 10_000 })
    await input.fill('第二個問題')
    await page.keyboard.press('Enter')
    await expect(page.locator('.flex.justify-end').getByText('第一個問題')).toBeVisible()
    await expect(page.locator('.flex.justify-end').getByText('第二個問題')).toBeVisible()
  })

  test('empty state disappears after first message', async ({ page }) => {
    await setupPage(page)
    await expect(page.locator('button:has-text("→")')).toHaveCount(6)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.locator('button:has-text("→")')).toHaveCount(0)
  })
})

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

test.describe('Error handling', () => {
  test('SSE error event shows error message in chat', async ({ page }) => {
    await mockDocuments(page)
    await mockQueryError(page)
    await page.goto('/')
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText('查詢失敗，請稍後再試')).toBeVisible({ timeout: 10_000 })
  })

  test('HTTP 500 shows error in chat', async ({ page }) => {
    await mockDocuments(page)
    await mockApiDown(page)
    await page.goto('/')
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.keyboard.press('Enter')
    await expect(page.getByText(/查詢失敗|Internal Server Error/)).toBeVisible({ timeout: 10_000 })
  })

  test('documents API failure shows empty sidebar gracefully', async ({ page }) => {
    await page.route('/api/documents', (route) => route.fulfill({ status: 500 }))
    await mockQueryStream(page)
    await page.goto('/')
    await expect(page.locator('aside').getByRole('button', { name: '全部法規', exact: true })).toBeVisible()
    await expect(page.locator('aside').getByRole('button', { name: '建築法', exact: true })).toHaveCount(0)
  })
})

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

test.describe('Accessibility', () => {
  test('hamburger button is accessible on mobile', async ({ page }) => {
    // The hamburger is md:hidden — must test at mobile viewport
    await page.setViewportSize({ width: 375, height: 812 })
    await setupPage(page)
    await expect(page.getByRole('button', { name: '開啟選單' })).toBeVisible()
  })

  test('input has placeholder text', async ({ page }) => {
    await setupPage(page)
    await expect(page.getByPlaceholder('請輸入法規相關問題...')).toBeVisible()
  })

  test('send button is keyboard accessible', async ({ page }) => {
    await setupPage(page)
    await page.getByPlaceholder('請輸入法規相關問題...').fill('問題')
    await page.getByRole('button', { name: '送出' }).focus()
    await page.keyboard.press('Space')
    await expect(page.locator('.flex.justify-end').getByText('問題')).toBeVisible()
  })
})
