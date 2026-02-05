import os
from flask import Flask, request, render_template, send_file
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from werkzeug.utils import secure_filename
from reportlab.lib.utils import ImageReader
import io
from reportlab.pdfbase.pdfmetrics import stringWidth

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER




# ---------- TEXT EXTRACTION ----------
def extract_text_with_styles(pdf_path):
    styled_blocks = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if "lines" in b:
                    for line in b["lines"]:
                        for span in line["spans"]:
                            text = span["text"]
                            font = span.get("font", "Times-Roman")
                            color = span.get("color", 0)
                            r = (color >> 16) & 255
                            g = (color >> 8) & 255
                            b = color & 255
                            styled_blocks.append((text, font, (r, g, b)))
    return styled_blocks

# ---------- IMAGE EXTRACTION ----------
def extract_images_from_pdfs(pdf_paths):
    images = []
    for path in pdf_paths:
        with fitz.open(path) as doc:
            for page in doc:
                for img_index, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    images.append((image_bytes, image_ext))
    return images

# ---------- TEXT WRAPPING ----------
def wrap_text(text, font_name, font_size, max_width):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + " " + word if current_line else word
        width = stringWidth(test_line, font_name, font_size)
        if width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

# ---------- CREATE MERGED TEXT PDF ----------
def render_pages_as_text_pdf(pdf_paths, output_path, selected_font="Times-Roman"):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    x_margin = 50
    y_margin = 50
    text_width_limit = width - 2 * x_margin
    current_y = height - y_margin

    for path in pdf_paths:
        with fitz.open(path) as doc:
            for page in doc:
                blocks = page.get_text("dict")["blocks"]

                for b in blocks:
                    if "lines" in b:
                        for line in b["lines"]:
                            align = line.get("alignment", 0)  # 0=left, 1=center, 2=right
                            for span in line["spans"]:
                                text = span["text"]
                                size = span.get("size", 12)
                                color = span.get("color", 0)
                                r = (color >> 16) & 255
                                g = (color >> 8) & 255
                                b = color & 255

                                # Apply selected font
                                try:
                                    c.setFont(selected_font, size)
                                except:
                                    selected_font = "Times-Roman"
                                    c.setFont(selected_font, size)

                                c.setFillColorRGB(r / 255.0, g / 255.0, b / 255.0)

                                # Wrap and align
                                wrapped_lines = wrap_text(text, selected_font, size, text_width_limit)
                                for wrapped_line in wrapped_lines:
                                    if current_y < y_margin + size:
                                        c.setLineWidth(2)
                                        c.rect(20, 20, width - 40, height - 40)
                                        c.showPage()
                                        current_y = height - y_margin
                                        c.setFont(selected_font, size)

                                    line_width = stringWidth(wrapped_line, selected_font, size)

                                    if align == 0:  # Left
                                        x_pos = x_margin
                                    elif align == 1:  # Center
                                        x_pos = (width - line_width) / 2
                                    elif align == 2:  # Right
                                        x_pos = width - x_margin - line_width
                                    else:
                                        x_pos = x_margin

                                    c.drawString(x_pos, current_y, wrapped_line)
                                    current_y -= size + 2

        if current_y < height - y_margin:
            c.setLineWidth(2)
            c.rect(20, 20, width - 40, height - 40)
            c.showPage()
            current_y = height - y_margin

    c.save()




# ---------- CREATE IMAGE PDF ----------
def create_image_pdf(images, output_path):
    if not images:
        return

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    for img_bytes, img_ext in images:
        image_stream = io.BytesIO(img_bytes)
        img_reader = ImageReader(image_stream)

        img_width, img_height = img_reader.getSize()
        aspect = img_height / float(img_width)
        new_width = width - 100
        new_height = new_width * aspect

        if new_height > height - 100:
            new_height = height - 100
            new_width = new_height / aspect

        x = (width - new_width) / 2
        y = (height - new_height) / 2

        c.drawImage(img_reader, x, y, new_width, new_height)
        c.showPage()

    c.save()

