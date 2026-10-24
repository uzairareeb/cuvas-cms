import type { Config } from "tailwindcss";

// MY CUVAS theme — navy / white / subtle gold (decided 2026-10-24).
// All colour values live in src/app/globals.css as CSS variables
// (brand hex anchors + shadcn HSL channels); this config only maps
// names onto them, so the theme is edited in exactly one place.
const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        // Brand anchors (hex CSS vars in globals.css)
        navy: "var(--color-primary)",
        "navy-deep": "var(--color-navy-deep)",
        brandblue: "var(--color-secondary)",
        gold: "var(--color-accent)",
        appbg: "var(--color-background)",
        surface: "var(--color-surface)",
        ink: "var(--color-foreground)",
        faint: "var(--color-muted)",
        success: "var(--color-success)",
        warning: "var(--color-warning)",
        error: "var(--color-error)",
        // Alias so border-line / divide-line resolve to the token border.
        line: "var(--color-border)",
        // shadcn/ui semantic tokens (HSL channel vars in globals.css)
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      // Premium shadow scale — soft navy-tinted elevation, never grey mud.
      boxShadow: {
        card: "0 1px 2px rgba(23, 54, 93, 0.05), 0 6px 20px rgba(23, 54, 93, 0.06)",
        "card-hover":
          "0 2px 4px rgba(23, 54, 93, 0.06), 0 12px 28px rgba(23, 54, 93, 0.10)",
        pop: "0 8px 30px rgba(15, 43, 76, 0.18)",
        topbar: "0 1px 0 rgba(23, 54, 93, 0.06), 0 8px 24px rgba(23, 54, 93, 0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
