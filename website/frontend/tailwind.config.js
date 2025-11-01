/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './_layouts/**/*.html',
    './_includes/**/*.html',
    './*.html',
    './*.md',
    './root-pages/**/*.{html,md}',
    './metars/**/*.html',
    './assets/**/*.js'
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

