import fitz  # PyMuPDF
import re
import os

# Paths
input_pdf_path = "Letter To Parent (7).pdf"
output_dir = "static/images"
base_url = "https://your-render.com/static/images"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Load PDF
doc = fitz.open(input_pdf_path)
data = {"images": []}

# Loop through odd pages
for page_number in range(0, len(doc), 2):
    page = doc.load_page(page_number)
    text = page.get_text()

    # Extract registration number (like RA2411003010415)
    match = re.search(r"Regist\s*rat\s*ion\s*Number\s*:\s*([A-Z0-9]+)", text)
    if not match:
        print(f"Registration number not found on page {page_number + 1}")
        continue

    reg_no = match.group(1).replace(" ", "")
    image_path = os.path.join(output_dir, f"{reg_no}.jpg")
    image_url = f"{base_url}/{reg_no}.jpg"

    # Render page to image
    pix = page.get_pixmap(dpi=300)
    pix.save(image_path)

    # Append to output structure
    data["images"].append({
        "regNo": reg_no,
        "imagePath": image_url
    })

# Output result
import json
print(json.dumps(data, indent=2))
