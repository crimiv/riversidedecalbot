import discord
from discord import app_commands
from PIL import Image, ImageOps
import io
import os
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def process_image(image_bytes, bait_bytes=None):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize((500, 500))

    def invert_image(im):
        rgb = ImageOps.invert(im.convert("RGB"))
        return Image.merge("RGBA", (*rgb.split(), im.split()[3]))

    def clear_white(im, tol=15):
        data = im.getdata()
        new = []
        for r, g, b, a in data:
            if a > 0 and r >= 255 - tol and g >= 255 - tol and b >= 255 - tol:
                new.append((0, 0, 0, 0))
            else:
                new.append((r, g, b, a))
        im.putdata(new)
        return im

    def set_opacity(im, opacity_percent):
        alpha = int(255 * (opacity_percent / 100.0))
        data = im.getdata()
        new = [(r, g, b, int(a * (alpha / 255.0))) for (r, g, b, a) in data]
        im.putdata(new)
        return im

    def overlay_bait(base_image, bait_bytes=None):
        if bait_bytes is not None:
            bait = Image.open(io.BytesIO(bait_bytes)).convert("RGBA")
        else:
            bait_path = os.path.join(os.path.dirname(__file__), "bait.png")
            if not os.path.exists(bait_path):
                return base_image
            bait = Image.open(bait_path).convert("RGBA")

        bait_width = base_image.width
        bait_ratio = bait_width / bait.width
        bait_size = (bait_width, int(bait.height * bait_ratio))
        bait = bait.resize(bait_size, resample=Image.LANCZOS)
        bait = set_opacity(bait, 50)

        layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        position = (0, base_image.height - bait.height)
        layer.paste(bait, position, bait)

        return Image.alpha_composite(layer, base_image)

    img = invert_image(img)
    img = clear_white(img)
    img = invert_image(img)
    img = set_opacity(img, 60)
    img = overlay_bait(img, bait_bytes)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

@tree.command(name="decalbypass")
async def decalbypass(
    interaction: discord.Interaction,
    image: discord.Attachment,
    bait: discord.Attachment,
):
    await interaction.response.defer()

    if not (image.content_type and image.content_type.startswith("image")):
        await interaction.followup.send("Please upload a valid image file for the decal.")
        return

    if not (bait.content_type and bait.content_type.startswith("image")):
        await interaction.followup.send("Please upload a valid image file for the bait.")
        return

    image_bytes = await image.read()
    bait_bytes = await bait.read()
    result = process_image(image_bytes, bait_bytes=bait_bytes)

    file = discord.File(fp=result, filename="decalbypass.png")
    await interaction.followup.send(file=file)

@client.event
async def on_ready():
    await tree.sync()

keep_alive()
client.run(TOKEN)