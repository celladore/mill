# Design System Documentation

## Overview

Mill uses a comprehensive design system based on Tailwind CSS with custom design tokens.

## Design Tokens

Design tokens are defined in `xtox/frontend/src/xtotext Design Tokens.json` and integrated into Tailwind configuration.

### Colors

#### Primary (Cyan)
- **500:** `#00d4ff` - Main brand color
- **600:** `#00a3cc` - Hover states
- **700:** `#007a99` - Active states

#### Secondary (Purple)
- **500:** `#7c3aed` - Accent color
- **600:** `#6d32d1` - Hover states

#### Accent Colors
- **Amber:** `#f59e0b` - Warnings
- **Emerald:** `#10b981` - Success

#### Neutral Grays
- **50:** `#f8fafc` - Lightest
- **900:** `#0f172a` - Darkest

### Typography

#### Font Families
- **Sans:** Inter, system-ui, -apple-system
- **Mono:** Monaco, Menlo, Ubuntu Mono
- **Display:** Space Grotesk, Inter

#### Font Sizes
- **xs:** 0.75rem (12px)
- **sm:** 0.875rem (14px)
- **base:** 1rem (16px)
- **lg:** 1.125rem (18px)
- **xl:** 1.25rem (20px)
- **2xl:** 1.5rem (24px)
- **3xl:** 1.875rem (30px)
- **4xl:** 2.25rem (36px)

#### Font Weights
- **light:** 300
- **normal:** 400
- **medium:** 500
- **semibold:** 600
- **bold:** 700

### Spacing

Uses Tailwind's default spacing scale (0.25rem base unit):
- **1:** 0.25rem (4px)
- **2:** 0.5rem (8px)
- **4:** 1rem (16px)
- **8:** 2rem (32px)

### Shadows

- **sm:** Small shadow
- **md:** Medium shadow
- **lg:** Large shadow
- **glow:** Custom glow effect `0 0 20px rgba(0, 212, 255, 0.3)`
- **purple-glow:** Purple glow effect

## Components

### Buttons

```jsx
// Primary button
<button className="btn-primary">Click me</button>

// Secondary button
<button className="btn-secondary">Click me</button>
```

### Forms

- Input fields with focus states
- Error states with red borders
- Success states with green borders

### Cards

- White background with shadow
- Rounded corners (xl)
- Padding: p-8

## Dark Theme

Dark theme tokens are defined but not yet fully implemented. To enable:

1. Add `dark` class to root element
2. Use dark mode variants: `dark:bg-background-primary`
3. Update components to use dark theme colors

## Accessibility

### Color Contrast

- Text on primary: WCAG AA compliant
- Text on secondary: WCAG AA compliant
- Error states: High contrast for visibility

### Focus States

- Visible focus rings on all interactive elements
- Keyboard navigation support
- ARIA labels on all interactive components

## Usage Guidelines

1. **Consistency:** Use design tokens, not hardcoded values
2. **Accessibility:** Ensure sufficient color contrast
3. **Responsive:** Use responsive breakpoints
4. **Performance:** Minimize custom CSS

## Component Library

See `xtox/frontend/src/components/` for reusable components:
- `AccessibleFileUpload`
- `AccessibleAlert`
- `ProgressBar`

## Resources

- Design Tokens: `xtox/frontend/src/xtotext Design Tokens.json`
- Tailwind Config: `xtox/frontend/tailwind.config.js`
- SCSS Config: `xtox/frontend/src/xtotext SCSS Configuration.scss`

