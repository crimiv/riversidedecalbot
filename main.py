import discord
from discord import app_commands
from PIL import Image, ImageOps, ImageFilter
import io
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def process_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    img = img.resize((300, 300))

    bw = ImageOps.grayscale(img).convert("RGBA")

    top = bw.copy()
    mid = bw.copy()
    bot = bw.copy()

    def remove_black(im, thresh=70):
        data = im.getdata()
        new = []
        for r, g, b, a in data:
            if r < thresh and g < thresh and b < thresh:
                new.append((0, 0, 0, 0))
            else:
                new.append((r, g, b, a))
        im.putdata(new)
        return im

    def remove_white(im, thresh=185):
        data = im.getdata()
        new = []
        for r, g, b, a in data:
            if r > thresh and g > thresh and b > thresh:
                new.append((0, 0, 0, 0))
            else:
                new.append((r, g, b, a))
        im.putdata(new)
        return im

    def apply_opacity(im, val):
        factor = val / 255.0
        data = im.getdata()
        new = [(r, g, b, int(a * factor)) for r, g, b, a in data]
        im.putdata(new)
        return im

    top = remove_black(top, 70)
    top = apply_opacity(top, 190)

    mid = ImageOps.invert(mid.convert("RGB")).convert("RGBA")
    mid = remove_white(mid, 185)
    mid = apply_opacity(mid, 165)

    bot = bot.filter(ImageFilter.GaussianBlur(radius=9))
    bot = remove_black(bot, 65)
    bot = apply_opacity(bot, 190)

    merged = Image.alpha_composite(bot, mid)
    merged = Image.alpha_composite(merged, top)
    merged = apply_opacity(merged, 130)

    output = io.BytesIO()
    merged.save(output, format="PNG")
    output.seek(0)
    return output

@tree.command(name="decal")
async def decal(interaction: discord.Interaction, image: discord.Attachment):
    await interaction.response.defer()

    if not image.content_type.startswith("image"):
        await interaction.followup.send("Please upload a valid image file.")
        return

    image_bytes = await image.read()
    result = process_image(image_bytes)

    file = discord.File(fp=result, filename="processed.png")
    await interaction.followup.send(file=file)

@client.event
async def on_ready():
    await tree.sync()

client.run(TOKEN)