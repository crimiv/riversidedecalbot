import discord
from discord import app_commands
from PIL import Image, ImageOps, ImageFilter
import io
import os
import asyncio
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

def csharp_int_div(n, d):
    if d == 0:
        return 0
    return int(n / d)


def minimum_alpha(Cc, Cb):
    if Cc == Cb:
        return 0
    if Cc > Cb:
        return csharp_int_div(255 * (Cc - Cb) - 1, 255 - Cb) + 1
    return csharp_int_div(255 * (Cb - Cc - 1), Cb) + 1


def adjust_for_alpha(Af, Cc, Cb, Cm):
    num = 255 * (Cc - Cb) - Af * (Cm - Cb)
    if num <= -255:
        Cm += csharp_int_div(num + 255, Af) - 1
    elif num > 0:
        Cm += csharp_int_div(num - 1, Af) + 1
    return max(0, min(255, Cm))


def color_clearer(image, target_color=(255, 255, 255)):
    r, g, b = target_color
    transp_white = (255, 255, 255, 0)

    src = image.convert("RGBA")
    dst = Image.new("RGBA", src.size)
    src_data = src.load()
    dst_data = dst.load()
    width, height = src.size

    for y in range(height):
        for x in range(width):
            r2, g2, b2, a = src_data[x, y]
            if a == 0:
                dst_data[x, y] = transp_white
            else:
                if a == 255:
                    cc = r2
                    cc2 = g2
                    cc3 = b2
                else:
                    cc = csharp_int_div(255 * r + a * (r2 - r), 255)
                    cc2 = csharp_int_div(255 * g + a * (g2 - g), 255)
                    cc3 = csharp_int_div(255 * b + a * (b2 - b), 255)

                num4 = minimum_alpha(cc, r)
                num4 = max(num4, minimum_alpha(cc2, g))
                num4 = max(num4, minimum_alpha(cc3, b))

                if num4 == 0:
                    dst_data[x, y] = transp_white
                else:
                    b3 = adjust_for_alpha(num4, cc, r, r2)
                    b4 = adjust_for_alpha(num4, cc2, g, g2)
                    b5 = adjust_for_alpha(num4, cc3, b, b2)
                    dst_data[x, y] = (b5, b4, b3, num4)

    return dst


def set_opacity(image, opacity):
    alpha_value = int(255 * (opacity / 255.0))
    img = image.convert("RGBA")
    data = img.getdata()
    new = []
    for r, g, b, a in data:
        new_alpha = int(a * alpha_value / 255)
        new.append((r, g, b, new_alpha))
    img.putdata(new)
    return img


def merge_layers(layers):
    base = Image.new("RGBA", layers[0].size, (0, 0, 0, 0))
    for layer in layers:
        base = Image.alpha_composite(base, layer)
    return base


def process_image_method1(image_bytes, bait_bytes=None):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize((500, 500))
    img = ImageOps.grayscale(img).convert("RGBA")

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

    def overlay_bait(base_image, bait_bytes=None):
        if bait_bytes is not None:
            bait = Image.open(io.BytesIO(bait_bytes)).convert("RGBA")
        else:
            bait_path = os.path.join(os.path.dirname(__file__), "bait.png")
            if not os.path.exists(bait_path):
                return base_image
            bait = Image.open(bait_path).convert("RGBA")

        bait = bait.resize(base_image.size, resample=Image.LANCZOS)
        bait = set_opacity(bait, 128)

        bait_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        bait_layer.paste(bait, (0, 0), bait)

        return Image.alpha_composite(bait_layer, base_image)

    img = invert_image(img)
    img = clear_white(img)
    img = invert_image(img)
    img = set_opacity(img, 153)
    img = overlay_bait(img, bait_bytes)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


def process_image_method2(image_bytes, bait_bytes=None):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize((300, 300), resample=Image.LANCZOS)
    img = ImageOps.grayscale(img).convert("RGBA")

    top = color_clearer(img, target_color=(0, 0, 0))

    middle = ImageOps.invert(img.convert("RGB")).convert("RGBA")
    middle = color_clearer(middle, target_color=(255, 255, 255))

    bottom = img.filter(ImageFilter.GaussianBlur(radius=6))
    bottom = color_clearer(bottom, target_color=(0, 0, 0))

    top = set_opacity(top, 190)
    middle = set_opacity(middle, 165)
    bottom = set_opacity(bottom, 190)

    merged = merge_layers([bottom, middle, top])
    merged = set_opacity(merged, 115)

    if bait_bytes is not None:
        bait = Image.open(io.BytesIO(bait_bytes)).convert("RGBA")
        bait = bait.resize(merged.size, resample=Image.LANCZOS)
        bait = set_opacity(bait, 128)
        merged = Image.alpha_composite(bait, merged)

    output = io.BytesIO()
    merged.save(output, format="PNG")
    output.seek(0)
    return output


def process_image(image_bytes, bait_bytes=None, method=1):
    if method == 2:
        return process_image_method2(image_bytes, bait_bytes=bait_bytes)
    return process_image_method1(image_bytes, bait_bytes=bait_bytes)

