/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0e1a',
        foreground: '#e4e4e7',
        primary: '#8b5cf6',
        'primary-hover': '#7c3aed',
        secondary: '#1e293b',
        accent: '#a78bfa',
        destructive: '#ef4444',
        muted: '#64748b',
        border: '#334155',
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
        'code-bg': '#1e1e1e',
        'code-text': '#d4d4d4',
        'purple-light': '#c4b5fd',
        'purple-dark': '#6d28d9'
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace']
      },
      animation: {
        'spin-slow': 'spin 3s linear infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}