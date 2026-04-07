import os
import sys
import re

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

import pdfplumber

# Splits PDF into chunks by reading each page and each line. If the line does not match standard 
# sentence-ending, it will simply be interpolated with the next line.
def chunkize(fname : str) -> list[str]:
    path = f"{project_root}/data/{fname}.pdf"
    chunks = []
    with pdfplumber.open(path) as pdf:
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            lines = page.extract_text_lines()

            if not lines:
                continue

            chunk = ""
            for l in range(len(lines)):
                line = lines[l]
                text = line["text"]
                if chunk.endswith('.') and not re.match(r'^\.\s*$', text):
                    chunks.append(chunk)
                    chunk = ""
                else:
                    chunk += text

            if chunk:
                chunks.append(chunk)
    return chunks

print(chunkize("ATO COEPE ICMS")[1])
