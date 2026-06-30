/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#f97316', dark: '#ea580c' },
        bull: 'var(--color-bull)',
        bear: 'var(--color-bear)',
        neutral: '#64748b',
        navy: {
          950: 'var(--color-navy-950)',
          900: 'var(--color-navy-900)',
          800: 'var(--color-navy-800)',
          700: 'var(--color-navy-700)',
          600: 'var(--color-navy-600)',
          300: 'var(--color-navy-300)',
          200: 'var(--color-navy-200)',
          100: 'var(--color-navy-100)',
          50: 'var(--color-navy-50)',
        }
      },
    },
  },
  plugins: [],
}
