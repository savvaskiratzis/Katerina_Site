#!/usr/bin/env python3
"""Re-tint the dark theme to Katerina's cream/sage artwork theme — property-aware.

A blind search/replace of "rgba(255,255,255,0.05)" is WRONG: the same value is used for a
glass card BACKGROUND (must become more opaque white on a light background) and for a
1px BORDER (white on cream is invisible — it must become a sage line). So the mapping is
chosen by the CSS property on the line, and the script prints every change it makes.

Usage:  python3 tools/retint.py            # dry run: print the change table
        python3 tools/retint.py --write    # apply to css/style.css
"""
import re
import sys

CSS = "css/style.css"
SAGE = (107, 115, 99)          # from the artwork: #757c6d, darkened for text contrast
TERRA = (163, 95, 69)
PAPER = (253, 244, 236)
SHADOW = (122, 104, 86)

# background: glass surfaces (dark glass -> frosted white over cream)
GLASS = {0.03: 0.45, 0.05: 0.55, 0.06: 0.60, 0.08: 0.65, 0.10: 0.60, 0.16: 0.90, 0.20: 0.95}
# border: white hairlines -> sage hairlines (visible, and on-palette)
LINE = {0.05: 0.16, 0.06: 0.18, 0.08: 0.20, 0.10: 0.22, 0.20: 0.30, 0.40: 0.45}


def map_line(line):
    """Return a new line, or None when nothing changes."""
    prop = line.split(":", 1)[0].strip().lower() if ":" in line else ""
    if prop.startswith("--"):
        return None                      # custom properties are handled in the :root block
    is_border = prop.startswith("border") or prop == "border-color"
    is_shadow = prop == "box-shadow"
    is_bg = prop == "background" or prop == "background-color"
    is_color = prop == "color"

    def white_rgba(m):
        a = float(m.group(1))
        if is_border:
            return f"rgba({SAGE[0]},{SAGE[1]},{SAGE[2]},{LINE.get(round(a, 2), 0.2)})"
        if is_bg:
            return f"rgba(255,255,255,{GLASS.get(round(a, 2), 0.55)})"
        if is_color:
            return f"rgba(95,95,86,0.55)"          # placeholder-ish faint text -> muted ink
        return f"rgba(255,255,255,{GLASS.get(round(a, 2), 0.55)})"

    def black_rgba(m):
        a = float(m.group(1))
        if is_shadow:
            return f"rgba({SHADOW[0]},{SHADOW[1]},{SHADOW[2]},{round(a*0.45, 2)})"
        if is_bg:
            return f"rgba({PAPER[0]},{PAPER[1]},{PAPER[2]},0.75)"
        return f"rgba({SHADOW[0]},{SHADOW[1]},{SHADOW[2]},{round(a*0.45, 2)})"

    def navy_rgba(m):
        a = float(m.group(1))
        return f"rgba({PAPER[0]},{PAPER[1]},{PAPER[2]},{a})"

    out = re.sub(r"rgba\(255,\s*255,\s*255,\s*([\d.]+)\)", white_rgba, line)
    out = re.sub(r"rgba\(0,\s*0,\s*0,\s*([\d.]+)\)", black_rgba, out)
    out = re.sub(r"rgba\(26,\s*26,\s*46,\s*([\d.]+)\)", navy_rgba, out)
    # rose tints -> sage / terracotta, KEEPING the alpha (the differences carry design
    # intent: a 0.15 wash vs a 0.35 ring are not the same thing). Focus rings get more
    # alpha, because on cream a 0.24 sage ring is too faint to read as a focus indicator.
    def rose(m):
        a = float(m.group(1))
        if is_shadow:
            return f"rgba({SAGE[0]},{SAGE[1]},{SAGE[2]},{min(0.6, a + 0.2)})"
        return f"rgba({SAGE[0]},{SAGE[1]},{SAGE[2]},{a})"

    out = re.sub(r"rgba\(223,\s*108,\s*115,\s*([\d.]+)\)", rose, out)
    out = re.sub(r"rgba\(255,\s*110,\s*120,\s*([\d.]+)\)",
                 lambda m: f"rgba({TERRA[0]},{TERRA[1]},{TERRA[2]},{m.group(1)})", out)
    # the two "dark label on a mid-tone fill" rules: --dark is now CREAM, so ink it is
    if prop == "color" and "var(--dark)" in out:
        out = out.replace("var(--dark)", "var(--text-dark)")
    if re.search(r"#e8848a", out):
        out = out.replace("#e8848a", "#7d8574")
    return None if out == line else out


def main():
    src = open(CSS, encoding="utf-8").read().splitlines(keepends=True)
    changed = []
    for i, line in enumerate(src, 1):
        new = map_line(line)
        if new:
            changed.append((i, line.rstrip(), new.rstrip()))
    print(f"{len(changed)} γραμμές αλλάζουν\n")
    for i, old, new in changed:
        print(f"{i:5d}  -  {old.strip()}")
        print(f"       +  {new.strip()}")
    if "--write" in sys.argv:
        for i, _, new in changed:
            src[i - 1] = new + "\n"
        open(CSS, "w", encoding="utf-8").write("".join(src))
        print(f"\n✓ γράφτηκε στο {CSS}")
    else:
        print("\n(dry run — τρέξε με --write για να εφαρμοστεί)")


if __name__ == "__main__":
    main()
