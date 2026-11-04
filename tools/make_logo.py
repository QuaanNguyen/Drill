import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drill.logo import contour, svg


def preview(path, inverted):
    from PIL import Image, ImageDraw
    scale = 4
    image = Image.new('RGB', (512 * scale, 512 * scale), 'black' if inverted else 'white')
    draw = ImageDraw.Draw(image)
    ink = 'white' if inverted else 'black'
    draw.ellipse(tuple(value * scale for value in (73, 73, 439, 439)), outline=ink, width=14 * scale)
    points = []
    current = None
    for command, *values in contour():
        if command == 'M':
            current = tuple(values)
            points.append(current)
        elif command == 'L':
            current = tuple(values)
            points.append(current)
        elif command == 'C':
            start = current
            for step in range(1, 161):
                t = step / 160
                u = 1 - t
                points.append(tuple(u ** 3 * start[axis] + 3 * u ** 2 * t * values[axis] + 3 * u * t ** 2 * values[axis + 2] + t ** 3 * values[axis + 4] for axis in (0, 1)))
            current = tuple(values[-2:])
    for curve in (points, [(512 - x, 512 - y) for x, y in points]):
        scaled = [(round(x * scale), round(y * scale)) for x, y in curve]
        draw.line(scaled, fill=ink, width=14 * scale, joint='curve')
        for x, y in (scaled[0], scaled[-1]):
            radius = 7 * scale
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=ink)
    image.resize((512, 512), Image.Resampling.LANCZOS).save(path)


def banner(output, with_preview):
    mark = '\n'.join(svg().splitlines()[2:-1])
    dots = ''.join(f'<rect x="{x}" y="{y}" width="2" height="2"/>' for x in range(1370, 1530, 16) for y in range(320, 400, 16) if (x + y) % 3 == 0)
    document = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 480" role="img" aria-label="Drill">
  <title>Drill</title>
  <rect width="1600" height="480" fill="#FFFFFF"/>
  <g transform="translate(48 48) scale(0.75)">{mark}</g>
  <text x="530" y="290" font-family="Menlo,monospace" font-size="150" font-weight="700" letter-spacing="14" fill="#000000">DRILL</text>
  <g fill="#000000">{dots}</g>
</svg>
'''
    (output / 'banner.svg').write_text(document)
    if with_preview:
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('RGB', (1600, 480), 'white')
        image.paste(Image.open(output / 'logo.png').resize((384, 384), Image.Resampling.LANCZOS), (48, 48))
        draw = ImageDraw.Draw(image)
        face = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 150, index=1)
        x = 530
        for letter in 'DRILL':
            draw.text((x, 290), letter, font=face, fill='black', anchor='ls')
            x += draw.textlength(letter, font=face) + 14
        for column in range(1370, 1530, 16):
            for row in range(320, 400, 16):
                if (column + row) % 3 == 0:
                    draw.rectangle((column, row, column + 1, row + 1), fill='black')
        image.save(output / 'banner.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'assets')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--banner', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for inverted, name in ((False, 'logo'), (True, 'logo-reversed')):
        (args.output / f'{name}.svg').write_text(svg(inverted))
        if args.preview:
            preview(args.output / f'{name}.png', inverted)
    if args.banner:
        banner(args.output, args.preview)


if __name__ == '__main__':
    main()
