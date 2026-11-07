import base64, io
from PIL import Image, ImageDraw


def signature():
    img = Image.new('RGB', (400, 140), 'white')
    ImageDraw.Draw(img).line([(15, 90), (70, 45), (150, 100), (260, 30), (380, 85)], fill='black', width=5)
    bio = io.BytesIO(); img.save(bio, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(bio.getvalue()).decode()
