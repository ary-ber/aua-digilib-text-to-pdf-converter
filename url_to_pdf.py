# This script requires the following libraries to be installed:
# pip install requests beautifulsoup4 fpdf
# It also requires a font that supports Armenian characters for the PDF generation.

import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import re
from urllib.parse import urljoin
import os

digilib_url = '''https://digilib.aua.am/book/3052/3602/24099/%D4%B3%D5%A1%D5%B6%D5%B4%D5%A5%D6%82%20%D5%A5%D6%82%20%D5%8F%D5%A1%D5%B2%D5%A5%D6%82'''

def sanitize_filename(name):
    """Removes characters from a string that are invalid for a filename."""
    return re.sub(r'[\\/*?:"<>|]',"", name).strip()

def get_book_details(main_url):
    """Fetches the book title and the list of chapters from the main book page."""
    print(f"Fetching book details from: {main_url}")
    response = requests.get(main_url)
    response.raise_for_status()  # Raise an exception for bad status codes
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract the book title from the specified div
    details_panel = soup.find('div', class_='product-details-panel')
    book_title_tag = details_panel.find('div').find('h1') if details_panel else None
    book_title = book_title_tag.text.strip() if book_title_tag else "Untitled Book"


    toc_div = soup.find('div', class_='tree well')
    if not toc_div:
        raise ValueError("Could not find the table of contents (div with class 'tree well').")

    # Extract chapter titles and their URLs
    chapters = []
    for a_tag in toc_div.find_all('a', href=True):
        chapter_title = a_tag.text.strip()
        # Convert relative URL to absolute
        chapter_url = urljoin(main_url, a_tag['href'])
        chapters.append({'title': chapter_title, 'url': chapter_url})

    if not chapters:
        raise ValueError("No chapters found in the table of contents.")

    print(f"Found {len(chapters)} chapters for the book: '{book_title}'")
    return book_title, chapters