def create_bait_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize((500, 500), resample=Image.LANCZOS)

    # 1. Black and White
    gray = ImageOps.grayscale(img)

    # 2. Pencil Sketch simulation
    inverted = ImageOps.invert(gray)
    blurred = inverted.filter(ImageFilter.GaussianBlur(radius=20))

    def color_dodge(front, back):
        front_data = front.load()
        back_data = back.load()
        result = Image.new("L", front.size)
        result_data = result.load()
        width, height = front.size
        for x in range(width):
            for y in range(height):
                f = front_data[x, y]
                b = back_data[x, y]
                if f == 255:
                    result_data[x, y] = 255
                else:
                    value = min(255, int((b << 8) / (255 - f)))
                    result_data[x, y] = value
        return result

    sketch = color_dodge(blurred, gray)
    sketch = ImageOps.autocontrast(sketch)

    # 3. Color Clearer (White) based on the decompiled Paint.NET plugin algorithm
    def csharp_int_div(n, d):
        return int(n / d) if d != 0 else 0

    def minimum_alpha(Cc, Cb):
        if Cc == Cb:
            return 0
        if Cc > Cb:
            return csharp_int_div(255 * (Cc - Cb) - 1, 255 - Cb) + 1
        return csharp_int_div(255 * (Cb - Cc - 1), Cb) + 1

    def adjust_for_alpha(Af, Cc, Cb, Cm):
        num = 255 * (Cc - Cb) - Af * (Cm - Cb)
        if num <= -255:
            Cm += csharp_int_div(num + 255, Af) - 1
        elif num > 0:
            Cm += csharp_int_div(num - 1, Af) + 1
        return max(0, min(255, Cm))

    def color_clearer_white(src_img):
        amount = True
        r = g = b = 255
        transp_white = (255, 255, 255, 0)

        src = src_img.convert("RGBA")
        dst = Image.new("RGBA", src.size)
        src_data = src.load()
        dst_data = dst.load()
        width, height = src.size

        for y in range(height):
            for x in range(width):
                r2, g2, b2, a = src_data[x, y]
                if a == 0:
                    dst_data[x, y] = transp_white if amount else (r2, g2, b2, 0)
                else:
                    if a == 255:
                        cc = r2
                        cc2 = g2
                        cc3 = b2
                    else:
                        cc = csharp_int_div(255 * r + a * (r2 - r), 255)
                        cc2 = csharp_int_div(255 * g + a * (g2 - g), 255)
                        cc3 = csharp_int_div(255 * b + a * (b2 - b), 255)

                    num4 = minimum_alpha(cc, r)
                    num4 = max(num4, minimum_alpha(cc2, g))
                    num4 = max(num4, minimum_alpha(cc3, b))

                    if num4 == 0:
                        dst_data[x, y] = transp_white if amount else (r2, g2, b2, 0)
                    else:
                        b3 = adjust_for_alpha(num4, cc, r, r2)
                        b4 = adjust_for_alpha(num4, cc2, g, g2)
                        b5 = adjust_for_alpha(num4, cc3, b, b2)
                        dst_data[x, y] = (b5, b4, b3, num4)

        return dst

    bait_image = color_clearer_white(sketch)

    output = io.BytesIO()
    bait_image.save(output, format="PNG")
    output.seek(0)
    return output

@tree.command(name="decalbypass")
@app_commands.describe(method="Choose the decal bypass style")
@app_commands.choices(method=[
    app_commands.Choice(name="Method 1", value=1),
    app_commands.Choice(name="Method 2", value=2)
])
async def decalbypass(
    interaction: discord.Interaction,
    image: discord.Attachment,
    bait: discord.Attachment,
    method: int = 1,
):
    await interaction.response.defer(ephemeral=True)

    if not (image.content_type and image.content_type.startswith("image")):
        await interaction.followup.send("Please upload a valid image file for the decal.", ephemeral=True)
        return

    if not (bait.content_type and bait.content_type.startswith("image")):
        await interaction.followup.send("Please upload a valid image file for the bait.", ephemeral=True)
        return

    image_bytes = await image.read()
    bait_bytes = await bait.read()
    result = process_image(image_bytes, bait_bytes=bait_bytes, method=method)

    file = discord.File(fp=result, filename="decalbypass.png")
    try:
        await interaction.user.send(file=file)
        message = await interaction.followup.send("Sent to your DMs.", ephemeral=True)
        await message.delete()
    except discord.Forbidden:
        await interaction.followup.send("I couldn't send the image to your DMs. Please make sure your DMs are open for this server.", ephemeral=True)

@tree.command(name="createbait")
async def createbait(
    interaction: discord.Interaction,
    image: discord.Attachment,
):
    await interaction.response.defer(ephemeral=True)

    if not (image.content_type and image.content_type.startswith("image")):
        await interaction.followup.send("Please upload a valid image file.", ephemeral=True)
        return

    image_bytes = await image.read()
    result = create_bait_image(image_bytes)

    file = discord.File(fp=result, filename="bait.png")
    try:
        await interaction.user.send(file=file)
        message = await interaction.followup.send("Sent to your DMs.", ephemeral=True)
        await message.delete()
    except discord.Forbidden:
        await interaction.followup.send("I couldn't send the image to your DMs. Please make sure your DMs are open for this server.", ephemeral=True)

@client.event
async def on_ready():
    await tree.sync()

keep_alive()
client.run(TOKEN)