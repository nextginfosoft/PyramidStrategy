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
        navy: {
          950: '#0a0e1a', // background
          900: '#111726', // card background
          800: '#1a2236', // input / inner card
          700: '#25304b', // borders / dividers
          600: '#34456c', // hover states
          300: '#94a9d4', // secondary text
          200: '#cbdcf7', // medium text
          100: '#e2ebf8', // primary text
          50: '#f0f5fc',  // glowing text
        }
      },
    },
  },
  plugins: [],
}
