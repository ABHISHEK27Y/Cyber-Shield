import fitz
import sys

pdf_path = "pipeline_flow.pdf"
doc = fitz.open(pdf_path)
page = doc.load_page(0)
# Zoom by 3x for high resolution
mat = fitz.Matrix(3.0, 3.0)
pix = page.get_pixmap(matrix=mat, alpha=False)
pix.save("../ppt_imgs/pipeline_flow.png")
print("Saved pipeline_flow.png")
