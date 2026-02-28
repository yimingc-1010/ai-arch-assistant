/**
 * Proxy GET /api/documents → FastAPI GET /rag/documents
 */
export async function GET() {
  const apiBase = process.env.FASTAPI_URL ?? 'http://localhost:8000'
  const upstream = await fetch(`${apiBase}/rag/documents`, {
    cache: 'no-store',
  })

  if (!upstream.ok) {
    return Response.json({ documents: [], count: 0 }, { status: upstream.status })
  }

  const data = await upstream.json()
  return Response.json(data)
}
