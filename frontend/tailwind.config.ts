import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          navy: '#0F172A',       // deep slate/navy for navigation
          navyLight: '#1E293B',  // slate border & item hover
          navyMuted: '#334155',  // secondary nav text / borders
          blue: '#2563EB',       // primary action blue
          blueHover: '#1D4ED8',  // hover action blue
        },
        verdict: {
          pass: '#059669',       // emerald-600
          passBg: '#ECFDF5',     // emerald-50
          passBorder: '#A7F3D0', // emerald-200
          fail: '#DC2626',       // crimson / red-600
          failBg: '#FEF2F2',     // red-50
          failBorder: '#FECACA', // red-200
          review: '#D97706',     // amber-600
          reviewBg: '#FFFBEB',   // amber-50
          reviewBorder: '#FDE68A', // amber-200
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Oxygen',
          'Ubuntu',
          'Cantarell',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
}

export default config
