import base64, io
from PIL import Image, ImageDraw


def signature():
    img = Image.new('RGB', (400, 140), 'white')
    ImageDraw.Draw(img).line([(15, 90), (70, 45), (150, 100), (260, 30), (380, 85)], fill='black', width=5)
    bio = io.BytesIO(); img.save(bio, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(bio.getvalue()).decode()


def putaway(server, unit_id, location='AFR-TEMP'):
    """Préparation de test : unité rangée (sans passer par la validation des capacités des racks)."""
    with server.db() as db:
        db.execute("UPDATE units SET location_id=?,status='available' WHERE id=? AND status='awaiting_putaway'", (location, unit_id))


def png_bytes():
    img = Image.new('RGB', (64, 48), 'white')
    ImageDraw.Draw(img).rectangle([5, 5, 50, 40], outline='black', width=3)
    bio = io.BytesIO(); img.save(bio, format='PNG')
    return bio.getvalue()
