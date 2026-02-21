import React, { useCallback, useRef, useState } from 'react'
import { uploadPDF } from '../api'

interface Props {
  onTaskCreated: (taskId: string, label: string) => void
}

export default function PDFUpload({ onTaskCreated }: Props) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [lawName, setLawName] = useState('')
  const [provider, setProvider] = useState('voyage')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setError('請選擇 PDF 檔案')
      return
    }
    setFile(f)
    setError('')
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [])

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(true)
  }

  const onDragLeave = () => setDragging(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { setError('請選擇檔案'); return }
    setLoading(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (lawName) fd.append('law_name', lawName)
      fd.append('embedding_provider', provider)
      const { task_id } = await uploadPDF(fd)
      onTaskCreated(task_id, `匯入 ${lawName || file.name}`)
      setFile(null)
      setLawName('')
      if (inputRef.current) inputRef.current.value = ''
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '上傳失敗')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-lg font-semibold mb-4">上傳 PDF 法規</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Drop zone */}
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => inputRef.current?.click()}
          className={`
            border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors
            ${dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'}
          `}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          {file ? (
            <p className="text-sm text-gray-700 font-medium">{file.name}</p>
          ) : (
            <>
              <p className="text-gray-500 text-sm">拖放 PDF 至此處，或點擊選擇</p>
              <p className="text-gray-400 text-xs mt-1">僅支援 .pdf 格式</p>
            </>
          )}
        </div>

        {/* Law name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            法規名稱（選填，預設使用檔名）
          </label>
          <input
            type="text"
            value={lawName}
            onChange={(e) => setLawName(e.target.value)}
            placeholder="例：建築法"
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Embedding provider */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Embedding Provider
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="voyage">Voyage AI (voyage-law-2)</option>
            <option value="openai">OpenAI</option>
          </select>
        </div>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading || !file}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '上傳中...' : '開始匯入'}
        </button>
      </form>
    </div>
  )
}
