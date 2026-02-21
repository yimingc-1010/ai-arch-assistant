import { useCallback, useEffect, useState } from 'react'
import { Document, fetchDocuments } from '../api'

export default function DocumentLibrary() {
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { documents } = await fetchDocuments()
      setDocs(documents)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '載入失敗')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">文件庫</h2>
        <button
          onClick={load}
          disabled={loading}
          className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
        >
          {loading ? '載入中...' : '重新整理'}
        </button>
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {docs.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-400 text-sm">
          尚無已匯入的文件
        </div>
      )}

      {docs.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">法規名稱</th>
                <th className="px-4 py-3">Chunk 數</th>
                <th className="px-4 py-3">來源</th>
                <th className="px-4 py-3">匯入時間</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {docs.map((doc) => (
                <tr key={doc.law_name} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{doc.law_name}</td>
                  <td className="px-4 py-3 text-gray-600">{doc.chunk_count}</td>
                  <td className="px-4 py-3 text-gray-500 truncate max-w-xs" title={doc.source_file}>
                    {doc.source_file}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(doc.ingested_at).toLocaleString('zh-TW')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
