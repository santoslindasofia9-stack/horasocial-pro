---
name: Horizon Academic Management
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#006591'
  on-secondary: '#ffffff'
  secondary-container: '#39b8fd'
  on-secondary-container: '#004666'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#001e2c'
  on-tertiary-container: '#008ebf'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#c9e6ff'
  secondary-fixed-dim: '#89ceff'
  on-secondary-fixed: '#001e2f'
  on-secondary-fixed-variant: '#004c6e'
  tertiary-fixed: '#c4e7ff'
  tertiary-fixed-dim: '#7bd0ff'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c69'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.4'
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.2'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style

The design system is engineered for a school social service management platform, prioritizing administrative efficiency and academic integrity. The brand personality is **Professional, Reliable, and Facilitative**. It aims to evoke a sense of organized progress and civic responsibility, moving away from cluttered educational tools toward a streamlined, modern SaaS experience.

The visual style is **Corporate Minimalism** with **Tactile Subtle Accents**. It leverages high-contrast typography for maximum legibility and a clean, light-filled interface to reduce cognitive load for administrators and students. Subtle geometric textures—specifically low-opacity gear and academic motifs—are used sparingly to provide depth and reinforce the platform's institutional focus without distracting from the data.

## Colors

The palette is anchored in a high-contrast foundation of **Navy Blue (#0F172A)** and **Pure White (#FFFFFF)**. This combination ensures WCAG AAA compliance for text readability and establishes an authoritative, professional tone.

- **Primary (Navy Blue):** Used for core branding, primary actions, and headline text. It represents stability and institutional trust.
- **Secondary (Sky Blue):** Utilized for active states, primary visual details, and iconography. It adds a modern, energetic spark to the conservative navy base.
- **Surface Neutrals:** A light grey (#F8FAFC) is used for container backgrounds and section dividers to distinguish between different functional areas of the UI.
- **Gradients:** Subtle linear gradients (180deg, Secondary to Tertiary) may be applied to primary buttons and key progress indicators to provide a modern, "glassy" depth.

## Typography

This design system uses a dual-font strategy to balance character with utility. 

**Plus Jakarta Sans** is the headline face, chosen for its friendly yet professional geometric construction. It is always set in **Semibold (600)** or **Bold (700)** for headings to ensure a strong visual hierarchy.

**Inter** is the workhorse for body copy and UI labels. Its high x-height and neutral tone make it ideal for data-heavy tables and long-form management instructions. 

- **Hierarchy:** Use larger display sizes for dashboard overviews and smaller, tighter labels for data grids.
- **Color:** Headlines should almost exclusively use the Navy Blue (#0F172A), while body text can vary between Navy and a Muted Slate (#64748B) for secondary information.

## Layout & Spacing

The design system employs a **12-column fluid grid** for desktop and a **single-column vertical stack** for mobile. 

- **Grid Logic:** A 24px gutter is maintained across desktop views to ensure breathable whitespace between management cards.
- **Rhythm:** All spacing is based on a **4px baseline grid**. Padding within components should follow the 4px increment rule (e.g., 8px, 16px, 24px).
- **Density:** The layout favors "Comfortable" density for public-facing pages and "Compact" density for administrative data tables to allow more information to be visible at once.
- **Safe Zones:** Background textures (gears/graduation caps) must never overlap with text and should maintain a minimum 40px clearance from the main content containers.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** and **Subtle Shadows** rather than heavy borders.

- **Background Layer:** The base canvas is either #FFFFFF or #F8FAFC. 
- **Surface Layer:** White cards or containers sit on the grey background, using a very soft, diffused shadow (0px 4px 20px rgba(15, 23, 42, 0.05)) to suggest elevation.
- **Interactive Layer:** Buttons and active elements use a slightly more pronounced shadow and a subtle linear gradient to appear "pressable."
- **Overlays:** Modals and dropdowns use a "Glassmorphism" light blur (12px backdrop-blur) to maintain context of the underlying management dashboard while focusing the user's attention.

## Shapes

The design system utilizes **Rounded (0.5rem)** corners as the default for standard components like input fields and cards. 

- **Buttons:** Use `rounded-lg` (1rem) to create a softer, more inviting call-to-action that contrasts with the structured grid.
- **Badges/Chips:** Use `rounded-full` (pill-shaped) to distinguish them from interactive buttons.
- **Visual Continuity:** All icons should follow a "Line-Art" style with rounded caps and joins to match the corner radii of the containers.

## Components

### Buttons
- **Primary:** Navy Blue (#0F172A) background, White text. Subtle gradient on hover. Rounded-lg (1rem).
- **Secondary:** White background with a Navy Blue border (1px). 
- **Ghost:** No background, Secondary Blue (#0EA5E9) text. Used for less critical actions like "Cancel."

### Input Fields
- **Default:** 1px border (#E2E8F0), 8px padding, Inter Medium font.
- **Focus:** 2px border in Sky Blue (#0EA5E9) with a soft outer glow.
- **Labels:** Always placed above the field in Label-MD style, Navy Blue.

### Cards
- Standard containers for student profiles or social service hours. 
- White background, 0.5rem rounded corners, 24px internal padding.
- Include a very faint (3%) gear icon watermark in the bottom-right corner of summary cards.

### Chips & Status Indicators
- **Approved:** Light Green background, Dark Green text.
- **Pending:** Light Amber background, Dark Amber text.
- **In Progress:** Light Blue (#E0F2FE) background, Sky Blue (#0EA5E9) text.

### Data Tables
- Clean, borderless rows with subtle dividers (#F1F5F9).
- Alternating row highlights using #F8FAFC for better horizontal scanning in long reports.