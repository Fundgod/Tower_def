import pygame
import random
import sys
import os
import json
from threading import Thread
from functools import partial
from time import sleep
from constants import *


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


def load_animation(path_to_image, width, height):
    image = load_image(os.path.join(path_to_image))
    x, y = image.get_size()
    frames = []
    for i in range(y // height):
        for j in range(x // width):
            frame_location = (width * j, height * i)
            frame = image.subsurface(pygame.Rect(frame_location, (width, height)))
            frames.append(frame)
    return frames


def load_mob_animations():
    animations = {}
    root = 'mobs'
    for mob in os.listdir(root):
        mob_dir = os.path.join(root, mob)
        animations[mob] = {}
        with open(os.path.join(mob_dir, 'info.json'), 'r', encoding='utf-8') as info_file:
            info = json.load(info_file)
        for animation in ('move', 'attack', 'death'):
            animations[mob][animation] = load_animation(os.path.join(mob_dir, 'sprites', animation + '.png'),
                                                        info[animation]['width'],
                                                        info[animation]['height'])
    return animations


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
    def __init__(self, type, way, group):
        super().__init__(group)
        self.way = way
        self.load_info(type)

    def load_info(self, type):
        with open(os.path.join('mobs', type, 'info.json'), 'r', encoding='utf-8') as info_file:
            self.info = json.load(info_file)
        self.width, self.height = self.info['move']['width'], self.info['move']['height']
        self.velocity = self.info['velocity'] / fps
        self.animations = MOB_ANIMATIONS[type]
        self.animation = self.animations['move']
        self.animation_index = 0.
        self.animation_speed = self.info['move']['animation_speed']
        self.health_line_bias = tuple(self.info['health_line_bias'].values())
        self.pos = 0
        self.health = 100
        self.coords = list(self.way[self.pos])
        self.steps = [0, 0]
        self.rect = pygame.Rect(self.coords[0] - self.width / 2, self.coords[1] - self.height / 2, self.width, self.height)

    def update(self):
        if self.health > 0:
            if round(self.animation_index, 1).is_integer():
                self.image = self.animation[int(self.animation_index)]
            self.animation_index = (self.animation_index + self.animation_speed) % len(self.animation)
            # Отрисовка полоски здоровья
            pygame.draw.rect(screen, 'red',
                             (
                                 int(self.coords[0] - self.width / 2 + self.health_line_bias[0]),
                                 int(self.coords[1]) - self.height / 2 - self.health_line_bias[1],
                                 30,
                                 5
                             ))
            pygame.draw.rect(screen, 'green',
                             (
                                 int(self.coords[0] - self.width / 2 + self.health_line_bias[0]),
                                 int(self.coords[1]) - self.height / 2 - self.health_line_bias[1],
                                 30 * self.health // 100,
                                 5
                             ))
            try:
                if self.steps[0] >= self.steps[1]:
                    start_point = tuple(map(lambda coord: coord + random.randint(-3, 3), self.way[self.pos]))
                    self.pos += 1
                    end_point = tuple(map(lambda coord: coord + random.randint(-3, 3), self.way[self.pos]))
                    d_x, d_y = end_point[0] - start_point[0], end_point[1] - start_point[1]
                    self.steps = [0, (d_x ** 2 + d_y ** 2) ** .5 // self.velocity]
                    self.x_velocity, self.y_velocity = d_x, d_y
                self.steps[0] += 1
                self.coords[0] += self.x_velocity / self.steps[1]
                self.coords[1] += self.y_velocity / self.steps[1]
                self.rect.x, self.rect.y = self.coords[0] - self.width / 2, self.coords[1] - self.height / 2
            except IndexError:
                self.attack()
        else:
            self.kill()

    def attack(self):
        attack_animation = self.animations['attack']
        if self.animation != attack_animation:
            self.animation = attack_animation
            self.animation_speed = self.info['attack']['animation_speed']
            self.animation_index = 0 - self.animation_speed
            self.width, self.height = self.info['attack']['width'], self.info['attack']['height']

    def kill(self):
        def new_update(self):
            try:
                if round(self.animation_index, 1).is_integer():
                    self.image = self.animation[int(self.animation_index)]
                self.animation_index += self.animation_speed
            except IndexError:
                super().kill()

        self.animation = self.animations['death']
        self.animation_index = 0.
        self.animation_speed = self.info['death']['animation_speed']
        self.width, self.height = self.info['death']['width'], self.info['death']['height']
        self.update = partial(new_update, self)


class Button(pygame.sprite.Sprite):
    def __init__(self, coords, filename, group=None):
        super().__init__(group)
        self.rect = pygame.Rect(*coords)
        self.image = load_image(os.path.join('sprites', 'buttons', filename), -1)


class AttackTower(pygame.sprite.Sprite):
    def __init__(self, group=None):
        super().__init__(group)
        self.long_range = 1
        self.tower_level = 1
        self.health = 1000
        # self.image = pygame.transform.scale(load_image())

    def attack(self):
        Bullet()

    def update(self):
        if self.health > 0:
            pygame.draw.rect(screen, 'red', (int(self.coords[0] + 15), int(self.coords[1]) - 10, 30, 5))
            pygame.draw.rect(screen, 'green',(int(self.coords[0] + 15), int(self.coords[1]) - 10, 30 * self.health // 100, 5))
        else:
            self.kill()


class Bullet(pygame.sprite.Sprite):
    pass


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.level = 1
        self.map = Map(self.level)
        self.mobs = {
            MASK: pygame.sprite.Group(),
            SKILLET: pygame.sprite.Group(),
            STONE_GOLEM: pygame.sprite.Group(),
            BOAR_WARRIOR: pygame.sprite.Group(),
            HORNY_DOG: pygame.sprite.Group(),
            CRYSTAL_GOLEM: pygame.sprite.Group()
        }
        self.plants = pygame.sprite.Group()
        self.plants_data = self.load_plants()
        self.towers = pygame.sprite.Group()
        self.buttons = pygame.sprite.Group()
        self.pause_button = Button((1800, 30, 80, 80), 'pause.png', self.buttons)
        self.on_pause = False
        self.mob_query = []

    def begin(self):
        # Инициализация фоновой картинки и кнопок
        background = load_image(os.path.join('sprites', 'background_image.png'))
        buttons = pygame.sprite.Group()
        single_player_button = Button((800, 500, 350, 90), 'start_single_game.png', buttons)
        online_game_button = Button((800, 650, 350, 90), 'start_online_game.png', buttons)
        exit_button = Button((800, 800, 350, 90), 'exit.png', buttons)
        self.screen.blit(background, (0, 0))
        buttons.draw(self.screen)
        # Ожидание юзер инпута
        while True:
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    click = pygame.Rect(*event.pos, 1, 1)
                    if click.colliderect(single_player_button):
                        self.start()
                        return
                    elif click.colliderect(online_game_button):
                        print('It must start online mode')
                    elif click.colliderect(exit_button):
                        self.quit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_END:
                        self.quit()
            pygame.display.flip()

    def start(self):
        self.mobs_spawn_thread = Thread(target=self.spawn_mobs, daemon=True)
        self.mobs_spawn_thread.start()

    def load_plants(self):
        plants_data = []
        plant_image = load_image('sprites/plant.png', -1)
        with open(os.path.join(self.map.dir, 'plants.csv'), 'r') as f:
            for line in f.readlines():
                plants_data.append(tuple(map(lambda coord: float(coord) - 125, line.rstrip().split(';'))))
                plant_sprite = pygame.sprite.Sprite(self.plants)
                plant_sprite.rect = pygame.Rect(*plants_data[-1], 40, 40)
                plant_sprite.image = plant_image
                plants_data[-1] = (plants_data[-1], plant_sprite)
        plants_data = dict(plants_data)
        return plants_data

    def spawn_mobs(self):
        for interval, road_num, mob_type in MOBS[self.level]:
            little_intervals_count = interval / 0.1
            little_intervals_counter = 0
            while little_intervals_counter != little_intervals_count:
                sleep(0.1)
                if not self.on_pause:
                    little_intervals_counter += 1
            self.mob_query.append((mob_type, road_num))

    def on_click(self, pos):
        click = pygame.Rect(*pos, 1, 1)
        if click.colliderect(self.pause_button):
            self.pause()

    def on_tap(self, key):
        if key == pygame.K_TAB:
            self.pause()
        elif key == pygame.K_END:
            self.quit()

    def pause(self):
        self.on_pause = True
        # Инициализация меню паузы
        menu = pygame.sprite.Group()
        menu_table = pygame.sprite.Sprite(menu)
        menu_table.rect = pygame.Rect(660, 190, 600, 700)
        menu_table.image = load_image(os.path.join('sprites', 'menu.png'), -1)
        continue_button = Button((770, 300, 350, 90), 'continue.png', menu)
        music_slider = Button((800, 483, 20, 40), 'slider.png', menu)
        sounds_slider = Button((800, 619, 20, 40), 'slider.png', menu)
        exit_button = Button((770, 680, 350, 90), 'exit.png', menu)
        menu.draw(self.screen)
        changing_music_volume = False
        changing_sounds_volume = False
        volume_changing_bias = 0
        # Обработка взаимодействия пользователя с меню паузы
        while True:
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    click = pygame.Rect(*event.pos, 1, 1)
                    if click.colliderect(continue_button):
                        self.on_pause = False
                        return
                    elif click.colliderect(music_slider):
                        changing_music_volume = True
                        volume_changing_bias = event.pos[0] - music_slider.rect.x
                        print(volume_changing_bias)
                    elif click.colliderect(sounds_slider):
                        changing_sounds_volume = True
                        volume_changing_bias = event.pos[0] - sounds_slider.rect.x
                        print(volume_changing_bias)
                    elif click.colliderect(exit_button):
                        self.quit()
                elif event.type == pygame.MOUSEMOTION:
                    if changing_music_volume:
                        cursor_x_coord = event.pos[0] - volume_changing_bias
                        if 800 > cursor_x_coord:
                            next_pos = 800
                        elif 1115 < cursor_x_coord:
                            next_pos = 1115
                        else:
                            next_pos = cursor_x_coord
                        music_slider.rect.x = next_pos
                        menu.draw(self.screen)
                    elif changing_sounds_volume:
                        cursor_x_coord = event.pos[0] - volume_changing_bias
                        if 800 > cursor_x_coord:
                            next_pos = 800
                        elif 1115 < cursor_x_coord:
                            next_pos = 1115
                        else:
                            next_pos = cursor_x_coord
                        sounds_slider.rect.x = next_pos
                        menu.draw(self.screen)
                elif event.type == pygame.MOUSEBUTTONUP:
                    changing_music_volume = False
                    changing_sounds_volume = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        self.on_pause = False
                        return
                    elif event.key == pygame.K_END:
                        self.quit()
                pygame.display.flip()

    def update_and_render(self):
        if self.mob_query:
            mob_type, road_num = self.mob_query.pop(-1)
            Mob(mob_type, self.map.get_way(road_num), self.mobs[mob_type])
        self.map.render(self.screen)
        for mob_type in (HORNY_DOG, BOAR_WARRIOR, SKILLET, CRYSTAL_GOLEM, STONE_GOLEM, MASK):
            self.mobs[mob_type].update()
            self.mobs[mob_type].draw(self.screen)
        self.plants.draw(self.screen)
        self.towers.draw(self.screen)
        self.buttons.draw(self.screen)

    def quit(self):
        pygame.quit()
        sys.exit(0)


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    MOB_ANIMATIONS = load_mob_animations()
    game = Game(screen)
    game.begin()
    fps = 60
    time = pygame.time.Clock()
    running = True
    while running:
        time.tick(fps)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                game.on_click(event.pos)
            if event.type == pygame.KEYDOWN:
                game.on_tap(event.key)
        screen.fill('black')
        game.update_and_render()
        pygame.display.flip()