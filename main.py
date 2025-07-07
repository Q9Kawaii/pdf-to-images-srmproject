from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import fitz  # PyMuPDF
import os, re, io
from PIL import Image
from uuid import uuid4
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# ✅ CORS middleware for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Directory for saving output images (relative, so Render can serve it)
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ✅ Serve the output folder publicly at /output
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

@app.post("/split-pdf")
async def split_pdf(file: UploadFile = File(...)):
    contents = await file.read()
    pdf = fitz.open(stream=contents, filetype="pdf")

    student_chunks = []
    current_chunk = []
    current_reg = None

    regno_pattern = re.compile(r"Registration\s*Number\s*:\s*(RA\d+)", re.IGNORECASE)

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        text = page.get_text()

        match = regno_pattern.search(text)
        if match:
            if current_chunk and current_reg:
                student_chunks.append((current_reg, current_chunk.copy()))
            current_reg = match.group(1)
            current_chunk = [page_num]
        else:
            if current_reg:
                current_chunk.append(page_num)

    if current_chunk and current_reg:
        student_chunks.append((current_reg, current_chunk.copy()))

    result = []

    for reg_no, pages in student_chunks:
        images = []
        for p in pages:
            pix = pdf[p].get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)

        total_height = sum(img.height for img in images)
        combined = Image.new("RGB", (images[0].width, total_height), (255, 255, 255))
        y_offset = 0
        for img in images:
            combined.paste(img, (0, y_offset))
            y_offset += img.height
        cropped_height = int(combined.height / 2)
        combined = combined.crop((0, 0, combined.width, cropped_height))
        filename = f"{reg_no}_{uuid4().hex[:6]}.jpg"
        path = os.path.join(OUTPUT_DIR, filename)
        combined.save(path, "JPEG")

        # ✅ Construct the public URL to serve this file
        public_url = f"https://pdf-to-images-srmproject.onrender.com/output/{filename}"

        result.append({ "regNo": reg_no, "imagePath": public_url })

    return JSONResponse(content={ "status": "success", "images": result })
