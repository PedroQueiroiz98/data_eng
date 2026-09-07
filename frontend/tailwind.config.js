/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Roboto",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      colors: {
        // Material-ish surface + primary
        primary: {
          DEFAULT: "#4f46e5",
          hover: "#4338ca",
          fg: "#ffffff",
          container: "#e0e7ff",
          "on-container": "#312e81",
        },
        surface: {
          DEFAULT: "#ffffff",
          variant: "#f4f5f7",
          border: "#e2e5ea",
        },
      },
      boxShadow: {
        // Material elevation
        e1: "0 1px 2px 0 rgb(0 0 0 / 0.06), 0 1px 3px 1px rgb(0 0 0 / 0.05)",
        e2: "0 1px 2px 0 rgb(0 0 0 / 0.06), 0 2px 6px 2px rgb(0 0 0 / 0.06)",
        e3: "0 4px 8px 3px rgb(0 0 0 / 0.08), 0 1px 3px 0 rgb(0 0 0 / 0.10)",
        e4: "0 6px 10px 4px rgb(0 0 0 / 0.09), 0 2px 3px 0 rgb(0 0 0 / 0.12)",
      },
      borderRadius: {
        md: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 120ms ease-out",
        "slide-up": "slide-up 160ms cubic-bezier(0.2,0,0,1)",
      },
    },
  },
  plugins: [],
};
