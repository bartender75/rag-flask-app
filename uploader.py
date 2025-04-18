import pdfplumber
import docx
import pandas as pd
import io

def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        texts = []
        for page in pdf.pages:
            content = page.extract_text()
            if content:
                for paragraph in content.split("\n"):
                    if len(paragraph.strip()) > 20:
                        texts.append(paragraph.strip())
    return texts

def extract_text_from_word(file):
    doc = docx.Document(file)
    texts = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if len(text) > 20:
            texts.append(text)
    return texts

def extract_text_from_excel(file):
    texts = []
    xls = pd.ExcelFile(file)
    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)
        for _, row in df.iterrows():
            for cell in row:
                if isinstance(cell, str) and len(cell.strip()) > 20:
                    texts.append(cell.strip())
    return texts

def extract_text_from_file(file, filename):
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file)
    elif filename.endswith(".docx"):
        return extract_text_from_word(file)
    elif filename.endswith(".xlsx"):
        return extract_text_from_excel(file)
    else:
        return []
