/**
 * Proxy POST /api/query-stream → FastAPI POST /rag/query/stream
 *
 * Using a Route Handler (not next.config rewrites) so that the SSE
 * ReadableStream is piped directly without Node.js buffering.
 */
export async function POST(request: Request) {
  const body = await request.text()

  const apiBase = process.env.FASTAPI_URL ?? 'http://localhost:8000'
  const upstream = await fetch(`${apiBase}/rag/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })

  if (!upstream.ok) {
    const text = await upstream.text()
    return new Response(text, { status: upstream.status })
  }

  // Pipe the SSE stream straight through
  return new Response(upstream.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no',
    },
  })
}
