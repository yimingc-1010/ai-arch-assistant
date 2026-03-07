'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Source {
  law_name: string
  article_number: string
  chapter: string
  text: string
  score: number
}

interface LawDocument {
  law_name: string
  chunk_count: number
  ingested_at: string
}

type OutputFormat = 'prose' | 'checklist'
type MsgStatus = 'retrieving' | 'streaming' | 'done' | 'error'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  status?: MsgStatus
  sources?: Source[]
  retrievedCount?: number
}

type StreamEvent =
  | { type: 'sources'; sources: Source[]; retrieved_chunk_count: number }
  | { type: 'token'; text: string }
  | { type: 'done'; model: string; provider: string }
  | { type: 'error'; message: string }

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CITIES = [
  '台北市', '新北市', '桃園市', '台中市',
  '台南市', '高雄市', '基隆市', '新竹市', '嘉義市',
]

const PRESETS = [
  '申請建造執照需要哪些文件？',
  '建築物竣工後的驗收程序為何？',
  '違反建築法規的罰則是什麼？',
  '建築師的執業範圍有哪些？',
  '建築物防火設備的規定？',
  '土地使用分區的限制？',
]

// ---------------------------------------------------------------------------
// Streaming helper
// ---------------------------------------------------------------------------

async function* fetchStream(
  question: string,
  lawNames: string[] | null,
  outputFormat: OutputFormat,
  jurisdictions: string[] | null,
): AsyncGenerator<StreamEvent> {
  const res = await fetch('/api/query-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      law_names: lawNames,
      n_results: 5,
      llm_provider: 'anthropic',
      embedding_provider: 'voyage',
      output_format: outputFormat,
      jurisdictions: jurisdictions,
    }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((err as { detail?: string }).detail ?? 'Query failed')
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        yield JSON.parse(line.slice(6)) as StreamEvent
      } catch {
        // ignore malformed line
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function LawChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [laws, setLaws] = useState<LawDocument[]>([])
  const [selectedLaws, setSelectedLaws] = useState<string[]>([])
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('prose')
  const [selectedCity, setSelectedCity] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Load indexed laws
  useEffect(() => {
    fetch('/api/documents')
      .then((r) => r.json())
      .then((d: { documents: LawDocument[] }) => setLaws(d.documents ?? []))
      .catch(() => {})
  }, [])

  // Scroll to bottom whenever messages update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const patchLast = useCallback((fn: (m: Message) => Message) => {
    setMessages((prev) => {
      const next = [...prev]
      const i = next.length - 1
      if (i >= 0 && next[i].role === 'assistant') next[i] = fn(next[i])
      return next
    })
  }, [])

  const submit = useCallback(
    async (q: string) => {
      const trimmed = q.trim()
      if (!trimmed || isLoading) return

      setInput('')
      setIsLoading(true)

      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', content: trimmed },
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '',
          status: 'retrieving',
          sources: [],
        },
      ])

      const jurisdictions = selectedCity
        ? [selectedCity, '全國']
        : null

      try {
        for await (const ev of fetchStream(
          trimmed,
          selectedLaws.length > 0 ? selectedLaws : null,
          outputFormat,
          jurisdictions,
        )) {
          if (ev.type === 'sources') {
            patchLast((m) => ({
              ...m,
              status: 'streaming',
              sources: ev.sources,
              retrievedCount: ev.retrieved_chunk_count,
            }))
          } else if (ev.type === 'token') {
            patchLast((m) => ({ ...m, content: m.content + ev.text }))
          } else if (ev.type === 'done') {
            patchLast((m) => ({ ...m, status: 'done' }))
            return
          } else if (ev.type === 'error') {
            throw new Error(ev.message)
          }
        }
        patchLast((m) => ({ ...m, status: 'done' }))
      } catch (err: unknown) {
        patchLast((m) => ({
          ...m,
          content: err instanceof Error ? err.message : '查詢失敗',
          status: 'error',
        }))
      } finally {
        setIsLoading(false)
        inputRef.current?.focus()
      }
    },
    [isLoading, selectedLaws, outputFormat, selectedCity, patchLast],
  )

  const toggleLaw = (name: string) =>
    setSelectedLaws((prev) =>
      prev.includes(name) ? prev.filter((l) => l !== name) : [...prev, name],
    )

  const hasMessages = messages.length > 0

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      {/* ── Header ── */}
      <header className="bg-white border-b border-slate-200 shadow-sm flex-shrink-0">
        <div className="max-w-3xl mx-auto px-4 py-4 space-y-3">
          {/* Title row */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-lg select-none">
              ⚖
            </div>
            <div>
              <h1 className="font-bold text-slate-900 leading-tight">法規問答</h1>
              <p className="text-xs text-slate-400">基於 RAG 的法律條文智慧問答系統</p>
            </div>
          </div>

          {/* Law filter pills */}
          {laws.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-slate-400">查詢範圍：</span>
              {laws.map((doc) => (
                <button
                  key={doc.law_name}
                  onClick={() => toggleLaw(doc.law_name)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-all ${
                    selectedLaws.includes(doc.law_name)
                      ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                      : 'bg-white text-slate-600 border-slate-300 hover:border-blue-400'
                  }`}
                >
                  {doc.law_name}
                  {selectedLaws.includes(doc.law_name) && ' ✓'}
                </button>
              ))}
              {selectedLaws.length === 0 && (
                <span className="text-xs text-slate-400">全部法規</span>
              )}
            </div>
          )}

          {/* Toolbar: output format toggle + city selector */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Output format toggle */}
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
              <button
                onClick={() => setOutputFormat('prose')}
                className={`text-xs px-3 py-1 rounded-md transition-all ${
                  outputFormat === 'prose'
                    ? 'bg-white text-slate-800 shadow-sm font-medium'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                問答模式
              </button>
              <button
                onClick={() => setOutputFormat('checklist')}
                className={`text-xs px-3 py-1 rounded-md transition-all ${
                  outputFormat === 'checklist'
                    ? 'bg-white text-slate-800 shadow-sm font-medium'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                清單模式
              </button>
            </div>

            {/* City/jurisdiction selector */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400">縣市：</span>
              <select
                value={selectedCity}
                onChange={(e) => setSelectedCity(e.target.value)}
                className="text-xs border border-slate-300 rounded-lg px-2 py-1 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">全部</option>
                {CITIES.map((city) => (
                  <option key={city} value={city}>{city}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </header>

      {/* ── Messages ── */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
          {/* Welcome + presets (shown when no messages) */}
          {!hasMessages && (
            <div className="space-y-6 mt-4">
              <p className="text-center text-slate-400 text-sm">
                請輸入問題，或選擇下方常見問題開始
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {PRESETS.map((q) => (
                  <button
                    key={q}
                    onClick={() => submit(q)}
                    disabled={isLoading}
                    className="text-sm text-left px-4 py-3 bg-white rounded-xl border border-slate-200 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 transition-all disabled:opacity-50 shadow-sm"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Chat messages */}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          <div ref={bottomRef} />
        </div>
      </main>

      {/* ── Input bar ── */}
      <div className="bg-white border-t border-slate-200 flex-shrink-0 px-4 py-3 space-y-2">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit(input)
              }
            }}
            placeholder="請輸入法規相關問題..."
            disabled={isLoading}
            className="flex-1 border border-slate-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-50 transition"
          />
          <button
            onClick={() => submit(input)}
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors whitespace-nowrap"
          >
            {isLoading ? '⋯' : '送出'}
          </button>
        </div>

        {/* Preset chips (compact, shown after first message) */}
        {hasMessages && (
          <div className="max-w-3xl mx-auto flex gap-1.5 overflow-x-auto scrollbar-none pb-0.5">
            {PRESETS.map((q) => (
              <button
                key={q}
                onClick={() => submit(q)}
                disabled={isLoading}
                className="flex-shrink-0 text-xs px-2.5 py-1 bg-slate-100 text-slate-500 rounded-full hover:bg-blue-50 hover:text-blue-600 disabled:opacity-40 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MessageBubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: Message }) {
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const isUser = message.role === 'user'
  const isDone = message.status === 'done'
  const isStreaming = message.status === 'streaming'
  const isRetrieving = message.status === 'retrieving'
  const isError = message.status === 'error'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-sm">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[92%] bg-white rounded-2xl rounded-tl-sm border border-slate-200 shadow-sm overflow-hidden">
        {/* Status bar */}
        {(isRetrieving || (isStreaming && !message.content)) && (
          <div className="flex items-center gap-2 px-5 py-3 text-xs text-slate-400">
            <Spinner />
            <span>
              {isRetrieving
                ? '正在搜尋相關法條...'
                : `正在生成回答...（已參考 ${message.retrievedCount ?? 0} 條法條）`}
            </span>
          </div>
        )}

        {/* Answer body */}
        {(message.content || isError) && (
          <div className="px-5 py-4">
            {isError ? (
              <p className="text-sm text-red-500">{message.content}</p>
            ) : isDone ? (
              /* ── Markdown rendered after streaming completes ── */
              <div className="prose prose-sm prose-slate max-w-none
                prose-headings:font-semibold prose-headings:text-slate-800
                prose-p:text-slate-700 prose-p:leading-relaxed
                prose-li:text-slate-700
                prose-strong:text-slate-900
                prose-code:bg-slate-100 prose-code:px-1 prose-code:rounded prose-code:text-sm prose-code:text-slate-800 prose-code:before:content-none prose-code:after:content-none
                prose-pre:bg-slate-900 prose-pre:text-slate-100
                prose-blockquote:border-blue-400 prose-blockquote:text-slate-500
                prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : (
              /* ── Plain text while streaming (fast, no layout shift) ── */
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                {message.content}
                {isStreaming && (
                  <span className="inline-block w-0.5 h-[1.1em] bg-blue-500 ml-px animate-pulse align-middle" />
                )}
              </p>
            )}
          </div>
        )}

        {/* Sources accordion */}
        {isDone && message.sources && message.sources.length > 0 && (
          <div className="border-t border-slate-100">
            <button
              onClick={() => setSourcesOpen((v) => !v)}
              className="w-full px-5 py-2.5 flex items-center justify-between text-xs text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <span>引用 {message.sources.length} 條法條</span>
              <span>{sourcesOpen ? '▲' : '▼'}</span>
            </button>
            {sourcesOpen && (
              <div className="px-5 pb-4 space-y-2">
                {message.sources.map((src, i) => (
                  <SourceCard key={i} source={src} rank={i + 1} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SourceCard
// ---------------------------------------------------------------------------

function SourceCard({ source, rank }: { source: Source; rank: number }) {
  const [open, setOpen] = useState(false)
  const similarity = ((1 - source.score) * 100).toFixed(1)

  return (
    <div className="border border-slate-100 rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-3 py-2 flex items-center gap-2 text-left hover:bg-slate-50 transition-colors"
      >
        <span className="w-4 h-4 rounded-full bg-blue-100 text-blue-600 text-[10px] font-bold flex items-center justify-center flex-shrink-0">
          {rank}
        </span>
        <span className="font-medium text-slate-700 flex-1 truncate">
          {source.law_name}
          {source.article_number && (
            <span className="font-normal text-slate-500 ml-1">{source.article_number}</span>
          )}
          {source.chapter && (
            <span className="font-normal text-slate-400 ml-1 hidden sm:inline">
              {source.chapter}
            </span>
          )}
        </span>
        <span className="text-slate-300 flex-shrink-0">
          {similarity}%{' '}
          <span className="text-[10px]">{open ? '▲' : '▼'}</span>
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 text-slate-500 leading-relaxed border-t border-slate-50 text-[12px]">
          {source.text}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <svg
      className="animate-spin h-3 w-3 text-blue-400 flex-shrink-0"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}
