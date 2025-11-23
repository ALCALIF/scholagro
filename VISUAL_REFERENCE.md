# 🎨 SCHOLAGRO - VISUAL REFERENCE GUIDE

## Color Palette

### Primary Colors
```
Emerald Green (Primary)
HEX: #10b981
RGB: 16, 185, 129
HSL: 160°, 84%, 40%
Usage: Main brand, buttons, links, accents

Emerald Dark
HEX: #059669
RGB: 5, 150, 105
HSL: 160°, 94%, 31%
Usage: Hover states, darker elements

Emerald Light
HEX: #6ee7b7
RGB: 110, 231, 183
HSL: 160°, 73%, 67%
Usage: Light backgrounds, highlights
```

### Accent Colors
```
Amber Gold (Accent)
HEX: #f59e0b
RGB: 245, 158, 11
HSL: 38°, 92%, 50%
Usage: Highlight, CTAs, badges

Amber Dark
HEX: #d97706
RGB: 217, 119, 6
HSL: 38°, 92%, 44%
Usage: Hover states

Amber Light
HEX: #fcd34d
RGB: 252, 211, 77
HSL: 38°, 99%, 64%
Usage: Light highlights
```

### Neutral Colors
```
Slate 50 (Very Light)
HEX: #f8fafc
Usage: Backgrounds, light surfaces

Slate 100
HEX: #f1f5f9
Usage: Secondary backgrounds

Slate 200
HEX: #e2e8f0
Usage: Borders, dividers

Slate 400
HEX: #94a3b8
Usage: Muted text

Slate 600
HEX: #475569
Usage: Secondary text

Slate 900 (Very Dark)
HEX: #0f172a
Usage: Primary text, dark backgrounds
```

### Semantic Colors
```
Success: #10b981 (Emerald)
Warning: #f59e0b (Amber)
Danger:  #ef4444 (Red)
Info:    #3b82f6 (Blue)
```

---

## Typography Scale

### Headings
```
H1 (Display 4): 2.5rem / 40px
  Font Weight: 700-800
  Letter Spacing: -0.02em
  Line Height: 1.2

H2 (Display 5): 2rem / 32px
  Font Weight: 700
  Letter Spacing: 0px
  Line Height: 1.25

H3: 1.75rem / 28px
  Font Weight: 700
  Letter Spacing: 0px
  Line Height: 1.3

H4: 1.5rem / 24px
  Font Weight: 600
  Letter Spacing: 0px
  Line Height: 1.4

H5: 1.25rem / 20px
  Font Weight: 600
  Letter Spacing: 0px
  Line Height: 1.4
```

### Body Text
```
Large: 1.125rem / 18px
  Font Weight: 400-500
  Line Height: 1.75

Base: 1rem / 16px (default)
  Font Weight: 400-500
  Line Height: 1.6

Small: 0.875rem / 14px
  Font Weight: 400-500
  Line Height: 1.5

X-Small: 0.75rem / 12px
  Font Weight: 500-600
  Line Height: 1.4
```

### Font Family
```
Primary: 'Poppins', system-ui
Weights Available: 300, 400, 500, 600, 700, 800
Letter Spacing: 0.3px (global)
```

---

## Spacing Scale

```
XS: 0.25rem (4px)
SM: 0.5rem  (8px)
MD: 1rem    (16px)
LG: 1.5rem  (24px)
XL: 2rem    (32px)
2XL: 3rem   (48px)
3XL: 4rem   (64px)
4XL: 5rem   (80px)
```

---

## Shadow System

### Box Shadows
```
Shadow XS:
0 1px 2px rgba(15, 23, 42, 0.05)

Shadow SM:
0 1px 3px rgba(15, 23, 42, 0.08),
0 1px 2px rgba(15, 23, 42, 0.04)

Shadow MD:
0 4px 6px rgba(15, 23, 42, 0.1),
0 2px 4px rgba(15, 23, 42, 0.06)

Shadow LG:
0 10px 15px rgba(15, 23, 42, 0.1),
0 4px 6px rgba(15, 23, 42, 0.05)

Shadow XL:
0 20px 25px rgba(15, 23, 42, 0.1),
0 10px 10px rgba(15, 23, 42, 0.04)
```

---

## Border Radius

```
XS: 4px   - Small elements
SM: 8px   - Input fields
MD: 10px  - Buttons
LG: 14px  - Cards
XL: 16px  - Modals
2XL: 20px - Hero sections
Full: 999px - Chips, badges
```

---

## Animation Timing

### Durations
```
Fast:   150ms
Base:   250ms (default)
Slow:   350ms
```

### Easing Functions
```
Standard: cubic-bezier(0.4, 0, 0.2, 1)
Ease In:  cubic-bezier(0.4, 0, 1, 1)
Ease Out: cubic-bezier(0, 0, 0.2, 1)
Bounce:   cubic-bezier(0.34, 1.56, 0.64, 1)
Linear:   linear
```

---

## Component Styles

### Buttons

#### Primary Button (Success)
```
Background: linear-gradient(135deg, #10b981, #059669)
Text Color: white
Padding: 0.625rem 1.25rem (sm), 1rem 1.5rem (lg)
Border Radius: 10px
Box Shadow: 0 4px 15px rgba(16, 185, 129, 0.3)
Hover: translateY(-2px), shadow increases
```

