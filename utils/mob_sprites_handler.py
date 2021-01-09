from PIL import Image


im = Image.open('move.png')
x, y = im.size
y -= 1
pixels = im.load()
start = None

fragments = []
for i in range(x):
    for j in range(y):
        if sum(pixels[i, j]) < 670:
            if start is None:
                start = i
            break
        else:
            pass#pixels[i, j] = (255, 255, 255)
    else:
        if start is not None:
            fragments.append(im.crop((start, 0, i, y)))
            start = None

if start is not None:
    fragments.append(im.crop((start, 0, i, y)))

fragments = [fragment for fragment in fragments if fragment.size[0] > 10]
print('frames count:', len(fragments))

fragments = fragments[::-1]

#for i in range(len(fragments) - 1, -1, -1):
#    print(i)
#    fragment = fragments[i]
#    pixels = fragment.load()
#    pixels_list = []
#    print(fragment.size)
#    for i in range(fragment.size[0]):
#        for j in range(fragment.size[1]):
#            pixels_list.append(pixels[i, j])
#    if all(map(lambda x: sum(x) > 600 and x[0] == x[1] == x[2], pixels_list)):
#        del fragments[i]

#for c, i in enumerate(fragments):
#    i.save(f'{c + 1}.png')

max_width = max([fragment.size[0] for fragment in fragments])
final_result = Image.new('RGB', (max_width * len(fragments), y), color=(255, 255, 255))
for i in range(len(fragments)):
    width = fragments[i].size[0]
    bias = (max_width - width) // 2
    updated_fragment = Image.new('RGB', (max_width, y), color=(255, 255, 255))
    updated_fragment.paste(fragments[i], (bias, 0))
    final_result.paste(updated_fragment, (i * max_width, 0))
print(f'width: {max_width}\nheight: {y}')
final_result.save('result.png')