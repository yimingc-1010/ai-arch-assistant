import type { Metadata, Viewport } from "next";
import "./globals.css";

const APP_URL = "https://law.archist.work";

export const metadata: Metadata = {
  title: "建築法規 AI 助手 | 專業建築、土木與都市計畫法規查詢",
  description:
    "專為建築師與工程師設計的 AI 法規助手。提供大眾捷運法、建築法、都市計畫法等即時 RAG 檢索，精準回答建照申請、土地開發與營造標準。",
  keywords: [
    "建築法規",
    "建築師考試",
    "建照申請",
    "都市計畫",
    "RAG AI",
    "營造法規",
    "台灣建築法律",
  ],
  authors: [{ name: "法規問答助手團隊" }],
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    url: APP_URL,
    title: "法規問答助手：您的建築法律 AI 顧問",
    description:
      "不再迷失在法條中。透過 RAG 技術，一鍵檢索最新建築法規，提供精準引用與解釋。",
    images: [{ url: `${APP_URL}/og-image.jpg` }],
  },
  twitter: {
    card: "summary_large_image",
    title: "法規問答助手",
    description: "專業建築法規 RAG 檢索系統，加速建照審查與規劃流程。",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#2563eb",
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "建築法規問答助手",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description: "基於 RAG 技術的台灣建築法規智慧檢索系統",
  featureList: [
    "語意法規檢索",
    "自動分類標籤",
    "法條來源溯源",
    "多法規聯動分析",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
