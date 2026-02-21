import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{ts,tsx,mdx}'],
  theme: { extend: {} },
  plugins: [require('@tailwindcss/typography')],
}

export default config
