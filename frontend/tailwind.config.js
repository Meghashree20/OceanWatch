/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Ocean-inspired palette
        ocean: {
          50: '#f0f7fa',
          100: '#dbecf2',
          200: '#b8d9e5',
          300: '#8abfcd',
          400: '#5a9db1',
          500: '#3d829a',
          600: '#316a80',
          700: '#2d5868',
          800: '#2a4a57',
          900: '#26404b',
          950: '#162832',
        },
        teal: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
          950: '#042f2e',
        },
        cyan: {
          50: '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
          700: '#0e7490',
          800: '#155e75',
          900: '#164e63',
          950: '#083344',
        },
        navy: {
          50: '#f0f5fa',
          100: '#dbe7f2',
          200: '#bcd3e5',
          300: '#8fb5d4',
          400: '#5e90bf',
          500: '#3d73a5',
          600: '#2d5a8a',
          700: '#264a72',
          800: '#243f5f',
          900: '#1d3450',
          950: '#0f1f33',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      maxWidth: {
        '8xl': '88rem',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(15 31 51 / 0.06), 0 1px 2px 0 rgb(15 31 51 / 0.04)',
        'card-hover': '0 8px 24px -4px rgb(15 31 51 / 0.10), 0 4px 8px -2px rgb(15 31 51 / 0.06)',
        glow: '0 0 32px -4px rgb(34 211 238 / 0.3)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-slow': 'pulseSlow 3s ease-in-out infinite',
        'wave': 'wave 8s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSlow: {
          '0%, 100%': { opacity: '0.6' },
          '50%': { opacity: '1' },
        },
        wave: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
      },
    },
  },
  plugins: [],
};
