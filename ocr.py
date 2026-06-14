import os, logging
from PIL import Image
import pytesseract, requests
from io import BytesIO
logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        self.temp = "temp_ocr"
        os.makedirs(self.temp, exist_ok=True)
    async def extract_from_photo(self, photo_file):
        try:
            path = os.path.join(self.temp, f"{os.urandom(4).hex()}.jpg")
            await photo_file.download_to_drive(path)
            img = Image.open(path)
            text = pytesseract.image_to_string(img, lang='ara+eng')
            if os.path.exists(path): os.remove(path)
            return text.strip() or None
        except Exception as e:
            logger.error(f"OCR: {e}"); return None
    async def extract_from_url(self, url):
        try:
            r = requests.get(url, timeout=10)
            img = Image.open(BytesIO(r.content))
            return pytesseract.image_to_string(img, lang='ara+eng').strip() or None
        except Exception as e:
            logger.error(f"OCR URL: {e}"); return None