/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 0: '#0A0B0E', 1: '#101216', 2: '#171A20', 3: '#1E222B' },
        line: '#23262E',
        txt: { 1: '#F2F4F8', 2: '#A6ADBB', 3: '#6B7280' },
        gold: { 300: '#FFD98A', 400: '#F5B841', 500: '#D99A2B', 600: '#B37B1F' },
        mint: '#6EE7B7',
        ember: '#F87171',
        sky2: '#7DD3FC'
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'Menlo', 'monospace']
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(245,184,65,.25), 0 0 24px rgba(245,184,65,.12)',
        panel: '0 1px 0 rgba(255,255,255,.03) inset, 0 8px 30px rgba(0,0,0,.35)'
      },
      backgroundImage: {
        grain: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E\")"
      },
      keyframes: {
        fadeUp: { '0%': { opacity: '0', transform: 'translateY(10px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        pulseSoft: { '0%,100%': { opacity: '.55' }, '50%': { opacity: '1' } },
        sweep: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(250%)' } }
      },
      animation: {
        fadeUp: 'fadeUp .45s cubic-bezier(.22,1,.36,1) both',
        pulseSoft: 'pulseSoft 2.4s ease-in-out infinite',
        sweep: 'sweep 1.4s ease-in-out infinite'
      }
    }
  },
  plugins: []
}
