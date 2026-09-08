/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./code.html"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "institutional-blue": "#0F172A",
        "bright-sky": "#38BDF8",
        "surface-container-highest": "#e0e3e5",
        "primary": "#000000",
        "on-tertiary-fixed": "#001e2c",
        "on-tertiary-container": "#008ebf",
        "on-primary-fixed-variant": "#3f465c",
        "inverse-primary": "#bec6e0",
        "secondary-fixed-dim": "#89ceff",
        "surface-bright": "#f7f9fb",
        "tertiary-container": "#001e2c",
        "surface-tint": "#565e74",
        "on-error-container": "#93000a",
        "inverse-surface": "#2d3133",
        "secondary-fixed": "#c9e6ff",
        "surface-container": "#eceef0",
        "on-tertiary": "#ffffff",
        "primary-fixed-dim": "#bec6e0",
        "outline": "#76777d",
        "on-background": "#191c1e",
        "tertiary-fixed-dim": "#7bd0ff",
        "surface-container-high": "#e6e8ea",
        "on-secondary-container": "#004666",
        "surface-container-low": "#f2f4f6",
        "primary-fixed": "#dae2fd",
        "error-container": "#ffdad6",
        "on-primary-container": "#7c839b",
        "tertiary": "#000000",
        "inverse-on-surface": "#eff1f3",
        "on-surface-variant": "#45464d",
        "error": "#ba1a1a",
        "tertiary-fixed": "#c4e7ff",
        "on-primary": "#ffffff",
        "primary-container": "#131b2e",
        "surface-container-lowest": "#ffffff",
        "background": "#f7f9fb",
        "surface": "#f7f9fb",
        "on-surface": "#191c1e",
        "outline-variant": "#c6c6cd",
        "on-secondary-fixed": "#001e2f",
        "on-secondary-fixed-variant": "#004c6e",
        "on-secondary": "#ffffff",
        "on-primary-fixed": "#131b2e",
        "surface-variant": "#e0e3e5",
        "on-error": "#ffffff",
        "secondary": "#006591",
        "on-tertiary-fixed-variant": "#004c69"
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        full: "9999px"
      },
      spacing: {
        unit: "4px",
        "margin-mobile": "16px",
        "margin-desktop": "48px",
        lg: "24px",
        xs: "4px",
        md: "16px",
        gutter: "24px",
        sm: "8px",
        xl: "32px"
      },
      fontFamily: {
        "body-md": ["Inter"],
        "headline-lg-mobile": ["Plus Jakarta Sans"],
        "label-sm": ["Inter"],
        "headline-md": ["Plus Jakarta Sans"],
        "headline-lg": ["Plus Jakarta Sans"],
        "display-lg": ["Plus Jakarta Sans"],
        "body-lg": ["Inter"],
        "label-md": ["Inter"],
        "headline-sm": ["Plus Jakarta Sans"]
      },
      fontSize: {
        "body-md": ["16px", { lineHeight: "1.5", fontWeight: "400" }],
        "headline-lg-mobile": ["28px", { lineHeight: "1.2", fontWeight: "600" }],
        "label-sm": ["12px", { lineHeight: "1.2", fontWeight: "600" }],
        "headline-md": ["24px", { lineHeight: "1.3", fontWeight: "600" }],
        "headline-lg": ["32px", { lineHeight: "1.2", fontWeight: "600" }],
        "display-lg": ["48px", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
        "body-lg": ["18px", { lineHeight: "1.6", fontWeight: "400" }],
        "label-md": ["14px", { lineHeight: "1.4", letterSpacing: "0.01em", fontWeight: "500" }],
        "headline-sm": ["20px", { lineHeight: "1.4", fontWeight: "600" }]
      }
    }
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/container-queries")
  ]
};