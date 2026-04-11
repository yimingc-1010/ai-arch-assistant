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
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [lawSearch, setLawSearch] = useState('')

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch('/api/documents')
      .then((r) => r.json())
      .then((d: { documents: LawDocument[] }) => setLaws(d.documents ?? []))
      .catch(() => {})
  }, [])

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
      setSidebarOpen(false)

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

      const jurisdictions = selectedCity ? [selectedCity, '全國'] : null

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

  const toggleLaw = (name: string) => {
    setSelectedLaws((prev) =>
      prev.includes(name) ? prev.filter((l) => l !== name) : [...prev, name],
    )
    setSidebarOpen(false)
  }

  const filteredLaws = laws.filter(
    (doc) => !lawSearch || doc.law_name.includes(lawSearch),
  )

  const hasMessages = messages.length > 0

  return (
    <div className="flex h-screen bg-[#F7F8FA] overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-30 w-64 bg-white border-r border-[#E8E8E8]
          flex flex-col transition-transform duration-200 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Sidebar logo */}
        <div className="px-4 pt-5 pb-4 border-b border-[#F0F0F0]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#1A1A1A] flex items-center justify-center text-white text-sm select-none flex-shrink-0">
              ⚖
            </div>
            <div className="min-w-0">
              <div className="text-sm font-bold text-[#1A1A1A] leading-tight">建築法規 AI 助手</div>
              <div className="text-[10px] text-[#888888] leading-tight">法律條文智慧檢索系統</div>
            </div>
          </div>
        </div>

        {/* Law search */}
        <div className="px-3 py-3">
          <div className="relative">
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#888888]"
              width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5"
            >
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              type="text"
              value={lawSearch}
              onChange={(e) => setLawSearch(e.target.value)}
              placeholder="搜尋法規..."
              className="w-full pl-7 pr-3 py-1.5 text-xs bg-[#F7F8FA] border border-[#E8E8E8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A9FD8] text-[#1A1A1A] placeholder:text-[#AAAAAA]"
            />
          </div>
        </div>

        {/* Law list */}
        <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-0.5">
          <div className="text-[10px] font-medium text-[#AAAAAA] uppercase tracking-wider px-2 pb-2">
            查詢範圍
          </div>

          <button
            onClick={() => setSelectedLaws([])}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
              selectedLaws.length === 0
                ? 'bg-[#1A1A1A] text-white font-medium'
                : 'text-[#333333] hover:bg-[#F7F8FA]'
            }`}
          >
            全部法規
          </button>

          {filteredLaws.map((doc) => (
            <button
              key={doc.law_name}
              onClick={() => toggleLaw(doc.law_name)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-center justify-between gap-1 ${
                selectedLaws.includes(doc.law_name)
                  ? 'bg-[#EBF5FF] text-[#4A9FD8] font-medium'
                  : 'text-[#333333] hover:bg-[#F7F8FA]'
              }`}
            >
              <span className="truncate">{doc.law_name}</span>
              {selectedLaws.includes(doc.law_name) && (
                <svg className="flex-shrink-0 text-[#4A9FD8]" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M20 6 9 17l-5-5"/>
                </svg>
              )}
            </button>
          ))}

          {filteredLaws.length === 0 && lawSearch && (
            <p className="text-xs text-[#AAAAAA] px-3 py-2">找不到相符法規</p>
          )}
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* ── Header ── */}
        <header className="bg-white border-b border-[#E8E8E8] flex items-center px-4 py-3 gap-3 flex-shrink-0">
          {/* Mobile hamburger */}
          <button
            className="md:hidden p-1.5 -ml-1.5 rounded-lg text-[#1A1A1A] hover:bg-[#F7F8FA] transition-colors"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="開啟選單"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6"/>
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>

          {/* Mobile: logo + title */}
          <div className="md:hidden flex items-center gap-2 flex-1 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-[#1A1A1A] flex items-center justify-center text-white text-xs select-none flex-shrink-0">
              ⚖
            </div>
            <span className="text-sm font-bold text-[#1A1A1A] truncate">建築法規 AI 助手</span>
          </div>

          {/* Desktop: current scope label */}
          <div className="hidden md:flex flex-1 min-w-0 items-center gap-2">
            <span className="text-sm font-medium text-[#1A1A1A] truncate">
              {selectedLaws.length === 0
                ? '全部法規'
                : selectedLaws.length === 1
                ? selectedLaws[0]
                : `${selectedLaws[0]} 等 ${selectedLaws.length} 部法規`}
            </span>
            {selectedLaws.length > 0 && (
              <button
                onClick={() => setSelectedLaws([])}
                className="text-xs text-[#AAAAAA] hover:text-[#666666] transition-colors"
              >
                清除
              </button>
            )}
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Reset chat */}
            {hasMessages && (
              <button
                onClick={() => setMessages([])}
                disabled={isLoading}
                title="清除對話"
                className="p-1.5 rounded-lg text-[#888888] hover:text-[#1A1A1A] hover:bg-[#F7F8FA] transition-colors disabled:opacity-40"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                  <path d="M3 3v5h5"/>
                </svg>
              </button>
            )}
            {/* Format toggle */}
            <div className="flex items-center bg-[#F7F8FA] rounded-lg p-0.5 border border-[#E8E8E8]">
              <button
                onClick={() => setOutputFormat('prose')}
                className={`text-xs px-2.5 py-1 rounded-md transition-all ${
                  outputFormat === 'prose'
                    ? 'bg-white text-[#1A1A1A] shadow-sm font-medium'
                    : 'text-[#666666] hover:text-[#1A1A1A]'
                }`}
              >
                問答
              </button>
              <button
                onClick={() => setOutputFormat('checklist')}
                className={`text-xs px-2.5 py-1 rounded-md transition-all ${
                  outputFormat === 'checklist'
                    ? 'bg-white text-[#1A1A1A] shadow-sm font-medium'
                    : 'text-[#666666] hover:text-[#1A1A1A]'
                }`}
              >
                清單
              </button>
            </div>

            {/* City selector */}
            <select
              value={selectedCity}
              onChange={(e) => setSelectedCity(e.target.value)}
              className="text-xs border border-[#E8E8E8] rounded-lg px-2 py-1.5 bg-white text-[#1A1A1A] focus:outline-none focus:ring-1 focus:ring-[#4A9FD8] cursor-pointer"
            >
              <option value="">全部縣市</option>
              {CITIES.map((city) => (
                <option key={city} value={city}>{city}</option>
              ))}
            </select>
          </div>
        </header>

        {/* ── Messages ── */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
            {/* Empty state */}
            {!hasMessages && (
              <div className="space-y-8 mt-6">
                <div className="text-center space-y-2">
                  <div className="w-14 h-14 rounded-2xl bg-[#1A1A1A] flex items-center justify-center text-white text-2xl mx-auto mb-4 shadow-sm">
                    ⚖
                  </div>
                  <h2 className="text-xl font-bold text-[#1A1A1A]">建築法規 AI 助手</h2>
                  <p className="text-sm text-[#666666]">輸入問題，即時查詢相關法條與解釋</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {PRESETS.map((q) => (
                    <button
                      key={q}
                      onClick={() => submit(q)}
                      disabled={isLoading}
                      className="text-sm text-left px-4 py-3.5 bg-white rounded-xl border border-[#E8E8E8] hover:border-[#4A9FD8] hover:shadow-sm text-[#1A1A1A] transition-all disabled:opacity-50 shadow-sm group"
                    >
                      <span className="text-[#4A9FD8] mr-2 group-hover:mr-3 transition-all">→</span>
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
        <div className="bg-white border-t border-[#E8E8E8] flex-shrink-0 px-4 pt-3 pb-4 space-y-2">
          {/* Preset chips (shown after first message) */}
          {hasMessages && (
            <div
              className="max-w-2xl mx-auto flex gap-1.5 overflow-x-auto pb-1"
              style={{ scrollbarWidth: 'none' }}
            >
              {PRESETS.map((q) => (
                <button
                  key={q}
                  onClick={() => submit(q)}
                  disabled={isLoading}
                  className="flex-shrink-0 text-xs px-3 py-1.5 bg-[#F7F8FA] text-[#666666] rounded-full border border-[#E8E8E8] hover:border-[#4A9FD8] hover:text-[#4A9FD8] disabled:opacity-40 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {/* Input row */}
          <div className="max-w-2xl mx-auto flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault()
                  submit(input)
                }
              }}
              placeholder="請輸入法規相關問題..."
              disabled={isLoading}
              className="flex-1 bg-[#F7F8FA] border border-[#E8E8E8] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4A9FD8] focus:border-transparent disabled:opacity-60 transition text-[#1A1A1A] placeholder:text-[#AAAAAA]"
            />
            <button
              onClick={() => submit(input)}
              disabled={isLoading || !input.trim()}
              className="bg-[#1A1A1A] text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-[#333333] disabled:opacity-40 transition-colors whitespace-nowrap"
            >
              {isLoading ? '⋯' : '送出'}
            </button>
          </div>
        </div>
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
        <div className="max-w-[80%] bg-[#1A1A1A] text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start gap-2.5">
      {/* Bot avatar */}
      <div className="w-7 h-7 rounded-lg bg-[#1A1A1A] flex items-center justify-center text-white text-xs flex-shrink-0 mt-0.5 select-none">
        ⚖
      </div>

      {/* Content card */}
      <div className="flex-1 min-w-0 max-w-[92%] bg-white rounded-2xl rounded-tl-sm border border-[#E8E8E8] shadow-sm overflow-hidden">
        {/* Status bar */}
        {(isRetrieving || (isStreaming && !message.content)) && (
          <div className="flex items-center gap-2 px-5 py-3 text-xs text-[#888888]">
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
              <div className="prose prose-sm max-w-none
                prose-headings:font-semibold prose-headings:text-[#1A1A1A]
                prose-p:text-[#333333] prose-p:leading-relaxed
                prose-li:text-[#333333]
                prose-strong:text-[#1A1A1A]
                prose-code:bg-[#F7F8FA] prose-code:px-1 prose-code:rounded prose-code:text-sm prose-code:text-[#1A1A1A] prose-code:before:content-none prose-code:after:content-none
                prose-pre:bg-[#1A1A1A] prose-pre:text-slate-100
                prose-blockquote:border-[#4A9FD8] prose-blockquote:text-[#666666]
                prose-a:text-[#4A9FD8] prose-a:no-underline hover:prose-a:underline">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm text-[#333333] leading-relaxed whitespace-pre-wrap">
                {message.content}
                {isStreaming && (
                  <span className="inline-block w-0.5 h-[1.1em] bg-[#4A9FD8] ml-px animate-pulse align-middle" />
                )}
              </p>
            )}
          </div>
        )}

        {/* Sources accordion */}
        {isDone && message.sources && message.sources.length > 0 && (
          <div className="border-t border-[#F0F0F0]">
            <button
              onClick={() => setSourcesOpen((v) => !v)}
              className="w-full px-5 py-2.5 flex items-center justify-between text-xs text-[#AAAAAA] hover:text-[#666666] hover:bg-[#F7F8FA] transition-colors"
            >
              <span>引用 {message.sources.length} 條法條</span>
              <svg
                className={`transition-transform ${sourcesOpen ? 'rotate-180' : ''}`}
                width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5"
              >
                <path d="m6 9 6 6 6-6"/>
              </svg>
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
    <div className="border border-[#F0F0F0] rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-3 py-2 flex items-center gap-2 text-left hover:bg-[#F7F8FA] transition-colors"
      >
        <span className="w-4 h-4 rounded-full bg-[#EBF5FF] text-[#4A9FD8] text-[10px] font-bold flex items-center justify-center flex-shrink-0">
          {rank}
        </span>
        <span className="font-medium text-[#333333] flex-1 truncate">
          {source.law_name}
          {source.article_number && (
            <span className="font-normal text-[#666666] ml-1">{source.article_number}</span>
          )}
          {source.chapter && (
            <span className="font-normal text-[#AAAAAA] ml-1 hidden sm:inline">
              {source.chapter}
            </span>
          )}
        </span>
        <span className="text-[#CCCCCC] flex-shrink-0 flex items-center gap-1">
          {similarity}%
          <svg
            className={`transition-transform ${open ? 'rotate-180' : ''}`}
            width="10" height="10" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5"
          >
            <path d="m6 9 6 6 6-6"/>
          </svg>
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 text-[#666666] leading-relaxed border-t border-[#F7F8FA] text-[12px]">
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
      className="animate-spin h-3 w-3 text-[#4A9FD8] flex-shrink-0"
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
