/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'navy-950': '#080d1a',
        'navy-900': '#0b0f19',
        'navy-800': '#0e121d',
        'navy-700': '#151a26',
        'navy-600': '#1c2231',
        'accent-blue': '#2563eb',
        'accent-purple': '#8b5cf6',
        'accent-indigo': '#6366f1',
        'accent-emerald': '#10b981',
        'accent-amber': '#facc15',
        'accent-orange': '#f97316',
        'accent-rose': '#f43f5e',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        'premium': '0 4px 20px rgba(0, 0, 0, 0.4)',
        'heavy': '0 10px 40px rgba(0, 0, 0, 0.6)',
      }
    },
  },
  plugins: [],
}