class PDF(FPDF):
    """Custom PDF class to add a page number footer."""
    def footer(self):
        self.set_y(-15)
        # Use a font that is known to exist, otherwise fall back
        try:
            self.set_font('ArmenianFont', 'I', 8)
        except RuntimeError:
            self.set_font('Arial', 'I', 8) # Fallback
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_book_pdf(book_title, chapters):
    """
    Generates a PDF file from the book's chapters, including titles, images, and content.
    """
    pdf_filename = f"{sanitize_filename(book_title)}.pdf"
    pdf = PDF()
    toc_entries = [] # To store table of contents data (title, page_number)

    # --- Font Configuration ---
    # Get the absolute path of the directory where the script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(script_dir, 'fonts')

    # Define the full, absolute paths to the font files.
    font_regular_path = os.path.join(fonts_dir, 'DejaVuSans.ttf')
    font_bold_path = os.path.join(fonts_dir, 'DejaVuSans-Bold.ttf')
    font_italic_path = os.path.join(fonts_dir, 'DejaVuSans-Oblique.ttf')

    if not os.path.exists(font_regular_path) or not os.path.exists(font_bold_path) or not os.path.exists(font_italic_path):
        print("--------------------------------------------------------------------")
        print("ERROR: Required DejaVu font files not found.")
        print(f"Please ensure the following files are in the 'fonts' directory next to the script:")
        print(f"  - {font_regular_path} (Missing: {'Yes' if not os.path.exists(font_regular_path) else 'No'})")
        print(f"  - {font_bold_path} (Missing: {'Yes' if not os.path.exists(font_bold_path) else 'No'})")
        print(f"  - {font_italic_path} (Missing: {'Yes' if not os.path.exists(font_italic_path) else 'No'})")
        print("\nYou can download them from a trusted source like: https://dejavu-fonts.github.io/")
        print("--------------------------------------------------------------------")
        return  # Stop execution if fonts are missing

    # Add Armenian-supporting font
    pdf.add_font('ArmenianFont', '', font_regular_path, uni=True)
    pdf.add_font('ArmenianFont', 'B', font_bold_path, uni=True)
    pdf.add_font('ArmenianFont', 'I', font_italic_path, uni=True)

    # Create the title page
    pdf.add_page()
    pdf.set_font('ArmenianFont', 'B', 24)
    pdf.multi_cell(0, 15, book_title, 0, 'C')
    pdf.ln(20)

    # Loop through each chapter and add it to the PDF
    for i, chapter in enumerate(chapters):
        print(f"Processing Chapter {i+1}/{len(chapters)}: {chapter['title']}")
        pdf.add_page()
        # Record the chapter title and current page number for the TOC
        toc_entries.append({'title': chapter['title'], 'page': pdf.page_no()})

        pdf.set_font('ArmenianFont', 'B', 16)
        pdf.multi_cell(0, 10, chapter['title'], 0, 'L')
        pdf.ln(5)

        try:
            # Get the content page for the chapter
            chapter_response = requests.get(chapter['url'])
            chapter_response.raise_for_status()
            chapter_soup = BeautifulSoup(chapter_response.content, 'html.parser')

            # Find, download, and add the chapter's image
            image_panel = chapter_soup.find('div', class_='work-reader-image-panel')
            if image_panel and image_panel.find('img'):
                img_tag = image_panel.find('img')
                img_url = urljoin(chapter['url'], img_tag['src'])
                img_response = requests.get(img_url)
                img_response.raise_for_status()

                # Save image to a temporary file to be embedded in the PDF
                img_filename = f"temp_image_for_pdf_{i}.jpg"
                with open(img_filename, 'wb') as f:
                    f.write(img_response.content)

                pdf.image(img_filename, x=pdf.get_x(), w=pdf.w - pdf.l_margin - pdf.r_margin)
                os.remove(img_filename)  # Clean up the temporary image file
                pdf.ln(5)

            # Find and add the chapter's text content
            content_div = chapter_soup.find('div', class_='work-reader-body-panel')
            if content_div:
                pdf.set_font('ArmenianFont', '', 12)

                # To handle explicit line breaks within paragraphs
                for br in content_div.find_all("br"):
                    br.replace_with("\n")

                # Process each paragraph to preserve structure.
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    for p in paragraphs:
                        text = p.get_text(separator=' ', strip=True)
                        pdf.multi_cell(0, 7, text)
                        pdf.ln(3)
                else:
                    text = content_div.get_text(separator=' ', strip=True)
                    pdf.multi_cell(0, 7, text)

            else:
                pdf.set_font('ArmenianFont', 'I', 12)
                pdf.multi_cell(0, 10, "Could not find text content for this chapter.")

        except requests.exceptions.RequestException as e:
            print(f"  -> Could not fetch chapter content: {e}")
            pdf.set_font('ArmenianFont', 'I', 12)
            pdf.multi_cell(0, 10, f"Error fetching content: {e}")
        except Exception as e:
            print(f"  -> An error occurred while processing this chapter: {e}")
            pdf.set_font('ArmenianFont', 'I', 12)
            pdf.multi_cell(0, 10, f"An error occurred: {e}")

    # --- Add the Table of Contents at the end of the document ---
    pdf.add_page()
    pdf.set_font('ArmenianFont', 'B', 20)
    pdf.cell(0, 15, "Table of Contents", 0, 1, 'C')
    pdf.ln(10)

    pdf.set_font('ArmenianFont', '', 12)
    available_width = pdf.w - pdf.l_margin - pdf.r_margin
    page_num_col_width = 20
    title_col_width = available_width - page_num_col_width
    line_height = 7  # The height of a single line of text

    for entry in toc_entries:
        title = entry['title']
        page_num = str(entry['page'])

        # --- Manual Height Calculation (fpdf compatible) ---
        # This logic calculates how many lines the title will take up in the cell.
        words = title.split(' ')
        lines = 1
        current_line_text = ''
        for word in words:
            # Check if adding the next word exceeds the column width
            if pdf.get_string_width(current_line_text + word + ' ') > title_col_width:
                lines += 1
                current_line_text = word + ' '
            else:
                current_line_text += word + ' '
        
        title_height = lines * line_height
        # --- End of Manual Calculation ---

        # Check if there is enough space on the current page for this entry.
        if pdf.get_y() + title_height >= pdf.page_break_trigger:
            pdf.add_page()

        # Record the Y position before drawing, as multi_cell will advance it.
        start_y = pdf.get_y()

        # Draw the title cell.
        pdf.multi_cell(w=title_col_width, h=line_height, txt=title, align='L')

        # Move the cursor to the position for the page number.
        pdf.set_xy(pdf.l_margin + title_col_width, start_y)

        # Draw the page number cell. Its height is set to the calculated title_height
        # to ensure the cursor moves below the entire entry for the next line.
        pdf.cell(w=page_num_col_width, h=title_height, txt=page_num, align='R', ln=1)

        # Add gap between TOC entries for readability.
        pdf.ln(4)


    try:
        pdf.output(pdf_filename)
        print(f"\nSuccessfully created PDF: {pdf_filename}")
    except Exception as e:
        print(f"An error occurred while saving the PDF: {e}")



if __name__ == "__main__":
    try:
        book_title, chapters = get_book_details(digilib_url)
        create_book_pdf(book_title, chapters)
    except Exception as e:
        print(f"A critical error occurred: {e}")
