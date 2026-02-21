import { useState } from 'react'
import PDFUpload from './components/PDFUpload'
import URLCrawl from './components/URLCrawl'
import DocumentLibrary from './components/DocumentLibrary'
import TaskProgress from './components/TaskProgress'

type Tab = 'pdf' | 'crawl' | 'docs'

interface QueuedTask {
  id: string
  label: string
}

const TABS: { key: Tab; label: string }[] = [
  { key: 'pdf', label: 'PDF 匯入' },
  { key: 'crawl', label: 'URL 爬蟲' },
  { key: 'docs', label: '文件庫' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('pdf')
  const [taskQueue, setTaskQueue] = useState<QueuedTask[]>([])

  const handleTaskCreated = (taskId: string, label: string) => {
    setTaskQueue((prev) => [...prev, { id: taskId, label }])
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-40">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-xl font-bold text-gray-900">AutoCrawler Admin</h1>
          <p className="text-sm text-gray-500 mt-0.5">法規 RAG 系統管理後台</p>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4">
          <nav className="flex gap-1">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`
                  px-4 py-3 text-sm font-medium border-b-2 transition-colors
                  ${activeTab === key
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        {activeTab === 'pdf' && (
          <PDFUpload onTaskCreated={handleTaskCreated} />
        )}
        {activeTab === 'crawl' && (
          <URLCrawl onTaskCreated={handleTaskCreated} />
        )}
        {activeTab === 'docs' && (
          <DocumentLibrary />
        )}
      </main>

      {/* Fixed bottom task progress drawer */}
      <TaskProgress taskQueue={taskQueue} />
    </div>
  )
}
