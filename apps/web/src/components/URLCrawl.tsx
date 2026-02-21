import React, { useState } from 'react'
import { ingestCrawlResult, startCrawl, TaskData, useTaskStream } from '../api'

interface Props {
  onTaskCreated: (taskId: string, label: string) => void
}

export default function URLCrawl({ onTaskCreated }: Props) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [crawlTaskId, setCrawlTaskId] = useState<string | null>(null)
  const [crawlTask, setCrawlTask] = useState<TaskData | null>(null)

  // Ingest dialog state
  const [showIngest, setShowIngest] = useState(false)
  const [ingestLawName, setIngestLawName] = useState('')
  const [ingestProvider, setIngestProvider] = useState('voyage')
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestError, setIngestError] = useState('')

  // Stream updates for the crawl task
  useTaskStream(crawlTaskId, (task) => {
    setCrawlTask(task)
  })

  const handleCrawl = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) { setError('請輸入 URL'); return }
    setLoading(true)
    setError('')
    setCrawlTask(null)
    setShowIngest(false)
    try {
      const { task_id } = await startCrawl(url.trim())
      setCrawlTaskId(task_id)
      onTaskCreated(task_id, `爬取 ${url.trim()}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '爬取失敗')
    } finally {
      setLoading(false)
    }
  }

  const handleIngest = async () => {
    if (!crawlTaskId || !ingestLawName.trim()) {
      setIngestError('請填入法規名稱')
      return
    }
    setIngestLoading(true)
    setIngestError('')
    try {
      const { task_id } = await ingestCrawlResult(crawlTaskId, ingestLawName.trim(), ingestProvider)
      onTaskCreated(task_id, `匯入 ${ingestLawName}`)
      setShowIngest(false)
    } catch (err: unknown) {
      setIngestError(err instanceof Error ? err.message : '匯入失敗')
    } finally {
      setIngestLoading(false)
    }
  }

  const result = crawlTask?.result as Record<string, unknown> | null

  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-lg font-semibold mb-4">URL 爬蟲</h2>
      <form onSubmit={handleCrawl} className="flex gap-2 mb-4">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=..."
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors whitespace-nowrap"
        >
          {loading ? '爬取中...' : '開始爬取'}
        </button>
      </form>
      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {/* Crawl result preview */}
      {crawlTask && (
        <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">爬取狀態</span>
            <StatusBadge status={crawlTask.status} />
          </div>
          <p className="text-sm text-gray-600">{crawlTask.message}</p>

          {crawlTask.status === 'done' && result && (
            <>
              <div className="text-sm space-y-1">
                <div>
                  <span className="text-gray-500">策略：</span>
                  <span className="font-medium">{String(result.strategy_used ?? '')}</span>
                </div>
                {result.article_count != null && (
                  <div>
                    <span className="text-gray-500">文章數：</span>
                    <span className="font-medium">{String(result.article_count)}</span>
                  </div>
                )}
                {Boolean(result.title) && (
                  <div>
                    <span className="text-gray-500">標題：</span>
                    <span className="font-medium">{String(result.title)}</span>
                  </div>
                )}
              </div>

              <button
                onClick={() => setShowIngest(true)}
                className="w-full mt-2 bg-green-600 text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-green-700 transition-colors"
              >
                存入向量庫
              </button>
            </>
          )}

          {crawlTask.status === 'error' && (
            <p className="text-red-500 text-sm">{crawlTask.error}</p>
          )}
        </div>
      )}

      {/* Ingest dialog */}
      {showIngest && (
        <div className="mt-4 border border-green-200 rounded-lg p-4 bg-green-50 space-y-3">
          <h3 className="text-sm font-semibold text-green-800">存入向量庫</h3>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">法規名稱</label>
            <input
              type="text"
              value={ingestLawName}
              onChange={(e) => setIngestLawName(e.target.value)}
              placeholder="例：建築法"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Embedding Provider</label>
            <select
              value={ingestProvider}
              onChange={(e) => setIngestProvider(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none"
            >
              <option value="voyage">Voyage AI</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          {ingestError && <p className="text-red-500 text-xs">{ingestError}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleIngest}
              disabled={ingestLoading}
              className="flex-1 bg-green-600 text-white py-2 px-3 rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {ingestLoading ? '匯入中...' : '確認匯入'}
            </button>
            <button
              onClick={() => setShowIngest(false)}
              className="px-3 py-2 text-sm text-gray-600 hover:text-gray-800"
            >
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-blue-100 text-blue-700',
    done: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  }
  const labels: Record<string, string> = {
    pending: '排隊中',
    running: '執行中',
    done: '完成',
    error: '失敗',
  }
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${map[status] ?? ''}`}>
      {labels[status] ?? status}
    </span>
  )
}
