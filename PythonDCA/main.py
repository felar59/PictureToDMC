from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
import os
import base64
import io
from .picture import Picture
from .csvValues import dataChart
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
import numpy as np
from math import sqrt
import colorsys

class Main():
    def __init__(self, picture64, colorsAmount, datas):
        self.datas = dataChart()
        self.datas.createRGBcol()
        self.colorCount = colorsAmount
        self.picture = Picture(picture64, colorsAmount)
        self.finalPic = Image.new("RGBA", self.picture.get_size(), color=(255,255,255, 1)) 
        self.PicPix = self.finalPic.load()
        self.optimiseDico = {}
        self.values = []
        self.editPicture = Image.new("RGBA", (1, 1), (255, 255, 255, 0))

    def rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        r, g, b = rgb
        return f"#{r:02X}{g:02X}{b:02X}"

    def createDMCimage(self, colorsList = []):
        self.usedColor = []
        self.colors = []
        for y in range(self.picture.get_size()[1]):
            for x in range(self.picture.get_size()[0]):
                self.find_closest_pix(x, y, colorsList)
        self.values = self.sortColors()

    def find_closest_pix(self, x, y, colorsList):
        r, g, b, a = self.picture.get_pix(x, y)
        if a < 150:
            self.PicPix[x, y] = (0, 0, 0, 0)
        elif (r, g, b) in self.optimiseDico.keys():
            self.PicPix[x, y] = self.optimiseDico[(r, g, b)]
        else:
            num, name, color = self.datas.findClosestColor((r, g, b), self.usedColor, colorsList)
            self.optimiseDico[(r, g, b)] = color
            self.PicPix[x, y] = color

            colorHex = self.rgb_to_hex(color)

            self.colors.append((color, str(num)))

            # Define list to send
            self.values.append((str(num), str(name), colorHex))
            self.usedColor.append(num)


    def sortColors(self):
        def rgb_to_hsv_key(color_tuple):
            r, g, b = [c / 255.0 for c in color_tuple[:3]]
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            return (h, s, v)

        sorted_colors = sorted(
            self.colors,
            key=lambda x: rgb_to_hsv_key(x[0])
        )
        newValues = []
        for i in range(len(sorted_colors)):
            for j in range(len(self.values)):
                if sorted_colors[i][1] == self.values[j][0]:
                    newValues.append(self.values[j])
        return newValues
    

    def ResizeFinalPic(self, endSize, Outline):
        self.outline = Outline
        newW = endSize

        ratio = newW / self.finalPic.size[0]
        newH = int(self.finalPic.size[1] * ratio)

        self.finalPic = self.finalPic.resize((newW, newH), Image.NEAREST)
        base = self.finalPic.convert("RGBA")
        result = base.resize(
            (newW * 3, newH * 3),
            resample=Image.NEAREST
        )

        self.editPicture1 = result if not Outline else self.contouring(result, max(1, int(endSize/40)), False)

        return self.editPicture1
    
    
    def createGrid(self, grid_every, heavy_every, scale, heavy_width, grid_width):
        draw = ImageDraw.Draw(self.editPicture)

        # 3) Quadrillage fin (chaque case)
        if grid_every:
            for x in range(0, self.editPicture.width, scale * grid_every):
                draw.line([(x, 0), (x, self.editPicture.height)], fill=(20,20,20,255), width=grid_width)
            for y in range(0, self.editPicture.height, scale * grid_every):
                draw.line([(0, y), (self.editPicture.width, y)], fill=(20,20,20,255), width=grid_width)

        # Quadrillage épais (tous les heavy_every cases)
        if heavy_every and heavy_every > 1:
            for x in range(0, self.editPicture.width, scale * heavy_every):
                draw.line([(x, 0), (x, self.editPicture.height)], fill=(10,10,10,200), width=heavy_width)
            for y in range(0, self.editPicture.height, scale * heavy_every):
                draw.line([(0, y), (self.editPicture.width, y)], fill=(10,10,10,200), width=heavy_width)
    
    def contouring(self, result, thikness, moved):
        result = result.convert("RGBA")

        # Créer un masque des pixels non transparents
        mask = result.split()[3]
    
        expanded_mask = mask.filter(ImageFilter.MaxFilter(thikness * 2 + 1))

        offset_value = 1 if moved else 0
        directional_mask = ImageChops.offset(expanded_mask, offset_value, offset_value)
        directional_mask = directional_mask.filter(ImageFilter.MaxFilter(1))

        contracted_mask = mask.filter(ImageFilter.MinFilter(3))
        combined_mask = ImageChops.lighter(directional_mask, expanded_mask)
        contour_only = ImageChops.subtract(combined_mask, contracted_mask)


        contour_final = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(contour_final)
        draw.bitmap((0, 0), contour_only, fill=(0, 0, 0, 255))

        # Fusionner l’image originale et le contour
        return Image.alpha_composite(contour_final, result)

    def createBroderie(self, grid, legend, backcolor, scale=10, grid_every=1, heavy_every=10,
        grid_width=1, heavy_width=2):

        backcolor = self.datas.from_Hex_to_Rgb(backcolor)
        # Assure que self.finalPic est déjà "cases logiques"
        base = self.finalPic.convert("RGBA")
        logical_w, logical_h = base.size

        # Agrandissement : chaque case -> scale×scale pixels
        self.editPicture = base.resize(
            (logical_w * scale, logical_h * scale),
            resample=Image.NEAREST
        )
        if self.outline:
            self.editPicture = self.contouring(self.editPicture, max(1, int(logical_w/40)), True)

        if grid:
            self.createGrid(grid_every, heavy_every, scale, heavy_width, grid_width)

        pixels = self.editPicture.load()
        for y in range(self.editPicture.height):
            for x in range(self.editPicture.width):
                if pixels[x, y][3] < 100:
                    pixels[x, y] = backcolor

        if legend:
            self.addLegend()

        return self.editPicture

    def addLegend(self):
        self.addBottomSpace()
        self.writeLegend()
        return self.editPicture

    def addBottomSpace(self):
        width, height = self.editPicture.size

        new_height = int(height * 1.2)
        new_img = Image.new("RGB", (width, new_height), color=(255, 255, 255))

        new_img.paste(self.editPicture, (0, 0))

        self.editPicture = new_img

    def writeLegend(self):
        width, height = self.editPicture.size
        draw = ImageDraw.Draw(self.editPicture)
        font = ImageFont.load_default(size=int(width/30))

        draw.line([(0, int(height / 1.2)), (int(width), int(height / 1.2))], fill=(0, 0, 0), width=int(height/500))


        cols = self.colorCount//2+1 if self.colorCount%2==1 else self.colorCount//2
        rows = (self.colorCount + cols - 1) // cols

        spacing_x = width / cols
        spacing_y = height / 10

        for i in range(self.colorCount):
            text = self.values[i][0]

            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            col = i % cols
            row = i // cols

            x = col * spacing_x + (spacing_x - text_width) / 2 + width/75
            y = height - (rows - row) * spacing_y + (spacing_y - text_height) / 2

            box_size = text_height
            draw.rectangle(
            [x - box_size - width/100, y + box_size/2, x - box_size/10 - width/100, y + box_size*1.5], 
            fill=self.values[i][2], outline=(0, 0, 0) )


            draw.text((x, y), text, font=font, fill=(0, 0, 0))

    def replaceColor(self, colorA, colorB):
        width, height = self.finalPic.size
        pixels = self.finalPic.load()

        self.values = [c for c in self.values if colorA["num"] != c[0]]
        self.values.append((colorB["num"], colorB["name"], colorB["hex"]))

        self.colors = [c for c in self.colors if colorA["num"] != c[1]]
        self.colors.append((self.datas.from_Hex_to_Rgb(colorB["hex"]), colorB["num"]))

        colorA, colorB = self.datas.from_Hex_to_Rgb(colorA["hex"]), self.datas.from_Hex_to_Rgb(colorB["hex"])
        for y in range(height):
            for x in range(width):
                if colorA == pixels[x, y][:3]:
                    pixels[x, y] = colorB

        return self.finalPic

    def createMask(self):
        width, height = self.editPicture1.size
        pixels = self.editPicture1.load()
        mask_dict = {}
        mask_pixels_dict = {}

        for i in range(len(self.values)):
            mask = Image.new("RGBA", (width, height), color=(255,255,255, 1))
            mask_dict[str(self.values[i][0])] = mask
            mask_pixels_dict[str(self.values[i][0])] = mask.load()

        color_to_num = {color: num for color, num in self.colors}

        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                if a != 0 and (r,g,b) != (0, 0, 0):
                    colorNum = color_to_num.get((r, g, b))
                    mask_pixels_dict[str(colorNum)][x, y] = (255, 255, 255, 255)

        return mask_dict
                

