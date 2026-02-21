import { useCallback, useEffect, useRef, useState } from 'react'
import { TaskData } from '../api'

interface TrackedTask {
  id: string
  label: string
  data: TaskData | null
  source: EventSource | null
  dismissed: boolean
}

interface Props {
  taskQueue: Array<{ id: string; label: string }>
}

const TYPE_LABELS: Record<string, string> = {
  ingest_pdf: 'PDF 匯入',
  crawl: '爬蟲',
  ingest_crawled: '爬蟲→向量庫',
}

const STATUS_ICON: Record<string, string> = {
  pending: '⏳',
  running: '⏳',
  done: '✅',
  error: '❌',
}

export default function TaskProgress({ taskQueue }: Props) {
  const [tasks, setTasks] = useState<TrackedTask[]>([])
  const sourcesRef = useRef<Record<string, EventSource>>({})

  // Watch for new tasks added to the queue
  const seenIds = useRef(new Set<string>())

  useEffect(() => {
    taskQueue.forEach(({ id, label }) => {
      if (seenIds.current.has(id)) return
      seenIds.current.add(id)

      const newTask: TrackedTask = { id, label, data: null, source: null, dismissed: false }
      setTasks((prev) => [newTask, ...prev])

      // Open SSE stream
      const source = new EventSource(`/admin/tasks/${id}/stream`)
      sourcesRef.current[id] = source

      source.onmessage = (e) => {
        try {
          const data: TaskData = JSON.parse(e.data)
          setTasks((prev) =>
            prev.map((t) => (t.id === id ? { ...t, data } : t))
          )
          if (data.status === 'done' || data.status === 'error') {
            source.close()
            delete sourcesRef.current[id]
          }
        } catch {
          // ignore
        }
      }

      source.onerror = () => {
        source.close()
        delete sourcesRef.current[id]
      }
    })
  }, [taskQueue])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      Object.values(sourcesRef.current).forEach((s) => s.close())
    }
  }, [])

  const dismiss = useCallback((id: string) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, dismissed: true } : t)))
    sourcesRef.current[id]?.close()
    delete sourcesRef.current[id]
  }, [])

  const visible = tasks.filter((t) => !t.dismissed)

  if (visible.length === 0) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-50">
      <div className="max-w-4xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            任務進度
          </span>
          <span className="text-xs text-gray-400">{visible.length} 個任務</span>
        </div>
        <div className="space-y-2 max-h-56 overflow-y-auto">
          {visible.map((task) => (
            <TaskRow key={task.id} task={task} onDismiss={dismiss} />
          ))}
        </div>
      </div>
    </div>
  )
}

function TaskRow({
  task,
  onDismiss,
}: {
  task: TrackedTask
  onDismiss: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const d = task.data
  const status = d?.status ?? 'pending'
  const progress = d?.progress ?? 0
  const message = d?.message ?? '排隊中...'
  const typeLabel = d ? (TYPE_LABELS[d.type] ?? d.type) : ''
  const isDone = status === 'done' || status === 'error'
  const hasError = status === 'error' && Boolean(d?.error)

  return (
    <div className="text-sm">
      <div className="flex items-center gap-3">
        <span className="text-base flex-shrink-0">{STATUS_ICON[status] ?? '⏳'}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            {typeLabel && (
              <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-medium">
                {typeLabel}
              </span>
            )}
            <span className="text-gray-800 font-medium truncate">{task.label}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-200 rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  status === 'error'
                    ? 'bg-red-500'
                    : status === 'done'
                    ? 'bg-green-500'
                    : 'bg-blue-500'
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 w-8 text-right">{progress}%</span>
            <span className={`text-xs truncate max-w-xs ${status === 'error' ? 'text-red-600' : 'text-gray-500'}`}>
              {message}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {hasError && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-red-500 hover:text-red-700 underline"
            >
              {expanded ? '收起' : '查看錯誤'}
            </button>
          )}
          {isDone && (
            <button
              onClick={() => onDismiss(task.id)}
              className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              aria-label="關閉"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Error log panel */}
      {hasError && expanded && (
        <div className="mt-2 ml-8 bg-red-50 border border-red-200 rounded p-2">
          <pre className="text-xs text-red-700 whitespace-pre-wrap break-words font-mono max-h-40 overflow-y-auto">
            {d!.error}
          </pre>
        </div>
      )}
    </div>
  )
}
