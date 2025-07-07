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

# ✅ Health check endpoint
@app.get("/")
async def root():
    return {"status": "healthy", "message": "PDF to Images API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2025-07-07"}

@app.post("/split-pdf")
async def split_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        pdf = fitz.open(stream=contents, filetype="pdf")

        student_chunks = []
        current_chunk = []
        current_reg = None

        regno_pattern = re.compile(r"Registration\s*Number\s*:\s*(RA\d+)", re.IGNORECASE)

        # ✅ Parse PDF and group pages by registration number
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

        # Add the last student chunk
        if current_chunk and current_reg:
            student_chunks.append((current_reg, current_chunk.copy()))

        result = []

        for reg_no, pages in student_chunks:
            # ✅ SMART SELECTION: Use first page + every other page if multiple pages exist
            if len(pages) == 1:
                selected_pages = pages
            elif len(pages) == 2:
                # If only 2 pages, use both
                selected_pages = pages
            else:
                # Take first page and every alternate page starting from page 2
                selected_pages = [pages[0]] + pages[2::2]
            
            print(f"Processing {reg_no}: {len(pages)} total pages, using {len(selected_pages)} pages")
            
            images = []
            for p in selected_pages:
                # ✅ Optimized DPI for better performance
                pix = pdf[p].get_pixmap(dpi=120)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                images.append(img)

            if len(images) == 1:
                # Single page - no combining needed
                combined = images[0]
            else:
                # ✅ Combine multiple pages vertically
                total_height = sum(img.height for img in images)
                max_width = max(img.width for img in images)
                combined = Image.new("RGB", (max_width, total_height), (255, 255, 255))
                
                y_offset = 0
                for img in images:
                    # Center the image if widths differ
                    x_offset = (max_width - img.width) // 2
                    combined.paste(img, (x_offset, y_offset))
                    y_offset += img.height

            # ✅ Generate unique filename
            filename = f"{reg_no}_{uuid4().hex[:6]}.jpg"
            path = os.path.join(OUTPUT_DIR, filename)
            
            # ✅ Save with compression for smaller file sizes
            combined.save(path, "JPEG", quality=85, optimize=True)

            # ✅ Construct the public URL to serve this file
            public_url = f"https://pdf-to-images-srmproject.onrender.com/output/{filename}"

            result.append({ 
                "regNo": reg_no, 
                "imagePath": public_url,
                "pagesProcessed": len(selected_pages),
                "totalPages": len(pages)
            })

        pdf.close()
        
        return JSONResponse(content={ 
            "status": "success", 
            "images": result,
            "totalStudents": len(result)
        })
        
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )

# ✅ Alternative endpoint for single page processing (faster)
@app.post("/split-pdf-fast")
async def split_pdf_fast(file: UploadFile = File(...)):
    try:
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
            # ✅ FAST METHOD: Process only the first page
            target_page = pages[0]
            
            pix = pdf[target_page].get_pixmap(dpi=120)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            
            filename = f"{reg_no}_{uuid4().hex[:6]}.jpg"
            path = os.path.join(OUTPUT_DIR, filename)
            img.save(path, "JPEG", quality=85, optimize=True)

            public_url = f"https://pdf-to-images-srmproject.onrender.com/output/{filename}"

            result.append({ 
                "regNo": reg_no, 
                "imagePath": public_url,
                "pagesProcessed": 1,
                "totalPages": len(pages)
            })

        pdf.close()
        
        return JSONResponse(content={ 
            "status": "success", 
            "images": result,
            "totalStudents": len(result)
        })
        
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )
