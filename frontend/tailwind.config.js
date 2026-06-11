/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#f97316', dark: '#ea580c' },
        bull: '#22c55e',
        bear: '#ef4444',
        neutral: '#64748b',
      },
    },
  },
  plugins: [],
}