app = FastAPI()
datas = dataChart()
datas.createRGBcol()

origins = [
    "*",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dist_path = os.path.abspath(os.path.join(BASE_DIR, "../dist"))

app.mount("/static", StaticFiles(directory=dist_path), name="static")

@app.get("/")
def index():
    return FileResponse(os.path.join(BASE_DIR, "../dist/index.html"))

main_instance = None

@app.post("/upload")
async def upload_image(data: dict):
    global main_instance
    try:
        base64_str = data["image"].split(",")[1]
        image_bytes = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(image_bytes))


        main_instance = Main(img, int(data["colorCount"]), datas)
        main_instance.createDMCimage(data["colors"])

        im_resized = main_instance.ResizeFinalPic(int(data["imageSize"]), data["Outline"])

        buf = io.BytesIO()
        im_resized.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        values = [
            {"num": str(num), "name": name, "hex": color}
            for (num, name, color) in main_instance.values
        ]

        return JSONResponse({
            "image": img_b64,
            "values": values
        })

    except Exception as e:
        return {"error": str(e)}

@app.post("/white_mask")
async def white_mask():
    global main_instance
    try:
        
        whiteMasks = main_instance.createMask()

        for key in whiteMasks.keys():
            buf = io.BytesIO()
            whiteMasks[key].save(buf, format="PNG")
            whiteMasks[key] = base64.b64encode(buf.getvalue()).decode("utf-8")

        return JSONResponse({
            "whitemasks": whiteMasks,
        })

    except Exception as e:
        return {"error": str(e)}

