import { useCallback, useEffect, useRef, useState } from 'react'
import { Document, fetchDocuments, QuerySource, streamQuery } from '../api'

// ---------------------------------------------------------------------------
// Preset questions
// ---------------------------------------------------------------------------

const PRESET_QUESTIONS = [
  '申請建造執照需要哪些文件？',
  '建築物竣工後的驗收程序為何？',
  '違反建築法規的罰則是什麼？',
  '建築師的執業範圍和責任有哪些？',
  '建築物的防火設備有哪些規定？',
  '都市計畫土地使用分區的限制？',
]

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Status = 'idle' | 'retrieving' | 'streaming' | 'done' | 'error'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LawQuery() {
  const [question, setQuestion] = useState('')
  const [selectedLaws, setSelectedLaws] = useState<string[]>([])
  const [laws, setLaws] = useState<Document[]>([])
  const [status, setStatus] = useState<Status>('idle')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState<QuerySource[]>([])
  const [error, setError] = useState('')
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [retrievedCount, setRetrievedCount] = useState(0)

  const answerRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const isLoading = status === 'retrieving' || status === 'streaming'

  // Load available laws on mount
  useEffect(() => {
    fetchDocuments()
      .then(({ documents }) => setLaws(documents))
      .catch(() => {})
  }, [])

  // Auto-scroll answer box as tokens arrive
  useEffect(() => {
    if (answerRef.current) {
      answerRef.current.scrollTop = answerRef.current.scrollHeight
    }
  }, [answer])

  const submit = useCallback(async (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || isLoading) return

    abortRef.current?.abort()
    abortRef.current = new AbortController()

    setAnswer('')
    setSources([])
    setError('')
    setSourcesOpen(false)
    setRetrievedCount(0)
    setStatus('retrieving')

    try {
      const gen = streamQuery({
        question: trimmed,
        law_names: selectedLaws.length > 0 ? selectedLaws : null,
        n_results: 5,
        llm_provider: 'anthropic',
        embedding_provider: 'voyage',
      })

      for await (const event of gen) {
        if (event.type === 'sources') {
          setSources(event.sources)
          setRetrievedCount(event.retrieved_chunk_count)
          setStatus('streaming')
        } else if (event.type === 'token') {
          setAnswer((prev) => prev + event.text)
        } else if (event.type === 'done') {
          setStatus('done')
          return
        } else if (event.type === 'error') {
          throw new Error(event.message)
        }
      }

      setStatus('done')
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : '查詢失敗')
      setStatus('error')
    }
  }, [isLoading, selectedLaws])

  const handlePreset = (q: string) => {
    setQuestion(q)
    submit(q)
  }

  const toggleLaw = (name: string) => {
    setSelectedLaws((prev) =>
      prev.includes(name) ? prev.filter((l) => l !== name) : [...prev, name],
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold">法規問答</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          輸入問題，AI 將根據已索引的法規條文回答
        </p>
      </div>

      {/* Law filter pills */}
      {laws.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
            限定查詢範圍（不選則查詢全部）
          </p>
          <div className="flex flex-wrap gap-2">
            {laws.map((doc) => {
              const active = selectedLaws.includes(doc.law_name)
              return (
                <button
                  key={doc.law_name}
                  onClick={() => toggleLaw(doc.law_name)}
                  className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-all ${
                    active
                      ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-600'
                  }`}
                >
                  {doc.law_name}
                  {active && <span className="ml-1 opacity-70">✓</span>}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Preset questions */}
      <div>
        <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
          常見問題
        </p>
        <div className="flex flex-wrap gap-2">
          {PRESET_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => handlePreset(q)}
              disabled={isLoading}
              className="text-xs px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-40 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit(question)
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="請輸入法規相關問題..."
          disabled={isLoading}
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors whitespace-nowrap"
        >
          {isLoading ? '查詢中...' : '送出'}
        </button>
      </form>

      {/* Answer panel */}
      {status !== 'idle' && (
        <div className="border border-gray-200 rounded-xl bg-white shadow-sm overflow-hidden">

          {/* Status bar */}
          <div
            className={`px-4 py-2.5 flex items-center gap-2 text-xs font-medium border-b ${
              status === 'error'
                ? 'bg-red-50 text-red-700 border-red-200'
                : 'bg-gray-50 text-gray-600 border-gray-100'
            }`}
          >
            {status === 'retrieving' && (
              <>
                <Spinner />
                <span>正在搜尋相關法條...</span>
              </>
            )}
            {status === 'streaming' && (
              <>
                <Spinner />
                <span>
                  正在生成回答
                  {retrievedCount > 0 && (
                    <span className="ml-1 text-gray-400">
                      （參考 {retrievedCount} 條法條）
                    </span>
                  )}
                </span>
              </>
            )}
            {status === 'done' && (
              <>
                <span className="text-green-600">✓</span>
                <span>
                  回答完成
                  {sources.length > 0 && (
                    <span className="ml-1 text-gray-400">
                      · 參考 {sources.length} 條法條
                    </span>
                  )}
                </span>
              </>
            )}
            {status === 'error' && (
              <>
                <span>✕</span>
                <span>發生錯誤</span>
              </>
            )}
          </div>

          {/* Answer text */}
          {(answer || status === 'error') && (
            <div
              ref={answerRef}
              className="px-5 py-4 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-[28rem] overflow-y-auto"
            >
              {status === 'error' ? (
                <span className="text-red-600">{error}</span>
              ) : (
                <>
                  {answer}
                  {status === 'streaming' && (
                    <span className="inline-block w-0.5 h-[1.1em] bg-blue-500 ml-px animate-pulse align-middle" />
                  )}
                </>
              )}
            </div>
          )}

          {/* Sources accordion — show only after done */}
          {sources.length > 0 && status === 'done' && (
            <div className="border-t border-gray-100">
              <button
                onClick={() => setSourcesOpen((v) => !v)}
                className="w-full px-5 py-3 text-left text-xs font-medium text-gray-500 hover:bg-gray-50 flex items-center justify-between transition-colors"
              >
                <span>引用法條（{sources.length} 筆）</span>
                <span className="text-gray-400">{sourcesOpen ? '▲' : '▼'}</span>
              </button>

              {sourcesOpen && (
                <div className="px-5 pb-4 space-y-2.5">
                  {sources.map((src, i) => (
                    <SourceCard key={i} source={src} rank={i + 1} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <svg
      className="animate-spin h-3 w-3 text-blue-500 flex-shrink-0"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

function SourceCard({ source, rank }: { source: QuerySource; rank: number }) {
  const [expanded, setExpanded] = useState(false)
  const similarity = ((1 - source.score) * 100).toFixed(1)

  return (
    <div className="bg-gray-50 rounded-lg border border-gray-100 overflow-hidden text-xs">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full px-3 py-2 text-left flex items-start justify-between gap-2 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-semibold flex items-center justify-center text-[10px]">
            {rank}
          </span>
          <span className="font-semibold text-gray-800 truncate">
            {source.law_name}
            {source.article_number && (
              <span className="ml-1 font-normal">{source.article_number}</span>
            )}
          </span>
          {source.chapter && (
            <span className="text-gray-400 truncate hidden sm:inline">
              {source.chapter}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 text-gray-400">
          <span>相似度 {similarity}%</span>
          <span>{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {expanded && (
        <div className="px-3 pb-3 pt-1 text-gray-600 leading-relaxed border-t border-gray-100">
          {source.text}
        </div>
      )}
    </div>
  )
}
