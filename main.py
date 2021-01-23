import pygame
import random
import sys
import os
import json
import math
import sqlite3
from threading import Thread
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


def load_bullets_sprites():
    bullets_sprites = {}
    path = os.path.join('sprites', 'bullets')
    for bullet, width, height in (('arrow', 25, 25), ('shell', 25, 25)):
        bullets_sprites[bullet] = load_animation(os.path.join(path, bullet + '.png'), width, height)
    return bullets_sprites


def draw_health_indicator(x, y, health, max_health, indicator_width, indicator_height, screen):
    pygame.draw.rect(screen, 'red', (x, y, indicator_width, indicator_height))
    pygame.draw.rect(screen, 'green', (x, y, indicator_width * health / max_health, indicator_height))


class Map:
    def __init__(self, index):
        self.dir = f'map{index}'
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

    def get_way(self, road_index, way_index=None):
        """Возвращает путь по заданным индексам дороги и пути.
        Если индекс пути не задан, возвращается случайный путь и его индекс"""
        if way_index is None:
            road = self.ways[road_index]
            way_index = random.randint(0, len(road) - 1)
            return road[way_index], way_index
        return self.ways[road_index][way_index]

    def render(self, screen):
        self.sprite.draw(screen)


class Mob(pygame.sprite.Sprite):
    def __init__(self, group, way, type, road_index, way_index, x=None, y=None, pos=0, state='move',
                 animation_index=0., passed_steps=0, total_steps=0, health=None, tagged=False):
        super().__init__(group)
        self.type = type
        self.road_index = road_index
        self.way_index = way_index
        self.way = way
        self.state = state
        self.load_info(self.type)
        self.pos = pos
        self.animations = MOB_ANIMATIONS[self.type]
        self.animation = self.animations[state]
        self.animation_index = animation_index
        self.steps = [passed_steps, total_steps]
        self.tagged = tagged
        if x is None:
            self.coords = list(self.way[self.pos])
        else:
            self.coords = [x, y]
            self.health = health
            self.image = self.animation[int(self.animation_index)]
            try:
                if passed_steps < total_steps:
                    start_point = self.way[self.pos]
                    end_point = self.way[self.pos + 1]
                    d_x, d_y = end_point[0] - start_point[0], end_point[1] - start_point[1]
                    self.x_velocity = d_x / self.steps[1]
                    self.y_velocity = d_y / self.steps[1]
            except IndexError:  # Значит, моб дошёл до конца пути
                self.x_velocity = 0
                self.y_velocity = 0
        self.rect = pygame.Rect(
            self.coords[0] - self.width / 2,
            self.coords[1] - self.height / 2,
            self.width,
            self.height
        )

    def load_info(self, type):
        with open(os.path.join('mobs', type, 'info.json'), 'r', encoding='utf-8') as info_file:
            self.info = json.load(info_file)
        self.width, self.height = self.info[self.state]['width'], self.info[self.state]['height']
        self.velocity = self.info['velocity'] / FPS
        self.health = self.max_health = self.info['health']
        self.damage = self.info['damage']
        self.cost = self.info['cost']
        self.animation_speed = self.info[self.state]['animation_speed']
        self.animation_length = self.info[self.state]['animation_length']
        self.health_line_bias = tuple(self.info['health_line_bias'].values())

    def get_position(self, time):
        """Возвращает координату, в которой окажется моб через заданное кол-во обновлений экрана"""
        # time - кол-во обновлений экрана
        index = self.pos
        steps = self.steps[1] - self.steps[0]
        way_len = len(self.way)
        while index < way_len - 1:
            if steps < time:
                time -= steps
            else:
                if index > self.pos:
                    way_point_1 = self.way[index - 1]
                else:
                    way_point_1 = self.coords
                way_point_2 = self.way[index]
                d_x, d_y = way_point_2[0] - way_point_1[0], way_point_2[1] - way_point_1[1]
                return (way_point_1[0] + d_x / steps * time,
                        way_point_1[1] + d_y / steps * time)
            start_point = self.way[index]
            index += 1
            end_point = self.way[index]
            d_x, d_y = end_point[0] - start_point[0], end_point[1] - start_point[1]
            steps = math.hypot(d_x, d_y) / self.velocity
        else:
            return self.way[-1]

    def update(self):
        if round(self.animation_index, 1).is_integer():
            self.image = self.animation[int(self.animation_index)]
        self.animation_index = (self.animation_index + self.animation_speed) % self.animation_length
        if self.health > 0:
            # Отрисовка полоски здоровья
            draw_health_indicator(int(self.coords[0] - self.width / 2 + self.health_line_bias[0]),
                                  int(self.coords[1] - self.height / 2 - self.health_line_bias[1]),
                                  self.health,
                                  self.max_health,
                                  30,
                                  5,
                                  screen)
            try:
                if self.steps[0] >= self.steps[1]:
                    start_point = self.way[self.pos]
                    self.pos += 1
                    end_point = self.way[self.pos]
                    d_x, d_y = end_point[0] - start_point[0], end_point[1] - start_point[1]
                    self.steps = [0, math.hypot(d_x, d_y) // self.velocity]
                    self.x_velocity = d_x / self.steps[1]
                    self.y_velocity = d_y / self.steps[1]
                self.steps[0] += 1
                self.coords[0] += self.x_velocity
                self.coords[1] += self.y_velocity
                self.rect.x, self.rect.y = self.coords[0] - self.width / 2, self.coords[1] - self.height / 2
            except IndexError:
                self.attack(MainTower)
        elif self.state != 'death':
            self.kill()
        elif round(self.animation_index) == self.animation_length:
            super().kill()

    def attack(self, target):
        attack_animation = self.animations['attack']
        if int(self.animation_index) == self.animation_length - 1:
            target.hit(self.damage)
        if self.state != 'attack':
            self.state = 'attack'
            self.animation = attack_animation
            self.animation_speed = self.info['attack']['animation_speed']
            self.animation_length = self.info['attack']['animation_length']
            self.animation_index = 0 - self.animation_speed
            self.width, self.height = self.info['attack']['width'], self.info['attack']['height']

    def hit(self, damage):
        self.health -= damage

    def kill(self):
        self.state = 'death'
        Game.currency += self.cost
        self.animation = self.animations['death']
        self.animation_index = 0.
        self.animation_speed = self.info['death']['animation_speed']
        self.animation_length = self.info['death']['animation_length']
        self.width, self.height = self.info['death']['width'], self.info['death']['height']


class BowTower(pygame.sprite.Sprite):
    cost = 50

    def __init__(self, group, coords, moblist, bullets_group, reloading=0, animation_index=0):
        super().__init__(group)
        self.coords = (coords[0] + 125, coords[1] - 25)
        self.moblist = moblist
        self.bullets_group = bullets_group
        self.reloading = reloading
        self.animation_index = animation_index
        self.time_to_reload = 100
        self.width = 250
        self.height = 250
        self.shooting_range = 600
        self.damage = 10
        self.image = load_image(os.path.join('sprites', 'towers', 'bow.png'), -1)
        self.rect = pygame.Rect(self.coords[0] - self.width // 2,
                                self.coords[1] - self.height // 2 + 100,
                                self.width,
                                self.height)

    def update(self):
        if not self.reloading:
            for mob in sorted(self.moblist, key=lambda mob_: not mob_.tagged):
                distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                if distance <= self.shooting_range and mob.state != 'death':
                    Bullet(self.bullets_group, self.coords, self.damage, 'arrow', distance, mob)
                    self.reloading = self.time_to_reload
                    return
        else:
            self.reloading -= 1

    def __str__(self):
        return 'bow'


class GunTower(pygame.sprite.Sprite):
    cost = 100

    def __str__(self):
        return 'gun'


class RocketTower(pygame.sprite.Sprite):
    cost = 150

    def __str__(self):
        return 'rocket'


class MainTower(pygame.sprite.Sprite):
    health = 1000
    full_hp = 1000

    def __init__(self, bullets_group, moblist,  group):
        super().__init__(group)
        self.rect = pygame.Rect(20, 670, 10, 10)
        self.coords = (20, 670)
        self.image = MAINTOWER_IMAGE
        self.moblist = moblist
        self.bullets_group = bullets_group
        self.reloading = 0
        self.time_to_reload = 60
        self.shooting_range = 600
        self.damage = 10

    def update(self):
        if self.health > 0:
            pygame.draw.rect(screen, 'blue', (int(self.coords[0] + 95), int(self.coords[1]) + 25, 110, 20))
            draw_health_indicator(int(self.coords[0] + 100), int(self.coords[1]) + 30, self.health, self.full_hp, 100, 10, screen)
            #pygame.draw.rect(screen, 'red', (int(self.coords[0] + 15), int(self.coords[1]) - 10, 30 * self.full_hp // 100, 5))
            #pygame.draw.rect(screen, 'green', (int(self.coords[0] + 15), int(self.coords[1]) - 10, 30 * self.health // 100, 5))
        else:
            self.kill()
            # здесь по идее должна поменяться картинка, а не башня должа испариться, но картинки ещё нет

        if not self.reloading:
            for mob in self.moblist:
                distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                if distance <= self.shooting_range and mob.state != 'death':
                    coords = (self.coords[0] + 135, self.coords[1] + 70)
                    Bullet(self.bullets_group, coords, self.damage, 'arrow', distance, mob)
                    self.reloading = self.time_to_reload
                    return
        else:
            self.reloading -= 1

    def hit(damage):
        MainTower.health -= damage


class Bullet(pygame.sprite.Sprite):
    def __init__(self, group, start_coords, damage, type, distance_to_target, mob,
                 end_coords=None, velocity=None, angle=None):
        super().__init__(group)
        self.type = type
        self.coords = list(start_coords)
        self.damage = damage
        self.rect = pygame.Rect(self.coords[0] - 5, self.coords[1] - 5, 10, 10)
        self.distance_to_target = distance_to_target
        self.mob = mob
        if end_coords:                    # Если конечную точку дали сразу, то снаряд просто летит туда, а если нет,
            self.end_coords = end_coords  # то конечная точка вычисляется исходя из движения моба-цели
            self.velocity = velocity
            self.angle = angle
            # Путь до цели будет разбит на шаги.
            # steps_to_target - количество шагов до цели, steps - количество пройденных шагов
            # angle - угол, под которым летит стрела
            self.steps = 0
            self.steps_to_target = distance_to_target / self.velocity
            self.step = (self.velocity * math.cos(self.angle),
                         self.velocity * -math.sin(self.angle))
        else:
            self.velocity = 600 / FPS
            self.steps, self.steps_to_target = 0, None
            self.calculate_trajectory(mob, distance_to_target)
        self.image = pygame.transform.rotate(BULLETS_SPRITES[self.type][0], math.degrees(self.angle))

    def calculate_trajectory(self, mob, distance_to_target):
        """Рассчитывает маршрут полёта стрелы до противника и угол, под которым полетит стрела"""
        flight_time = distance_to_target / self.velocity
        self.end_coords = mob.get_position(flight_time)
        d_x, d_y = self.end_coords[0] - self.coords[0], self.end_coords[1] - self.coords[1]
        distance = math.hypot(d_x, d_y)
        self.velocity = distance / flight_time
        self.step = (d_x / distance * self.velocity,
                     d_y / distance * self.velocity)
        self.steps_to_target = distance / self.velocity
        self.angle = -math.atan(d_y / d_x)
        if d_x < 0:
            self.angle += math.pi

    def update(self):
        if self.steps < self.steps_to_target:
            self.coords[0] += self.step[0]
            self.coords[1] += self.step[1]
            self.rect.x = self.coords[0] - 5
            self.rect.y = self.coords[1] - 5
            self.steps += 1
        else:
            self.mob.hit(self.damage)
            self.kill()


class AddTowerMenu(pygame.sprite.Sprite):
    width = 400
    height = 180

    def __init__(self, plant, moblist, currency, group_for_towers, group_for_bullets, group):
        super().__init__(group)
        self.coords = plant.rect.x, plant.rect.y
        self.plant = plant
        self.moblist = moblist
        self.group_for_towers = group_for_towers
        self.group_for_bullets = group_for_bullets
        self.currency = currency
        self.image = ADD_TOWER_MENU_IMAGE
        self.width, self.height = AddTowerMenu.width, AddTowerMenu.height
        self.rect = pygame.Rect(self.coords[0] - 70,
                                self.coords[1] - 100,
                                self.width,
                                self.height)
        self.buttons = pygame.sprite.Group()
        self.bow_tower_button = Button(
            (self.coords[0] - 5, self.coords[1] - 60, 80, 80),
            'bow_tower_icon.png',
            self.buttons
        )
        self.cost1 = SMALL_FONT.render(str(BowTower.cost), True, (245, 189, 31))
        self.gun_tower_button = Button(
            (self.coords[0] + 95, self.coords[1] - 60, 80, 80),
            'gun_tower_icon.png',
            self.buttons
        )
        self.cost2 = SMALL_FONT.render(str(GunTower.cost), True, (245, 189, 31))
        self.rocket_tower_button = Button(
            (self.coords[0] + 195, self.coords[1] - 60, 80, 80),
            'rocket_tower_icon.png',
            self.buttons
        )
        self.cost3 = SMALL_FONT.render(str(RocketTower.cost), True, (245, 189, 31))

    def check_click(self, click):
        if click.colliderect(self.bow_tower_button):
            if self.currency >= BowTower.cost:
                self.spawn_tower(BowTower)
        elif click.colliderect(self.gun_tower_button):
            if self.currency >= BowTower.cost:
                self.spawn_tower(BowTower)
        elif click.colliderect(self.rocket_tower_button):
            if self.currency >= BowTower.cost:
                self.spawn_tower(BowTower)

    def spawn_tower(self, tower):
        tower(self.group_for_towers, self.coords, self.moblist, self.group_for_bullets)
        Game.currency -= tower.cost
        self.plant.free = False
        self.plant.kill()

    def draw_buttons(self, surface):
        self.buttons.draw(surface)
        costs_height = self.coords[1] + 20
        surface.blit(self.cost1, (self.coords[0] + 15, costs_height))
        surface.blit(self.cost2, (self.coords[0] + 105, costs_height))
        surface.blit(self.cost3, (self.coords[0] + 205, costs_height))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 45, costs_height))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 150, costs_height))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 250, costs_height))