@app.post("/download")
async def download_image(data: dict):
    global main_instance
    try:
        broderie = main_instance.createBroderie(data["grid"], data["legend"], data["backcolor"])

        buf = io.BytesIO()
        broderie.save(buf, format="PNG")
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=broderie.png"}
        )

    except Exception as e:
        return {"error": str(e)}
    


@app.post("/new_color")
async def new_color(data: dict):
    global main_instance
    try:
        newColor = datas.findNewColor(data["Colors"], data["Color"])

        return JSONResponse({
            "new_colors": [
                {
                    "num": str(c[0]),
                    "name": c[1],
                    "hex": f"#{c[2][0]:02X}{c[2][1]:02X}{c[2][2]:02X}"
                }
                for c in newColor
            ]
            })
    except Exception as e:
        return {"error": str(e)}
    
@app.post("/add_color")
async def new_color(data: dict):
    global main_instance
    try:
        add_Color = datas.addColor(data["colorNum"])

        return JSONResponse({
            "add_color":
                {
                    "num": str(add_Color[0]),
                    "name": add_Color[1],
                    "hex": f"#{add_Color[2][0]:02X}{add_Color[2][1]:02X}{add_Color[2][2]:02X}"
                }
            })
    except Exception as e:
        return {"error": str(e)}
    
@app.post("/replace")
async def replace(data: dict):
    global main_instance
    try:
        new_img = main_instance.replaceColor(data["select"], data["new"])

        buf = io.BytesIO()
        new_img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return JSONResponse({ "image": img_b64 })
    except Exception as e:
        return {"error": str(e)}