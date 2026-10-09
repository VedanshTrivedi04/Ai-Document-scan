import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1000, 630
card = Image.new('RGB', (W, H), '#E8F3F8')
draw = ImageDraw.Draw(card)

# Background subtle design / gradient lines
for i in range(0, W, 25):
    draw.line([(i, 0), (i + 150, H)], fill='#D9ECF4', width=2)

# Top header banner
draw.rectangle([(0, 0), (W, 115)], fill='#2B547E')
draw.rectangle([(0, 115), (W, 122)], fill='#E5A823') # gold stripe

# Fonts
font_dir = r'C:\Windows\Fonts'
font_title = ImageFont.truetype(os.path.join(font_dir, 'arialbd.ttf'), 26)
font_subtitle = ImageFont.truetype(os.path.join(font_dir, 'arial.ttf'), 18)
font_pan = ImageFont.truetype(os.path.join(font_dir, 'arialbd.ttf'), 30)
font_label = ImageFont.truetype(os.path.join(font_dir, 'arial.ttf'), 16)
font_value = ImageFont.truetype(os.path.join(font_dir, 'arialbd.ttf'), 24)

# Try Segoe Script or fallback to italic/arial
try:
    font_sig = ImageFont.truetype(os.path.join(font_dir, 'segoepr.ttf'), 28)
except Exception:
    font_sig = ImageFont.truetype(os.path.join(font_dir, 'ariali.ttf'), 26)

# Header text
draw.text((W // 2, 35), 'INCOME TAX DEPARTMENT', fill='#FFFFFF', font=font_title, anchor='mm')
draw.text((W // 2, 72), 'GOVT. OF INDIA', fill='#FFFFFF', font=font_subtitle, anchor='mm')
draw.text((W // 2, 98), 'Permanent Account Number Card', fill='#E5A823', font=font_label, anchor='mm')

# Paste Rahul Photo on left
photo_path = os.path.join('sample-documents', 'rahul_photo.jpg')
photo = Image.open(photo_path).convert('RGB')
photo_resized = photo.resize((190, 240), Image.Resampling.LANCZOS)
card.paste(photo_resized, (50, 155))
draw.rectangle([(48, 153), (242, 397)], outline='#2B547E', width=3)

# Details on right
x_labels = 280

# PAN Number
draw.text((x_labels, 155), 'Permanent Account Number / PAN', fill='#555555', font=font_label)
draw.text((x_labels, 180), 'ABCFR1994K', fill='#0B3056', font=font_pan)

# Name
draw.text((x_labels, 235), 'Name', fill='#555555', font=font_label)
draw.text((x_labels, 258), 'RAHUL KUMAR', fill='#111111', font=font_value)

# Father Name
draw.text((x_labels, 310), "Father's Name", fill='#555555', font=font_label)
draw.text((x_labels, 333), 'SURESH KUMAR', fill='#111111', font=font_value)

# Date of Birth
draw.text((x_labels, 385), 'Date of Birth', fill='#555555', font=font_label)
draw.text((x_labels, 408), '15/08/1994', fill='#111111', font=font_value)

# Signature area on bottom right
draw.rectangle([(680, 475), (940, 555)], fill='#FFFFFF', outline='#999999', width=2)
draw.text((810, 515), 'Rahul Kumar', fill='#0A196F', font=font_sig, anchor='mm')
draw.text((810, 570), 'Signature', fill='#666666', font=font_label, anchor='mm')

# QR code placeholder or seal
draw.rectangle([(50, 425), (240, 555)], fill='#FFFFFF', outline='#999999', width=2)
draw.text((145, 490), 'QR CODE', fill='#888888', font=font_subtitle, anchor='mm')

# SPECIMEN WATERMARK
draw.text((W // 2, 605), 'SPECIMEN - FOR TESTING PURPOSE ONLY', fill='#C0392B', font=font_subtitle, anchor='mm')

out_path = os.path.join('sample-documents', 'pan_rahul_kumar.jpg')
card.save(out_path, quality=95)
print('Successfully generated', out_path)
