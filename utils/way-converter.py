from PIL import Image


def conv_way(filename):
    im = Image.open(filename + '.png')
    pixels = im.load()
    x, y = im.size

    x_axis = range(x - 1, -1, -1)
    y_axis = range(y)

    way = []
    for i in x_axis:
        for j in y_axis:
            if sum(pixels[i, j]) < 700:
                way.append((i, j))

    for i in range(len(way) - 1, 0, -1):
        if abs(way[i][0] - way[i - 1][0]) <= 1 and abs(way[i][1] - way[i - 1][1]) <= 1:
            del way[i]

    with open(filename + '.csv', 'w') as f:
        f.write('\n'.join([f'{i};{j}' for i, j in way]))


conv_way('map1/ways/way2')