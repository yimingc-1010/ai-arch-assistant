import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '法規問答',
  description: '基於 RAG 的法律條文智慧問答系統',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body className="antialiased">{children}</body>
    </html>
  )
}
