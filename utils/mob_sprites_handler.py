from PIL import Image


im = Image.open('golem.jpg')
x, y = im.size
y -= 1
pixels = im.load()
start = None

fragments = []
for i in range(x):
    for j in range(y):
        if sum(pixels[i, j]) < 700:
            if start is None:
                start = i
            break
        else:
            pixels[i, j] = (255, 255, 255)
    else:
        if start is not None:
            fragments.append(im.crop((start, 0, i, y)))
            start = None

if start is not None:
    fragments.append(im.crop((start, 0, i, y)))

del fragments[3]

#for c, i in enumerate(fragments):
#    i.save(f'{c + 1}.png')

max_width = max([fragment.size[0] for fragment in fragments]) + 2
final_result = Image.new('RGB', (max_width * len(fragments), y), color=(255, 255, 255))
for i in range(len(fragments)):
    width = fragments[i].size[0]
    bias = (max_width - width) // 2
    updated_fragment = Image.new('RGB', (max_width, y), color=(255, 255, 255))
    updated_fragment.paste(fragments[i], (bias, 0))
    final_result.paste(updated_fragment, (i * max_width, 0))
print(f'width: {max_width}\nheight: {y}')
final_result.save('result.png')