# ---------- CREATE COMBINED TEXT + IMAGE PDF ----------
def create_combined_pdf_interleaved(pdf_paths, output_path, fallback_font="Times-Roman"):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    x_margin = 50
    y_margin = 50
    text_width_limit = width - 2 * x_margin
    current_y = height - y_margin  # Start from the top

    for path_index, path in enumerate(pdf_paths):
        with fitz.open(path) as doc:
            for page_index, page in enumerate(doc):
                blocks = page.get_text("dict")["blocks"]

                for b in blocks:
                    if "lines" in b:
                        for line in b["lines"]:
                            align = line.get("alignment", 0)
                            for span in line["spans"]:
                                text = span["text"]
                                font = span.get("font", fallback_font)
                                size = span.get("size", 12)
                                color = span.get("color", 0)
                                r = (color >> 16) & 255
                                g = (color >> 8) & 255
                                b = color & 255

                                # Set font and color
                                try:
                                    c.setFont(font, size)
                                except:
                                    font = fallback_font
                                    c.setFont(font, size)
                                c.setFillColorRGB(r / 255.0, g / 255.0, b / 255.0)

                                # Wrap text if needed
                                wrapped_lines = wrap_text(text, font, size, text_width_limit)
                                for wrapped_line in wrapped_lines:
                                    if current_y < y_margin + size:
                                        c.setLineWidth(2)
                                        c.rect(20, 20, width - 40, height - 40)
                                        c.showPage()
                                        current_y = height - y_margin
                                        c.setFont(font, size)

                                    if align == 0:  # Left
                                        x_pos = x_margin
                                    elif align == 1:  # Center
                                        line_width = stringWidth(wrapped_line, font, size)
                                        x_pos = (width - line_width) / 2
                                    elif align == 2:  # Right
                                        line_width = stringWidth(wrapped_line, font, size)
                                        x_pos = width - x_margin - line_width
                                    else:
                                        x_pos = x_margin

                                    c.drawString(x_pos, current_y, wrapped_line)
                                    current_y -= size + 2  # space between lines

                # Handle images
                images = page.get_images(full=True)
                for img in images:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    img_bytes = base_image["image"]
                    image_stream = io.BytesIO(img_bytes)
                    img_reader = ImageReader(image_stream)

                    img_width, img_height = img_reader.getSize()
                    aspect = img_height / float(img_width)
                    new_width = width - 100
                    new_height = new_width * aspect

                    if new_height > height - 100:
                        new_height = height - 100
                        new_width = new_height / aspect

                    x = (width - new_width) / 2
                    y = (height - new_height) / 2

                    if current_y < y + new_height:
                        c.setLineWidth(2)
                        c.rect(20, 20, width - 40, height - 40)
                        c.showPage()
                        current_y = height - y_margin

                    c.drawImage(img_reader, x, y, new_width, new_height)
                    c.setLineWidth(2)
                    c.rect(20, 20, width - 40, height - 40)
                    c.showPage()
                    current_y = height - y_margin

        # Finish the last page if needed
        if current_y < height - y_margin:
            c.setLineWidth(2)
            c.rect(20, 20, width - 40, height - 40)
            c.showPage()
            current_y = height - y_margin

    c.save()



# ---------- FLASK ROUTES ----------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        uploaded_files = request.files.getlist("pdfs")
        selected_font = request.form.get("font", "Times-Roman")
        action = request.form.get("action")  # "transform" or "merge"
        saved_paths = []

        for idx, file in enumerate(uploaded_files):
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)

            try:
                with fitz.open(path) as doc:
                    if doc.is_encrypted:
                        return f"<h2>Error: File '{filename}' is password protected.</h2><a href='/'>Go Back</a>"
                saved_paths.append(path)
            except Exception as e:
                return f"<h2>Error processing file '{filename}': {str(e)}</h2><a href='/'>Go Back</a>"

        # Handle single file transform
        if action == "transform" and len(saved_paths) == 1:
            output_path = os.path.join(OUTPUT_FOLDER, "transformed_output.pdf")
            render_pages_as_text_pdf(saved_paths, output_path, selected_font=selected_font)
            return f"""
                <h2>PDF Transformed Successfully!</h2>
                <a href="/download/transformed">Download Transformed PDF</a><br>
                <button onclick="window.location.href='/'">⬅ Back</button>
            """

        # Handle merge only when more than one file
        elif action == "merge" and len(saved_paths) >= 2:
            output_path = os.path.join(OUTPUT_FOLDER, "merged_output.pdf")
            render_pages_as_text_pdf(saved_paths, output_path, selected_font=selected_font)

            images = extract_images_from_pdfs(saved_paths)
            image_output_path = os.path.join(OUTPUT_FOLDER, "extracted_images.pdf")
            create_image_pdf(images, image_output_path)

            combined_output_path = os.path.join(OUTPUT_FOLDER, "combined_output.pdf")
            create_combined_pdf_interleaved(saved_paths, combined_output_path, fallback_font=selected_font)

            return f"""
                <h2>PDFs Merged Successfully!</h2>
                <a href="/download/merged">Download Merged Text PDF</a><br>
                <a href="/download/images">Download Extracted Images PDF</a><br>
                <a href="/download/combined">Download Combined Text + Images PDF</a><br>
                <button onclick="window.location.href='/'">⬅ Back</button>
            """
        else:
            return "<h2>Invalid action or file count.</h2><a href='/'>Go Back</a>"

    return render_template('index.html')


@app.route('/download/merged')
def download_merged():
    return send_file(os.path.join(OUTPUT_FOLDER, "merged_output.pdf"), as_attachment=True)

@app.route('/download/images')
def download_images():
    return send_file(os.path.join(OUTPUT_FOLDER, "extracted_images.pdf"), as_attachment=True)

@app.route('/download/combined')
def download_combined():
    return send_file(os.path.join(OUTPUT_FOLDER, "combined_output.pdf"), as_attachment=True)

@app.route('/download/transformed')
def download_transformed():
    return send_file(os.path.join(OUTPUT_FOLDER, "transformed_output.pdf"), as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