class Button(pygame.sprite.Sprite):
    def __init__(self, rect, filename, group=None):
        super().__init__(group)
        self.rect = pygame.Rect(*rect)
        self.image = load_image(os.path.join('sprites', 'buttons', filename))


class MobMark(pygame.sprite.Group):
    """Класс крестика, который появляется на экране если кликнуть по мобу"""

    def __init__(self):
        super().__init__()
        self.image = MOB_MARK_SPRITE
        self.sprite = pygame.sprite.Sprite(self)
        self.sprite.rect = pygame.Rect(0, 0, 60, 60)
        self.size = 60
        self.exist = False

    def place(self, x, y):
        self.sprite.rect.x = x - 30
        self.sprite.rect.y = y - 30
        self.sprite.image = self.image
        self.size = 60
        self.exist = True

    def update_and_render(self, surface):
        if self.exist:
            self.sprite.image = pygame.transform.scale(self.image, (self.size, self.size))
            self.draw(surface)
            self.size -= 2
            self.sprite.rect.x += 1
            self.sprite.rect.y += 1
            if self.size <= 0:
                self.exist = False


class Game:
    currency = 100

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
        self.plants = self.load_plants()
        self.towers = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.buttons = pygame.sprite.Group()
        self.main_tower = pygame.sprite.Group()
        self.add_tower_menus = pygame.sprite.Group()
        self.pause_button = Button((1800, 30, 80, 80), 'pause.png', self.buttons)
        self.on_pause = False
        self.mob_query = []
        self.moblist = []
        self.mt = MainTower(self.bullets, self.moblist, self.main_tower)
        self.tagged_mob = None  # Помеченный моб - тот, в которого в первую очередь стреляют башни
        self.mob_mark = MobMark()  # Крестик, которым можно помечать мобов
        self.time_in_game = 0

    def load_game_data(self, save_slot_id):
        con = sqlite3.connect(os.path.join('data', 'save_slots_db.sqlite3'))
        cur = con.cursor()
        main_data = cur.execute('''SELECT main_tower_hp, level, play_time, currency FROM slots 
                                   WHERE id = ?''', (save_slot_id,)).fetchone()
        if main_data and all(map(lambda v: v is not None, main_data)):  # Если в этом слоте лежат данные
            MainTower.health = main_data[0]
            self.level = main_data[1]
            self.time_in_game += main_data[2]
            Game.currency = main_data[3]
            towers_data = cur.execute('''SELECT * FROM towers
                                         WHERE slot_id = ?''', (save_slot_id,)).fetchall()
            towers = {'bow': BowTower, 'gun': GunTower, 'rocket': RocketTower}

            for _, x, y, reloading, tower_type, animation_index in towers_data:
                tower = towers[tower_type]
                x -= 125
                y += 25
                tower(self.towers, (x, y), self.moblist, self.bullets, reloading, animation_index)
                for plant in self.plants:
                    if plant.rect.x == x and plant.rect.y == y:
                        break
                plant.free = False
                plant.kill()

            mobs_data = cur.execute('''SELECT * FROM mobs
                                       WHERE slot_id = ?''', (save_slot_id,)).fetchall()
            for mob_data in mobs_data:
                mob = Mob(self.mobs[mob_data[1]], self.map.get_way(*mob_data[2:4]), *mob_data[1:])
                self.moblist.append(mob)

            bullets_data = cur.execute('''SELECT * FROM bullets
                                          WHERE slot_id = ?''', (save_slot_id,)).fetchall()
            for _, x, y, angle, end_x, end_y, bullet_type, velocity, damage, mob_index in bullets_data:
                distance = math.hypot(end_x - x, end_y - y)
                Bullet(self.bullets, (x, y), damage, bullet_type, distance, self.moblist[mob_index],
                       end_coords=(end_x, end_y), velocity=velocity, angle=angle)
            con.close()
            return main_data[2]
        return 0

    def load_plants(self):
        plants = pygame.sprite.Group()
        plant_image = load_image('sprites/plant.png')
        with open(os.path.join(self.map.dir, 'plants.csv'), 'r') as f:
            for line in f.readlines():
                plant_coords = tuple(map(lambda coord: float(coord) - 125, line.rstrip().split(';')))
                plant_sprite = pygame.sprite.Sprite(plants)
                plant_sprite.rect = pygame.Rect(*plant_coords, 250, 250)
                plant_sprite.image = plant_image
                plant_sprite.free = True
        return plants

    def begin(self):
        # Инициализация фоновой картинки и главного меню
        background = load_image(os.path.join('sprites', 'background_image.png'))
        menu = pygame.sprite.Group()
        menu_table = pygame.sprite.Sprite(menu)
        menu_table.rect = pygame.Rect(700, 400, 600, 450)
        menu_table.image = load_image(os.path.join('sprites', 'main_menu.png'), -1)
        single_player_button = Button((800, 500, 350, 90), 'start_single_game.png', menu)
        exit_button = Button((800, 650, 350, 90), 'exit.png', menu)
        state = 'main_menu'
        save_slot_buttons = []
        self.screen.blit(background, (0, 0))
        menu.draw(self.screen)
        # Ожидание юзер инпута
        while True:
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    click = pygame.Rect(*event.pos, 1, 1)
                    if state == 'main_menu':
                        if click.colliderect(single_player_button):
                            state = 'choose_save_slot_menu'
                            single_player_button.kill()
                            exit_button.kill()
                            menu_table.rect.y -= 150
                            menu_table.image = load_image(os.path.join('sprites', 'save_slots_menu.png'))
                            for save_slot in range(5):
                                save_slot_buttons.append(Button(
                                    (800, 400 + save_slot * 100, 340, 90),
                                    f'save_slot_{save_slot + 1}.png',
                                    menu
                                ))
                            self.screen.blit(background, (0, 0))
                            menu.draw(self.screen)
                            pygame.display.flip()
                        elif click.colliderect(exit_button):
                            self.quit()
                    else:
                        for index, button in enumerate(save_slot_buttons):
                            if click.colliderect(button.rect):
                                self.start(index + 1)
                                return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_END:
                        self.quit()
                elif event.type == pygame.QUIT:
                    self.quit()
            pygame.display.flip()

    def start(self, save_slot):
        self.save_slot = save_slot
        spawner_start = self.load_game_data(save_slot)
        self.mobs_spawn_thread = Thread(target=self.spawn_mobs, args=[spawner_start], daemon=True)
        self.mobs_spawn_thread.start()

    def spawn_mobs(self, start):
        spawn_list = SPAWN_DATA[self.level]
        for index, (interval, road_index, mob_type) in enumerate(spawn_list):
            if interval <= start:
                start -= interval
            else:
                spawn_list = list(spawn_list[index:])
                spawn_list[0] = (interval - start, road_index, mob_type)
                spawn_list = tuple(spawn_list)
                break
        else:
            spawn_list = []
        for interval, road_index, mob_type in spawn_list:
            little_intervals_count = interval / 0.1
            little_intervals_counter = 0
            while little_intervals_count - little_intervals_counter > 0.05:
                sleep(0.1)
                if not self.on_pause:
                    little_intervals_counter += 1
                    self.time_in_game += 0.1
            self.mob_query.append((mob_type, road_index))

    def on_click(self, pos):
        click = pygame.Rect(*pos, 1, 1)
        for add_tower_menu in self.add_tower_menus:
            add_tower_menu.check_click(click)
            self.close_add_tower_menu()
            return
        # Если пользователь нажал в любое место экрана, но не на кнопку,
        # то открытое меню добавления башни, если оно есть, закроется:
        self.close_add_tower_menu()
        if click.colliderect(self.pause_button):
            self.update_and_render()
            self.pause()
            return
        for plant in self.plants:
            if click.colliderect(plant) and plant.free:
                AddTowerMenu(plant, self.moblist, self.currency, self.towers, self.bullets, self.add_tower_menus)
                return
        for mob in self.moblist:
            if click.colliderect(mob):
                mob.tagged = True
                if self.tagged_mob is not None and self.tagged_mob != mob:
                    self.tagged_mob.tagged = False
                self.tagged_mob = mob
                self.mob_mark.place(click.x, click.y)
                return

    def on_tap(self, key):
        if key == pygame.K_TAB:
            self.pause()
        elif key == pygame.K_END:
            self.save_progress()
            self.quit()

    def pause(self):
        self.on_pause = True
        # Инициализация меню паузы
        menu = pygame.sprite.Group()
        menu_table = pygame.sprite.Sprite(menu)
        menu_table.rect = pygame.Rect(660, 190, 600, 700)
        menu_table.image = load_image(os.path.join('sprites', 'pause_menu.png'), -1)
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
                    elif click.colliderect(sounds_slider):
                        changing_sounds_volume = True
                        volume_changing_bias = event.pos[0] - sounds_slider.rect.x
                    elif click.colliderect(exit_button):
                        self.save_progress()
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
                        self.save_progress()
                        self.quit()
                pygame.display.flip()

    def render_currency(self):
        self.screen.blit(COIN_ICON, (20, 20))
        currency_text = CURRENCY_FONT.render(f': {Game.currency}', True, (245, 189, 31))
        self.screen.blit(currency_text, (130, 40))

    def update_and_render(self):
        # Спавн мобов
        if self.mob_query:
            mob_type, road_index = self.mob_query.pop(-1)
            way, way_index = self.map.get_way(road_index)
            mob = Mob(self.mobs[mob_type], way, mob_type, road_index, way_index)
            self.moblist.append(mob)
        # Отрисовка карты
        self.map.render(self.screen)
        # Обновление и отрисовка игровых объектов
        self.main_tower.update()
        self.main_tower.draw(self.screen)
        for mob_type in (HORNY_DOG, BOAR_WARRIOR, SKILLET, CRYSTAL_GOLEM, STONE_GOLEM, MASK):
            self.mobs[mob_type].update()
            self.mobs[mob_type].draw(self.screen)
        self.plants.draw(self.screen)
        self.towers.update()
        self.towers.draw(self.screen)
        self.bullets.update()
        self.bullets.draw(self.screen)
        self.add_tower_menus.draw(self.screen)
        for add_tower_menu in self.add_tower_menus:
            add_tower_menu.draw_buttons(self.screen)
        self.buttons.draw(self.screen)
        self.render_currency()
        self.mob_mark.update_and_render(self.screen)

    def close_add_tower_menu(self):
        for add_tower_menu in self.add_tower_menus:
            add_tower_menu.kill()

    def save_progress(self):
        con = sqlite3.connect(os.path.join('data', 'save_slots_db.sqlite3'))
        cur = con.cursor()
        # Сохранение основной информации:
        cur.execute('''DELETE FROM slots
                       WHERE id = ?''', (self.save_slot,))
        cur.execute('INSERT INTO slots VALUES (?, ?, ?, ?, ?)',
                    (self.save_slot, self.mt.health, self.level, self.time_in_game, self.currency))
        # Сохранение информации о мобах:
        cur.execute('''DELETE FROM mobs
                       WHERE slot_id = ?''', (self.save_slot,))
        mobs_data = []
        for mob in self.moblist:
            if mob.state != 'death':
                mobs_data.append((self.save_slot, mob.type, mob.road_index, mob.way_index, *mob.coords,
                                  mob.pos, mob.state, mob.animation_index, *mob.steps, mob.health, mob.tagged))
        if mobs_data:
            cur.execute('INSERT INTO mobs VALUES ' + ', '.join([str(mob_data) for mob_data in mobs_data]))
        self.moblist = [mob for mob in self.moblist if mob.state != 'death']
        # Сохранение информации о снарядах:
        cur.execute('''DELETE FROM bullets
                       WHERE slot_id = ?''', (self.save_slot,))
        bullets_data = []
        for bullet in self.bullets:
            bullets_data.append((self.save_slot, *bullet.coords, bullet.angle, *bullet.end_coords, bullet.type,
                                 bullet.velocity, bullet.damage, self.moblist.index(bullet.mob)))
        if bullets_data:
            cur.execute('INSERT INTO bullets VALUES ' + ', '.join([str(bullet_data) for bullet_data in bullets_data]))
        # Сохранение информации о башнях:
        cur.execute('''DELETE FROM towers
                       WHERE slot_id = ?''', (self.save_slot,))
        towers_data = []
        for tower in self.towers:
            towers_data.append((self.save_slot, *tower.coords, tower.reloading, str(tower), tower.animation_index))
        if towers_data:
            cur.execute('INSERT INTO towers VALUES ' + ', '.join([str(tower_data) for tower_data in towers_data]))
        con.commit()
        con.close()

    def quit(self):
        pygame.quit()
        sys.exit(0)


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    MOB_ANIMATIONS = load_mob_animations()
    BULLETS_SPRITES = load_bullets_sprites()
    MAINTOWER_IMAGE = pygame.transform.scale(load_image(os.path.join('sprites', 'main_tower.png')), (300, 300))
    ADD_TOWER_MENU_IMAGE = load_image(os.path.join('sprites', 'add_tower_menu.png'))
    COIN_ICON = load_image(os.path.join('sprites', 'coin.png'))
    SMALL_COIN_ICON = pygame.transform.scale(load_image(os.path.join('sprites', 'coin.png')), (20, 20))
    MOB_MARK_SPRITE = load_image(os.path.join('sprites', 'mark.png'))
    CURRENCY_FONT = pygame.font.SysFont('Arial', 60)
    SMALL_FONT = pygame.font.SysFont('Arial', 25)
    game = Game(screen)
    game.begin()
    running = True
    time = pygame.time.Clock()
    while running:
        time.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                game.on_click(event.pos)
            if event.type == pygame.KEYDOWN:
                game.on_tap(event.key)
            elif event.type == pygame.QUIT:
                break
        screen.fill('black')
        game.update_and_render()
        pygame.display.flip()
    pygame.quit()
