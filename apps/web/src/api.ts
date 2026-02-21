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
