from math import sqrt


def contour():
    return [('M', 232, 256 - sqrt(176 ** 2 - 24 ** 2)), ('L', 232, 242), ('C', 232, 304, 114, 326, 80, 256)]


def svg(inverted=False):
    ink, background = ('#FFFFFF', '#000000') if inverted else ('#000000', '#FFFFFF')
    path = ' '.join(command + ' ' + ' '.join(f'{value:.3f}'.rstrip('0').rstrip('.') for value in values) for command, *values in contour())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Drill">
  <title>Drill</title>
  <rect width="512" height="512" fill="{background}"/>
  <g fill="none" stroke="{ink}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="256" cy="256" r="176"/>
    <path d="{path}"/>
    <path d="{path}" transform="rotate(180 256 256)"/>
  </g>
</svg>
'''
