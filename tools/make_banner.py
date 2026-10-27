"""Compose the official existing fox and local typography; no generated substitute."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
R = Path(__file__).resolve().parents[1]
im = Image.new('RGB', (1280, 640))
p = im.load()
for y in range(640):
    for x in range(1280):
        t = max(0, 1-((x-1080)**2/900**2+(y-280)**2/660**2))
        p[x,y] = (int(249-24*t), int(252-17*t), 255)
d = ImageDraw.Draw(im)
fonts = R/'source/assets/fonts'
def font(size):
    f=ImageFont.truetype(str(fonts/'manrope.ttf'), size)
    f.set_variation_by_axes([650 if size>=30 else 500])
    return f
d.rounded_rectangle((66,65,281,103), 19, fill='#e5efff')
d.text((84,73),'LOCAL-FIRST · WINDOWS',font=font(15),fill='#215bcd')
d.text((63,157),'YOEAI 2.0',font=font(84),fill='#10254c')
d.text((69,280),'YOUR AI. YOUR PC.',font=font(35),fill='#193c72')
d.text((69,331),'YOUR RULES.',font=font(35),fill='#2766ee')
d.text((71,425),'A personal AI workspace.',font=font(25),fill='#586b88')
d.text((71,465),'Conversations. Voice. Mini YOE agents.',font=font(21),fill='#586b88')
d.text((71,561),'yoeai.online  /  github.com/Alsehli/YOEAI',font=font(17),fill='#3864a2')
fox = Image.open(R/'source/assets/yoeai-mascot.png').convert('RGBA')
fox.thumbnail((470,530),Image.Resampling.LANCZOS)
im.paste(fox,(770+(470-fox.width)//2,65),fox)
out=R/'docs/images';out.mkdir(exist_ok=True,parents=True)
im.save(out/'social-preview.png', optimize=True)
print(out/'social-preview.png')
