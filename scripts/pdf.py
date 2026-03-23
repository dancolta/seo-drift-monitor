#!/usr/bin/env python3
"""
HTML-to-PDF converter for SEO Drift reports.

Uses Playwright to screenshot the full report, then converts to PDF.
This avoids Chrome's PDF pagination quirks entirely — produces a single
clean page with edge-to-edge dark background.

Usage:
    python pdf.py <html_path> [output_path]
"""

import os
import sys
import tempfile


def html_to_pdf(html_path: str, pdf_path: str = None) -> str | None:
    """
    Convert an HTML drift report to PDF.

    Takes a full-page screenshot at 2x resolution, then converts
    the image to a PDF sized exactly to the content.
    """
    if not os.path.isfile(html_path):
        print(f"  [WARN] HTML file not found: {html_path}", file=sys.stderr)
        return None

    if pdf_path is None:
        pdf_path = html_path.rsplit(".", 1)[0] + ".pdf"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [WARN] Playwright not installed — skipping PDF generation.", file=sys.stderr)
        print("  Install: pip install playwright && playwright install chromium", file=sys.stderr)
        return None

    try:
        file_url = "file://" + os.path.abspath(html_path)
        page_width = 900

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": page_width, "height": 800},
                device_scale_factor=2,  # Retina-quality rendering
            )
            page.goto(file_url, wait_until="networkidle")
            page.wait_for_timeout(1500)

            # Inject PDF-specific overrides
            page.add_style_tag(content="""
                .dl { display: none !important; }
                html, body {
                    background: #0a0a0a !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }
                .r {
                    max-width: 100% !important;
                    padding: 36px 48px 40px !important;
                    margin: 0 !important;
                }
            """)

            page.wait_for_timeout(300)

            # Take full-page screenshot as PNG
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_png = tmp.name

            page.screenshot(path=tmp_png, full_page=True, type="png")
            browser.close()

        # Convert PNG to PDF using the image dimensions
        _png_to_pdf(tmp_png, pdf_path)
        os.unlink(tmp_png)

        print(f"  PDF saved: {pdf_path}", file=sys.stderr)
        return pdf_path

    except Exception as e:
        print(f"  [WARN] PDF generation failed: {e}", file=sys.stderr)
        return None


def _png_to_pdf(png_path: str, pdf_path: str):
    """Convert a PNG image to a single-page PDF sized to the image."""
    try:
        # Try Pillow first (most common)
        from PIL import Image
        img = Image.open(png_path)
        # Convert RGBA to RGB (PDF doesn't support alpha)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (10, 10, 10))  # #0a0a0a
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Scale: at 2x device scale, the image is 2x the CSS dimensions.
        # For PDF, we want ~150 DPI for good quality without huge file size.
        # At 2x capture of 900px width, image is 1800px wide.
        # 1800px / 150dpi = 12 inches = 304.8mm — close to A4 height, good width.
        # We'll use 150 DPI so the PDF is roughly A4-width.
        dpi = 150
        img.save(pdf_path, "PDF", resolution=dpi)
        return
    except ImportError:
        pass

    try:
        # Fallback: reportlab
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        from PIL import Image
        img = Image.open(png_path)
        w, h = img.size
        # Scale to A4 width
        ratio = A4[0] / w
        c = rl_canvas.Canvas(pdf_path, pagesize=(A4[0], h * ratio))
        c.drawImage(png_path, 0, 0, width=A4[0], height=h * ratio)
        c.save()
        return
    except ImportError:
        pass

    raise ImportError("Install Pillow (pip install Pillow) for PDF generation.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf.py <html_path> [output_path]")
        sys.exit(1)

    html = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    result = html_to_pdf(html, out)
    if result:
        print(f"PDF: {result}")
    else:
        print("PDF generation failed.", file=sys.stderr)
        sys.exit(1)
