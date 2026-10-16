/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-base': '#06090e',
        'bg-panel': '#0b1118',
        'bg-panel-solid': '#0f1620',
        'bg-card': '#131c28',
        'bg-card-hover': '#1a2636',
        'border-subtle': '#1c2838',
        'border-medium': '#27374d',
        'border-highlight': '#38bdf8',
        'brand-cyan': '#38bdf8',
        'brand-blue': '#3b82f6',
        'accent-green': '#10b981',
        'accent-amber': '#f59e0b',
        'accent-red': '#ef4444',
        'accent-pink': '#ec4899',
        'accent-purple': '#a855f7',
      },
      fontFamily: {
        sans: ['Space Grotesk', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
