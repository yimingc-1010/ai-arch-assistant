/**
 * API fetch wrappers and SSE task-stream hook.
 */

import { useEffect } from 'react'

export interface TaskData {
  id: string
  type: 'ingest_pdf' | 'crawl' | 'ingest_crawled'
  status: 'pending' | 'running' | 'done' | 'error'
  progress: number
  message: string
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
}

export interface Document {
  law_name: string
  source_file: string
  chunk_count: number
  ingested_at: string
}

// ---------------------------------------------------------------------------
// PDF ingest
// ---------------------------------------------------------------------------

export async function uploadPDF(formData: FormData): Promise<{ task_id: string }> {
  const res = await fetch('/admin/ingest', { method: 'POST', body: formData })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Upload failed')
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// URL crawl
// ---------------------------------------------------------------------------

export async function startCrawl(url: string): Promise<{ task_id: string }> {
  const res = await fetch('/admin/crawl', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Crawl failed')
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Ingest crawl result into vector store
// ---------------------------------------------------------------------------

export async function ingestCrawlResult(
  taskId: string,
  lawName: string,
  embeddingProvider = 'voyage',
): Promise<{ task_id: string }> {
  const res = await fetch(`/admin/crawl/${taskId}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ law_name: lawName, embedding_provider: embeddingProvider }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Ingest failed')
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Task list
// ---------------------------------------------------------------------------

export async function fetchTasks(): Promise<{ tasks: TaskData[] }> {
  const res = await fetch('/admin/tasks')
  if (!res.ok) throw new Error('Failed to fetch tasks')
  return res.json()
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export async function fetchDocuments(): Promise<{ documents: Document[]; count: number }> {
  const res = await fetch('/admin/documents')
  if (!res.ok) throw new Error('Failed to fetch documents')
  return res.json()
}

// ---------------------------------------------------------------------------
// SSE hook
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Streaming RAG query
// ---------------------------------------------------------------------------

export interface QuerySource {
  law_name: string
  article_number: string
  chapter: string
  text: string
  score: number
  page: number
}

export type StreamEvent =
  | { type: 'sources'; sources: QuerySource[]; retrieved_chunk_count: number }
  | { type: 'token'; text: string }
  | { type: 'done'; model: string; provider: string }
  | { type: 'error'; message: string; traceback?: string }

export interface QueryRequest {
  question: string
  law_names?: string[] | null
  n_results?: number
  llm_provider?: string
  embedding_provider?: string
}

export async function* streamQuery(req: QueryRequest): AsyncGenerator<StreamEvent> {
  const response = await fetch('/rag/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail ?? 'Query failed')
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
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

export function useTaskStream(
  taskId: string | null,
  onUpdate: (task: TaskData) => void,
): void {
  useEffect(() => {
    if (!taskId) return

    const source = new EventSource(`/admin/tasks/${taskId}/stream`)

    source.onmessage = (e) => {
      try {
        const data: TaskData = JSON.parse(e.data)
        onUpdate(data)
        if (data.status === 'done' || data.status === 'error') {
          source.close()
        }
      } catch {
        // ignore parse errors
      }
    }

    source.onerror = () => {
      source.close()
    }

    return () => {
      source.close()
    }
  }, [taskId, onUpdate])
}
