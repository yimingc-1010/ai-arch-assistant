/**
 * Proxy GET /api/documents → FastAPI GET /rag/documents
 */
export async function GET() {
  const upstream = await fetch('http://localhost:8000/rag/documents', {
    cache: 'no-store',
  })

  if (!upstream.ok) {
    return Response.json({ documents: [], count: 0 }, { status: upstream.status })
  }

  const data = await upstream.json()
  return Response.json(data)
}
