import pygame
import random
import sys, os


def load_image(name, colorkey=None):
    if not name:
        print(f"Файл с изображением '{name}' не найден")
        sys.exit()
    image = pygame.image.load(name)
    if colorkey is not None:
        image = image.convert()
        if colorkey == -1:
            colorkey = image.get_at((0, 0))
        image.set_colorkey(colorkey)
    else:
        image = image.convert_alpha()
    return image


class Map:
    def __init__(self, number):
        self.dir = f'map{number}'
        self.ways = self.load_ways()
        self.plants_sprites = pygame.sprite.Group()
        self.plants = self.load_plants()
        self.sprite = self.load_sprite()

    def load_ways(self):
        ways = []
        path = os.path.join(self.dir, 'ways')
        for file in os.listdir(path):
            if '.csv' in file:
                with open(os.path.join(path, file), 'r') as f:
                    ways.append([])
                    for line in f.readlines():
                        ways[-1].append(tuple(map(float, line.rstrip().split(';'))))
                    ways[-1] = tuple(ways[-1])
        return ways

    def load_plants(self):
        plants = []
        plant_image = pygame.transform.scale(load_image('sprites/plant.png', -1), (50, 50))
        with open(os.path.join(self.dir, 'plants.csv'), 'r') as f:
            for line in f.readlines():
                plants.append(tuple(map(float, line.rstrip().split(';'))))
                plant_sprite = pygame.sprite.Sprite(self.plants_sprites)
                plant_sprite.rect = pygame.Rect(*plants[-1], 40, 40)
                plant_sprite.image = plant_image
                plants[-1] = (plants[-1], plant_sprite)
        plants = tuple(plants)
        return plants

    def load_sprite(self):
        group = pygame.sprite.Group()
        sprite = pygame.sprite.Sprite(group)
        sprite.image = load_image(os.path.join(self.dir, 'image.png'))
        sprite.rect = pygame.Rect(0, 0, WIDTH, HEIGHT)
        return group

    def get_way(self):
        return random.choice(self.ways)

    def render(self, screen):
        self.sprite.draw(screen)
        self.plants_sprites.draw(screen)


class Mob(pygame.sprite.Sprite):
    def __init__(self, way, width=60, height=60, velocity=1, group=None):
        super().__init__(group)
        self.way = way
        self.width = width
        self.height = height
        self.velocity = velocity
        self.pos = 0
        self.coords = list(self.way[self.pos])
        self.coords[0] -= self.width / 2
        self.coords[1] -= self.height / 2
        self.steps = [0, 0]
        self.rect = pygame.Rect(*self.way[self.pos], 10, 10)
        self.image = pygame.transform.scale(load_image('lol.png', -1), (60, 60))

    def update(self):
        try:
            if self.steps[0] >= self.steps[1]:
                start_point = self.way[self.pos]
                self.pos += 1
                end_point = self.way[self.pos]
                d_x, d_y = end_point[0] - start_point[0], end_point[1] - start_point[1]
                self.steps = [0, (d_x ** 2 + d_y ** 2) ** .5 // self.velocity]
                self.x_velocity, self.y_velocity = d_x, d_y
            self.steps[0] += 1
            self.coords[0] += self.x_velocity / self.steps[1]
            self.coords[1] += self.y_velocity / self.steps[1]
            self.rect.x, self.rect.y = self.coords
        except IndexError:
            self.kill()


if __name__ == '__main__':
    c = 0
    pygame.init()
    SIZE = WIDTH, HEIGHT = 1920, 1080
    screen = pygame.display.set_mode(SIZE)
    map_ = Map(1)
    mobs = pygame.sprite.Group()
    Mob(map_.get_way(), group=mobs)
    fps = 60
    time = pygame.time.Clock()
    running = True
    while running:
        time.tick(fps)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        screen.fill('black')
        map_.render(screen)
        mobs.update()
        mobs.draw(screen)
        pygame.display.flip()
        if not c % 300:
            Mob(map_.get_way(), group=mobs)
        c += 1
    pygame.quit()