import discord
from discord import app_commands
from PIL import Image, ImageOps, ImageFilter
import io
import os
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")

app = Flask("")

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS


@app.route("/")
def home():
    return "Bot is alive"


def run_web():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run_web)
    t.start()


intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def fit_square(img, size):
    """
    Resize an image to fit within a square while preserving aspect ratio.
    Pads the remaining space with transparency instead of stretching.
    """
    img = img.convert("RGBA")
    return ImageOps.pad(
        img,
        (size, size),
        method=RESAMPLE,
        color=(0, 0, 0, 0),
        centering=(0.5, 0.5),
    )


def set_opacity(img, opacity_percent):
    """
    Adjust overall opacity without touching RGB data.
    """
    img = img.convert("RGBA")
    alpha = img.getchannel("A").point(lambda a: int(a * (opacity_percent / 100.0)))
    img.putalpha(alpha)
    return img


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

    bait = bait.resize(base_image.size, resample=RESAMPLE)
    bait = set_opacity(bait, 50)

    bait_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    bait_layer.paste(bait, (0, 0), bait)

    return Image.alpha_composite(bait_layer, base_image)


def process_image(image_bytes, bait_bytes=None):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = fit_square(img, 500)
    img = ImageOps.grayscale(img).convert("RGBA")

    img = invert_image(img)
    img = clear_white(img)
    img = invert_image(img)
    img = set_opacity(img, 70)

    img = overlay_bait(img, bait_bytes)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


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


def color_clearer(src_img, color, make_transp_white=False):
    r, g, b = color
    amount = make_transp_white
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


def gaussian_blur_plus(src_img, radius, channels, blending_mode):
    blurred = src_img.filter(ImageFilter.GaussianBlur(radius=radius))

    src_data = src_img.load()
    blurred_data = blurred.load()
    dst = Image.new("RGBA", src_img.size)
    dst_data = dst.load()
    width, height = src_img.size

    for y in range(height):
        for x in range(width):
            orig = src_data[x, y]
            blur = blurred_data[x, y]
            r = blur[0] if channels[0] else orig[0]
            g = blur[1] if channels[1] else orig[1]
            b = blur[2] if channels[2] else orig[2]
            a = blur[3] if channels[3] else orig[3]
            dst_data[x, y] = (r, g, b, a)

    return dst


def set_alpha(img, alpha):
    img = img.convert("RGBA")
    data = img.getdata()
    new = [(r, g, b, int(a * (alpha / 255.0))) for (r, g, b, a) in data]
    img.putdata(new)
    return img


def create_bait_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = fit_square(img, 500)

    gray = ImageOps.grayscale(img)
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


def process_image_method2(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = fit_square(img, 300)
    img = ImageOps.grayscale(img).convert("RGBA")

    layer_bottom = img.copy()
    layer_middle = img.copy()
    layer_top = img.copy()

    layer_top = color_clearer(layer_top, color=(0, 0, 0), make_transp_white=False)

    layer_middle = ImageOps.invert(layer_middle.convert("RGB")).convert("RGBA")
    layer_middle = color_clearer(layer_middle, color=(255, 255, 255), make_transp_white=True)

    layer_bottom = gaussian_blur_plus(layer_bottom, radius=6, channels=[True, True, True, True], blending_mode=0)
    layer_bottom = color_clearer(layer_bottom, color=(0, 0, 0), make_transp_white=False)

    layer_top = set_alpha(layer_top, 190)
    layer_middle = set_alpha(layer_middle, 165)
    layer_bottom = set_alpha(layer_bottom, 190)

    base = layer_bottom
    base = Image.alpha_composite(base, layer_middle)
    base = Image.alpha_composite(base, layer_top)

    base = set_alpha(base, 115)

    output = io.BytesIO()
    base.save(output, format="PNG")
    output.seek(0)
    return output


@tree.command(name="decalbypass")
@app_commands.describe(method="Choose the decal bypass method")
@app_commands.choices(
    method=[
        app_commands.Choice(name="Method 1", value="method1"),
        app_commands.Choice(name="Method 2", value="method2"),
    ]
)
async def decalbypass(
    interaction: discord.Interaction,
    image: discord.Attachment,
    method: str,
    bait: discord.Attachment = None,
):
    await interaction.response.defer(ephemeral=True)

    if not (image.content_type and image.content_type.startswith("image")):
        await interaction.followup.send("Please upload a valid image file for the decal.", ephemeral=True)
        return

    if method == "method1":
        if bait is None or not (bait.content_type and bait.content_type.startswith("image")):
            await interaction.followup.send("For Method 1, please upload a valid image file for the bait.", ephemeral=True)
            return
        image_bytes = await image.read()
        bait_bytes = await bait.read()
        result = process_image(image_bytes, bait_bytes=bait_bytes)

    elif method == "method2":
        if bait is not None:
            await interaction.followup.send("Method 2 does not use a bait. Ignoring the bait attachment.", ephemeral=True)
        image_bytes = await image.read()
        result = process_image_method2(image_bytes)

    else:
        await interaction.followup.send("Invalid method selected.", ephemeral=True)
        return

    file = discord.File(fp=result, filename="image.png")
    try:
        await interaction.user.send(file=file)
        message = await interaction.followup.send("Sent to your DMs.", ephemeral=True)
        await message.delete()
    except discord.Forbidden:
        await interaction.followup.send(
            "I couldn't send the image to your DMs. Please make sure your DMs are open for this server.",
            ephemeral=True,
        )


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
        await interaction.followup.send(
            "I couldn't send the image to your DMs. Please make sure your DMs are open for this server.",
            ephemeral=True,
        )


@client.event
async def on_ready():
    await tree.sync()


keep_alive()
client.run(TOKEN)