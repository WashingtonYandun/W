<p align="center">
  <img src="../assets/wawi.jpg" alt="Wawi — Official Mascot of the W Programming Language" width="280" style="border-radius: 20px;">
</p>

# Brand Identity Specification · The W Programming Language

> **Status:** Canonical Brand Specification  
> **Official Mascot:** **Wawi** (inspired by *Pyrophorus noctilucus* / Ninacuro)  
> **Canonical Image:** `assets/wawi.jpg` (Single Source of Truth for documentation and web)  
> **Assets Directory:** `assets/`  

---

## 1. Executive Summary & Mascot Concept

Programming language identities reflect their engineering philosophy through memorable, standalone emblems:
- **Python:** Interlocking serpentine curves (dynamic duality).
- **Rust:** Heavy industrial gear and Ferris the Crab (mechanical safety).
- **Go:** Minimalist typography and Gordon the Gopher (practical concurrency).
- **Linux:** Tux the Penguin (open-source freedom).
- **W:** **Wawi** (bioluminescent click beetle / Ninacuro of the Ecuadorian Andes).

### The Vision of Wawi
**W** is an autonomous, deterministic, self-hostable systems language featuring pure value semantics, Copy-on-Write (CoW), deterministic ARC, monomorphized generics, and zero-GC C99 compilation.

W is personified by its official mascot: **Wawi**, inspired by a real-world biological marvel of Ecuador: the *Ninacuro* (*Pyrophorus noctilucus*, family Elateridae). In Kichwa, *Nina* means light/fire and *Kuru* means insect/bug, while *Wawa* represents the newborn sprout.

1. **Cold Light & Zero Memory Waste:** *Pyrophorus noctilucus* produces cold light with 100% luminous efficiency and zero thermal dissipation. Similarly, W operates with zero garbage collection pauses or runtime bloat: every byte is deterministically owned and released in `CleanupScope`.
2. **Cephalic Luminous Headlights:** Unlike common fireflies, Wawi features two circular light organs directly on its head, represented by large, expressive cyan eyes (`#00bed2`), symbolizing pre-emission type verification (`TypeInterner`).
3. **The 'W' Antennae & Crown:** The antennae and head crest organically form a sharp **'W'** silhouette, celebrating W1's 3-stage cryptographic bootstrap fixed point ($\text{SHA256}(c_0) == \text{SHA256}(c_1) == \text{SHA256}(c_2)$).
4. **Biomechanical Click Mechanism:** The click beetle's frictionless thoracic spine snaps it upright instantly, embodying zero-overhead C99 native dispatch.

---

## 2. Color Palette & Design Tokens

| Token Name | Hex Code | RGB | Role & Application |
| :--- | :--- | :--- | :--- |
| **Electric Cyan** | `#00bed2` | `rgb(0, 190, 210)` | Wawi body, eyes, interactive rings, glow accents. |
| **Deep Navy** | `#00468e` | `rgb(0, 70, 142)` | Core structural contours, dark shading, header accents. |
| **Obsidian Dark** | `#0a1228` | `rgb(10, 18, 40)` | Canvas background, icon tile surface, dark-mode root. |
| **Surface Card** | `#111c38` | `rgb(17, 28, 56)` | Elevated tile surface, tooltips, dialogs. |
| **Border / Grid** | `#1e2d5a` | `rgb(30, 45, 90)` | Tile perimeter border, diagnostic coordinate marks. |
| **Pure White** | `#ffffff` | `rgb(255, 255, 255)` | Die-cut sticker contour, eye highlights, belly patch. |

> [!IMPORTANT]
> **Semantic Isolation:** Green (`#10b981`) and Red (`#ef4444`) are strictly excluded from decorative styling, reserved exclusively for test suite execution outcomes (pass/fail) and runtime exit codes.

---

## 3. Official Image Asset (Canonical: `assets/wawi.jpg`)

To guarantee strict visual consistency across repositories, documentation, and web pages, **`assets/wawi.jpg` is the designated canonical image** for the W language mascot:

| File | Format | Usage Policy | Description |
| :--- | :--- | :--- | :--- |
| `assets/wawi.jpg` | JPEG | **Canonical / Mandatory** | High-resolution 2D die-cut artwork of Wawi. Used everywhere across READMEs, docs, and publications. |
| `assets/wawi.svg` | SVG | Source Vector | Scalable master vector illustration for print and high-DPI scaling. |
| `assets/wawi-icon.svg` | SVG | Favicon / App Icon | Compact face and W-crown framed on a dark squircle tile (`#111c38`). |
| `assets/favicon.svg` | SVG | Browser Tabs | Ultra-crisp, high-contrast favicon. |
| `assets/w-logo-header.svg` | SVG | Banner | Horizontal banner for navigation bars. |

---

## 4. Typography & Wordmark Guidelines

- **Logotype Primary Font:** Inter, SF Pro Display, or Geist Sans (Bold / 900).
- **Monospace Code Font:** JetBrains Mono or Fira Code for CLI prompts and compiler outputs:
  ```text
  W Language v0.2.4 (darwin-arm64, C99 backend)
  Deterministic • Value Semantics • Zero GC
  ```
- **Tagline:**
  `Compact • Deterministic • Statically Typed • Self-Hostable Systems Language`