#### Secondary Button (Warning)
```
Background: linear-gradient(135deg, #f59e0b, #d97706)
Text Color: #111
Padding: 0.625rem 1.25rem (sm), 1rem 1.5rem (lg)
Border Radius: 10px
Box Shadow: 0 4px 15px rgba(245, 158, 11, 0.3)
Hover: translateY(-2px), shadow increases
```

#### Outline Button
```
Background: transparent
Border: 2px solid --color
Text Color: --color
Padding: 0.625rem 1.25rem (sm)
Border Radius: 10px
Hover: Background fills with color
```

### Cards

#### Product Card
```
Background: white
Border: 0
Border Radius: 16px
Box Shadow: 0 4px 6px rgba(15, 23, 42, 0.1)
Padding: 1rem
Hover: 
  - translateY(-8px) scale(1.02)
  - shadow: 0 20px 25px rgba(15, 23, 42, 0.1)
  - image scale: 1.08
```

### Forms

#### Input Field
```
Background: white
Border: 2px solid #e2e8f0
Border Radius: 10px
Padding: 0.65rem 0.875rem
Font Weight: 500
Focus:
  - Border Color: #10b981
  - Box Shadow: 0 0 0 0.3rem rgba(16, 185, 129, 0.15)
```

---

## Animation Library

### Fade Animations
```css
.animate-fadeIn        /* Simple fade */
.animate-fadeInUp      /* Fade + Move up 30px */
.animate-fadeInDown    /* Fade + Move down 30px */
.animate-fadeInLeft    /* Fade + Move left 30px */
.animate-fadeInRight   /* Fade + Move right 30px */
```

### Slide Animations
```css
.animate-slideInUp     /* Slide from bottom */
.animate-slideInDown   /* Slide from top */
.animate-slideInLeft   /* Slide from left */
.animate-slideInRight  /* Slide from right */
```

### Scale Animations
```css
.animate-scaleIn       /* Scale from 0.9 */
.animate-scaleInUp     /* Scale + Move up */
```

### Special Effects
```css
.animate-bounceIn      /* Bounce entrance */
.animate-pulse         /* Pulsing opacity */
.animate-spin          /* 360° rotation */
.animate-wobble        /* Wobble side to side */
.animate-shake         /* Shake effect */
.animate-flipIn        /* 3D flip */
```

### Hover Effects
```css
.hover-lift            /* Lifts up with shadow */
.hover-glow            /* Glowing shadow effect */
.hover-scale           /* Scales to 1.05 */
.hover-scale-down      /* Scales to 0.95 */
.hover-rotate          /* Slight rotation */
```

---

## Dark Mode Colors

### Background
```
Primary: #1e293b
Secondary: #0f172a
```

### Text
```
Primary: #f1f5f9
Secondary: #cbd5e1
Muted: #64748b
```

### Components
```
Cards: #1e293b
Borders: rgba(52, 211, 153, 0.1)
```

---

## Responsive Breakpoints

```
Mobile:    0px - 575px      (Extra small)
Tablet:    576px - 991px    (Small to Medium)
Desktop:   992px - 1199px   (Large)
Wide:      1200px+          (Extra Large)
```

---

## Interactive States

### Button States
```
Default:   Base color + shadow
Hover:     Lighter/Darker + Elevated + Enhanced shadow
Active:    Pressed down effect
Focus:     Outline with accent color
Disabled:  Opacity 0.5 + no hover effect
Loading:   Spinner animation + disabled state
```

### Link States
```
Default:    Color: --primary
Hover:      Color: --accent + underline animation
Active:     Color: --primary-dark
Visited:    Color: --slate-600 (or hide)
Focus:      Outline: --accent
```

### Form States
```
Default:    Border: --slate-200
Hover:      Border: --slate-300
Focus:      Border: --primary + Shadow
Error:      Border: --danger + Error color
Disabled:   Background: --slate-100 + Opacity: 0.5
```

---

## Usage Examples

### Creating a Premium Section
```html
<section class="section-alt p-4 p-md-5 rounded-3 animate-slideInRight">
  <h3 class="heading-accent fw-bold mb-4">
    <i class="bi bi-star-fill me-2"></i>Title
  </h3>
  <!-- Content here -->
</section>
```

### Creating Animated Product Cards
```html
<div class="animate-stagger">
  <div class="card product-card shadow-sm hover-lift">
    <!-- Card content -->
  </div>
</div>
```

### Creating Premium Buttons
```html
<button class="btn btn-success fw-bold px-5 hover-lift">
  <i class="bi bi-check-circle me-2"></i>Action
</button>
```

### Creating Smooth Animations
```html
<div class="animate-fadeInUp" style="animation-delay: 0.1s;">
  Fades in upward
</div>
```

---

## Best Practices

1. **Use CSS Variables** for colors and spacing
2. **Apply animations** with utility classes
3. **Respect motion preferences** (prefers-reduced-motion)
4. **Use shadows** for depth and hierarchy
5. **Maintain spacing consistency** using scale
6. **Test dark mode** thoroughly
7. **Optimize for mobile** - lighter animations
8. **Keep animations under 400ms** for best UX
9. **Use semantic colors** for consistent meaning
10. **Follow typography hierarchy** for readability

---

Generated: November 14, 2025
Scholagro Premium Design Visual Reference v1.0
