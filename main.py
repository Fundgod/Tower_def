import pygame
import random
import sys, os
from threading import Thread
from time import sleep


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
        self.sprite = self.load_sprite()

    def load_ways(self):
        ways = []
        path_to_roads = os.path.join(self.dir, 'ways')
        for road in os.listdir(path_to_roads):
            ways.append([])
            path_to_ways = os.path.join(path_to_roads, road)
            for way_file in os.listdir(path_to_ways):
                if '.csv' in way_file:
                    with open(os.path.join(path_to_ways, way_file), 'r') as f:
                        ways[-1].append([])
                        for line in f.readlines():
                            ways[-1][-1].append(tuple(map(float, line.rstrip().split(';'))))
                        ways[-1][-1] = tuple(ways[-1][-1])
        return ways

    def load_sprite(self):
        group = pygame.sprite.Group()
        sprite = pygame.sprite.Sprite(group)
        sprite.image = load_image(os.path.join(self.dir, 'image.png'))
        sprite.rect = pygame.Rect(0, 0, WIDTH, HEIGHT)
        return group

    def get_way(self, road_num):
        return random.choice(self.ways[road_num])

    def render(self, screen):
        self.sprite.draw(screen)


class Mob(pygame.sprite.Sprite):
    def __init__(self, way, width=60, height=60, velocity=1, group=None):
        super().__init__(group)
        self.way = way
        self.width = width
        self.height = height
        self.velocity = velocity
        self.pos = 0
        self.health = 100
        self.coords = list(self.way[self.pos])
        self.coords[0] -= self.width / 2
        self.coords[1] -= self.height / 2
        self.steps = [0, 0]
        self.rect = pygame.Rect(*self.way[self.pos], 10, 10)
        self.image = pygame.transform.scale(load_image('sprites\\lol.png', -1), (60, 60))

    def update(self):
        if self.health > 0:
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

                # Отрисовка полоски здоровья
                pygame.draw.rect(screen, 'red', (int(self.coords[0] + 15), int(self.coords[1]) - 10, 30, 5))
                pygame.draw.rect(screen, 'green', (int(self.coords[0] + 15), int(self.coords[1]) - 10, 30 * self.health // 100, 5))
            except IndexError:
                self.kill()
        else:
            self.kill()


class Game:
    def __init__(self):
        self.level = 1
        self.map = Map(self.level)
        self.mobs = pygame.sprite.Group()
        self.plants = pygame.sprite.Group()
        self.plants_data = self.load_plants()
        self.towers = pygame.sprite.Group()

    def start(self):
        self.mobs_spawn_thread = Thread(target=self.spawn_mobs, daemon=True)
        self.mobs_spawn_thread.start()

    def load_plants(self):
        plants_data = []
        plant_image = pygame.transform.scale(load_image('sprites/plant.png', -1), (50, 50))
        with open(os.path.join(self.map.dir, 'plants.csv'), 'r') as f:
            for line in f.readlines():
                plants_data.append(tuple(map(lambda coord: float(coord) - 25, line.rstrip().split(';'))))
                plant_sprite = pygame.sprite.Sprite(self.plants)
                plant_sprite.rect = pygame.Rect(*plants_data[-1], 40, 40)
                plant_sprite.image = plant_image
                plants_data[-1] = (plants_data[-1], plant_sprite)
        plants_data = dict(plants_data)
        return plants_data

    def spawn_mob(self, road_num):
        Mob(self.map.get_way(road_num), group=self.mobs)

    def spawn_mobs(self):
        for interval, road_num in ((1, 0), (2, 0), (3, 0), (1, 0), (2, 0), (3, 0), (1, 0), (2, 0), (3, 0)):
            sleep(interval)
            self.spawn_mob(road_num)

    def update(self):
        self.mobs.update()

    def render(self, screen):
        self.map.render(screen)
        self.mobs.draw(screen)
        self.plants.draw(screen)
        self.towers.draw(screen)


if __name__ == '__main__':
    pygame.init()
    SIZE = WIDTH, HEIGHT = 1920, 1080
    screen = pygame.display.set_mode(SIZE)
    game = Game()
    game.start()
    fps = 60
    time = pygame.time.Clock()
    running = True
    while running:
        time.tick(fps)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        screen.fill('black')
        game.update()
        game.render(screen)
        pygame.display.flip()
    pygame.quit()