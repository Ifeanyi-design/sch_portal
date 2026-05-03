/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
        display: ["Plus Jakarta Sans", "IBM Plex Sans", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eef6ff",
          100: "#d8e9ff",
          200: "#b9d7ff",
          300: "#8ec0ff",
          400: "#5ca0fb",
          500: "#377fe8",
          600: "#2564c9",
          700: "#1f4fa2",
          800: "#1f457f",
          900: "#213e67",
        },
        slateink: "#0f172a",
        mist: "#f7f9fc",
        sage: "#e8f4ef",
        sand: "#f8f3ea",
      },
      boxShadow: {
        soft: "0 18px 40px -24px rgba(15, 23, 42, 0.22)",
      },
      backgroundImage: {
        "mesh-glow":
          "radial-gradient(circle at top left, rgba(55, 127, 232, 0.16), transparent 35%), radial-gradient(circle at bottom right, rgba(37, 99, 235, 0.12), transparent 30%)",
      },
    },
  },
  plugins: [],
};
