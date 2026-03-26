import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

import pdfplumber

def chunkize(fname : str) -> list[str]:
    path = f"{project_root}/data/{fname}.pdf"
    chunks = []
    with pdfplumber.open(path) as pdf:
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            text = page.extract_text(layout=True)
            chunks = text.split('\n')
            # print(lines)
    return chunks

# chunkize("ATO COEPE ICMS")
