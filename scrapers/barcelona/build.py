"""Build index.html (artifact) and /home/claude/films/index.html (GitHub Pages) from template + data."""
import re
ROOT = '/home/claude/cinema'
t = open(f'{ROOT}/template.html').read()
data = open(f'{ROOT}/data.json').read().replace('</', '<\\/')
page = t.replace('__DATA__', data)
open(f'{ROOT}/index.html', 'w').write(page)

META = '''<title>Arthouse Barcelona</title>
<meta name="description" content="Art-house, repertory and festival screenings across Barcelona's independent cinemas.">
<meta property="og:type" content="website">
<meta property="og:title" content="Arthouse Barcelona">
<meta property="og:description" content="Art-house, repertory and festival screenings across Barcelona's independent cinemas.">
<meta property="og:url" content="https://danielnaca.github.io/films/">
<meta property="og:image" content="https://danielnaca.github.io/films/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Arthouse Barcelona">
<meta name="twitter:description" content="Art-house, repertory and festival screenings across Barcelona's independent cinemas.">
<meta name="twitter:image" content="https://danielnaca.github.io/films/og.jpg">'''
h = page.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '', 1)
h = h.replace('<title>Arthouse Barcelona</title>', META, 1)
head = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
j = h.index('</style>') + 8
open('/home/claude/films/index.html', 'w').write(head + h[:j] + '\n</head>\n<body>\n' + h[j:] + '\n</body>\n</html>\n')
print('built')
