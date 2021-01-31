import random
import math
import sqlite3
from threading import Thread
from sprites import *
from online_game import play_online
from exceptions import ServerError
from utils import load_ways, calculate_distance_between_points
from pygame_functions import *


class Map:
    def __init__(self, index):
        self.dir = os.path.join('maps', f'map{index}')
        self.ways = load_ways(self.dir)
        self.image = load_image(os.path.join(self.dir, 'image.png'))

    def get_way(self, road_index, way_index=None):
        """Возвращает путь по заданным индексам дороги и пути.
        Если индекс пути не задан, возвращается случайный путь и его индекс"""
        if way_index is None:
            road = self.ways[road_index]
            way_index = random.randint(0, len(road) - 1)
            return road[way_index], way_index
        return self.ways[road_index][way_index]

    def render(self, screen):
        screen.blit(self.image, (0, 0))


class Mob(pygame.sprite.Sprite):
    def __init__(self, group, way, type, road_index, way_index, x=None, y=None, pos=0, state='move',
                 animation_index=0., steps_to_next_point=0, health=None, tagged=False, target=None):
        super().__init__(group)
        self.way = way
        self.type = type
        self.road_index = road_index
        self.way_index = way_index
        self.pos = pos
        self.state = state
        self.load_info(self.type)
        self.animations = MOB_ANIMATIONS[self.type]
        self.animation = self.animations[state]
        self.animation_index = animation_index
        self.steps_to_next_point = steps_to_next_point
        self.tagged = tagged
        self.target = target  # сюда передаётся главная башня
        # Моб может либо спавниться по ходу игры, либо загружаться из БД при продолжении сохранённой игры.
        # В первом случае опциональные аргументы не передаются, а во втором передаются
        if x is None:
            # Если опциональные аргументы не переданы, то просто ставим моба в начало пути
            self.coords = list(self.way[0])
        else:
            # Иначе приводим моба в такое состояние, в котором он был перед сохранением игры
            self.coords = [x, y]
            self.health = health
            self.image = self.animation[int(self.animation_index)]
            try:
                if self.steps_to_next_point > 0:
                    next_point = self.way[self.pos]
                    d_x, d_y = next_point[0] - self.coords[0], next_point[1] - self.coords[1]
                    self.x_velocity = d_x / self.steps_to_next_point
                    self.y_velocity = d_y / self.steps_to_next_point
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
        """Загружает параметры моба из json файла"""
        with open(os.path.join('mobs', type, 'info.json'), 'r', encoding='utf-8') as info_file:
            self.info = json.load(info_file)
        self.width = self.info[self.state]['width']
        self.height = self.info[self.state]['height']
        self.velocity = self.info['velocity'] / FPS
        self.health = self.max_health = self.info['health']
        self.damage = self.info['damage']
        self.reward = self.info['reward']
        self.animation_speed = self.info[self.state]['animation_speed']
        self.animation_length = self.info[self.state]['animation_length']
        self.health_line_bias = tuple(self.info['health_line_bias'].values())

    def get_position(self, delta_steps):
        """Возвращает координату, в которой окажется моб через заданное количество шагов"""
        index = self.pos
        steps = self.steps_to_next_point
        way_len = len(self.way)
        # Будет просчитываться движение моба до тех пор, пока он не пройдёт нужное количество шагов
        while index < way_len - 1:
            if steps < delta_steps:
                delta_steps -= steps
            else:
                if index > self.pos:
                    way_point_1 = self.way[index - 1]
                else:
                    way_point_1 = self.coords.copy()
                way_point_2 = self.way[index]
                d_x = way_point_2[0] - way_point_1[0]
                d_y = way_point_2[1] - way_point_1[1]
                return (way_point_1[0] + d_x / steps * delta_steps,
                        way_point_1[1] + d_y / steps * delta_steps)
            start_point = self.way[index]
            index += 1
            next_point = self.way[index]
            d_x, d_y = next_point[0] - start_point[0], next_point[1] - start_point[1]
            steps = math.hypot(d_x, d_y) / self.velocity
        else:
            return self.way[-1]

    def update(self):
        # Смена картинки:
        if round(self.animation_index, 1).is_integer():
            self.image = self.animation[int(self.animation_index)]
        self.animation_index = (self.animation_index + self.animation_speed) % self.animation_length
        if self.health > 0:
            # Отрисовка полоски здоровья:
            draw_health_indicator(int(self.coords[0] - self.width / 2 + self.health_line_bias[0]),
                                  int(self.coords[1] - self.height / 2 - self.health_line_bias[1]),
                                  self.health,
                                  self.max_health,
                                  30,
                                  5,
                                  screen)
            try:
                if self.steps_to_next_point <= 0:
                    # Определение маршрута до следующей точки пути:
                    start_point = self.way[self.pos]
                    self.pos += 1
                    next_point = self.way[self.pos]
                    d_x = next_point[0] - start_point[0]
                    d_y = next_point[1] - start_point[1]
                    self.steps_to_next_point = math.hypot(d_x, d_y) // self.velocity
                    self.x_velocity = d_x / self.steps_to_next_point
                    self.y_velocity = d_y / self.steps_to_next_point
                self.steps_to_next_point -= 1
                self.coords[0] += self.x_velocity
                self.coords[1] += self.y_velocity
                self.rect.x = self.coords[0] - self.width / 2
                self.rect.y = self.coords[1] - self.height / 2
            except IndexError:  # Значит, моб дошёл до конца пути
                self.attack(self.target)
        elif self.state != 'death':
            self.kill()
        elif round(self.animation_index) == self.animation_length:
            # Если проигралась анимация смерти, убиваем спрайт:
            super().kill()

    def get_data(self):
        """Возвращает всю информацию о мобе для сохранения в БД сохранений"""
        return (self.type, self.road_index, self.way_index, *self.coords,
                self.pos, self.state, self.animation_index, self.steps_to_next_point, self.health, self.tagged)

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
        Game.currency += self.reward
        self.animation = self.animations['death']
        self.animation_index = 0.
        self.animation_speed = self.info['death']['animation_speed']
        self.animation_length = self.info['death']['animation_length']
        self.width, self.height = self.info['death']['width'], self.info['death']['height']


class BowTower(pygame.sprite.Sprite):
    cost = 50
    width = 250
    height = 250
    time_to_reload = 100
    shooting_range = 600
    damage = 10
    x_bias = 125
    y_bias = -25
    # bias - смещение точки, из которой вылетает снаряд, от левого верхнего угла плента, на котором спавнится башня

    def __init__(self, group, coords, moblist, bullets_group, reloading=0, animation_index=0):
        super().__init__(group)
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.moblist = moblist
        self.bullets_group = bullets_group
        self.reloading = reloading  # сколько времени осталось до выстрела(сек/60)
        self.animation_index = animation_index  # Всегда равен нулю, так как эта башня не имеет анимации
        self.image = TOWERS_SPRITES['bow'][0]
        self.rect = pygame.Rect(self.coords[0] - self.x_bias,
                                self.coords[1] + self.y_bias,
                                self.width,
                                self.height)

    def update(self):
        if not self.reloading:
            # Поиск цели:
            for mob in sorted(self.moblist, key=lambda mob_: not mob_.tagged):
                if mob.state != 'death':
                    distance = calculate_distance_between_points(*self.coords, *mob.coords)
                    if distance <= self.shooting_range:
                        Bullet(self.bullets_group, self.coords, self.damage, 'arrow', distance, mob)
                        self.reloading = self.time_to_reload
                        return
        else:
            self.reloading -= 1

    def get_data(self):
        """Возвращает всю информацию о башне для сохранения в БД сохранений"""
        return (*self.coords, self.reloading, 'bow', self.animation_index)


class CannonTower(pygame.sprite.Sprite):
    cost = 100
    width = 250
    height = 250
    time_to_reload = 200
    shooting_range = 800
    damage = 40
    x_bias = 125
    y_bias = 75
    # bias - смещение точки, из которой вылетает снаряд, от левого верхнего угла плента, на котором спавнится башня
    animation_length = 16

    def __init__(self, group, coords, moblist, bullets_group, reloading=0, animation_index=0):
        super().__init__(group)
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.moblist = moblist
        self.bullets_group = bullets_group
        self.reloading = reloading  # сколько времени осталось до выстрела(сек/60)
        self.animation_index = animation_index
        self.image = TOWERS_SPRITES['cannon'][13]
        self.rect = pygame.Rect(self.coords[0] - self.x_bias,
                                self.coords[1] - self.y_bias,
                                self.width,
                                self.height)

    def update(self):
        if not self.reloading:
            # Поиск цели:
            for mob in sorted(self.moblist, key=lambda mob_: not mob_.tagged):
                if mob.state != 'death':
                    distance = calculate_distance_between_points(*self.coords, *mob.coords)
                    if distance <= self.shooting_range:
                        bullet = Bullet(self.bullets_group, self.coords, self.damage, 'shell', distance, mob,
                                        velocity=20)
                        # Пушка меняет спрайт в зависимости от того под каким углом она выстрелила
                        self.animation_index = round(bullet.angle / (math.pi / 8)) % self.animation_length
                        self.image = TOWERS_SPRITES['cannon'][self.animation_index]
                        self.reloading = self.time_to_reload
                        return
        else:
            self.reloading -= 1

    def get_data(self):
        """Возвращает всю информацию о башне для сохранения в БД сохранений"""
        return (*self.coords, self.reloading, 'cannon', self.animation_index)


class CrystalTower(pygame.sprite.Sprite):
    cost = 150
    width = 250
    height = 300
    time_to_reload = 30
    shooting_range = 700
    damage = 7
    x_bias = 115
    y_bias = -50
    # bias - смещение точки, из которой вылетает снаряд, от левого верхнего угла плента, на котором спавнится башня
    animation_length = 27

    def __init__(self, group, coords, moblist, bullets_group, reloading=0, animation_index=0):
        super().__init__(group)
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.moblist = moblist
        self.bullets_group = bullets_group
        self.reloading = reloading  # сколько времени осталось до выстрела(сек/60)
        self.animation_index = animation_index
        self.image = TOWERS_SPRITES['crystal'][0]
        self.rect = pygame.Rect(self.coords[0] - self.x_bias,
                                self.coords[1] + self.y_bias,
                                self.width,
                                self.height)

    def update(self):
        if not self.reloading:
            # Поиск цели:
            for mob in sorted(self.moblist, key=lambda mob_: not mob_.tagged):
                if mob.state != 'death':
                    distance = calculate_distance_between_points(*self.coords, *mob.coords)
                    if distance <= self.shooting_range:
                        HomingBullet(self.bullets_group, self.coords, self.damage, 'sphere', mob)
                        self.reloading = self.time_to_reload
                        return
        else:
            self.reloading -= 1
        self.animation_index = (self.animation_index + 0.3) % self.animation_length
        self.image = TOWERS_SPRITES['crystal'][int(self.animation_index)]

    def get_data(self):
        """Возвращает всю информацию о башне для сохранения в БД сохранений"""
        return (*self.coords, self.reloading, 'crystal', self.animation_index)


class MainTower(pygame.sprite.Sprite):
    health = 1000
    full_hp = 1000
    time_to_reload = 60
    shooting_range = 600
    damage = 10

    def __init__(self, group, coords, moblist, bullets_group):
        super().__init__(group)
        self.coords = coords
        self.moblist = moblist
        self.bullets_group = bullets_group
        self.reloading = 0
        self.rect = pygame.Rect(*self.coords, 10, 10)
        self.image = MAINTOWER_IMAGE

    def set_position(self, coords):
        self.coords = self.rect.x, self.rect.y = coords

    def update(self):
        if self.health > 0:
            # Отрисовка полоски здоровья:
            pygame.draw.rect(screen, 'blue', (int(self.coords[0] + 95), int(self.coords[1]) + 25, 110, 20))
            draw_health_indicator(int(self.coords[0] + 100), int(self.coords[1]) + 30,
                                  self.health, self.full_hp, 100, 10, screen)

            if not self.reloading:
                # Поиск цели:
                for mob in sorted(self.moblist, key=lambda mob_: not mob_.tagged):
                    distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                    if distance <= self.shooting_range and mob.state != 'death':
                        coords = (self.coords[0] + 135, self.coords[1] + 70)
                        Bullet(self.bullets_group, coords, self.damage, 'arrow', distance, mob)
                        self.reloading = self.time_to_reload
                        return
            else:
                self.reloading -= 1
        else:
            self.kill()

    def hit(self, damage):
        self.health -= damage


class Bullet(pygame.sprite.Sprite):
    """Класс прямолетящего снаряда"""
    def __init__(self, group, start_coords, damage, type, distance_to_target, mob,
                 end_coords=None, velocity=10, angle=None):
        super().__init__(group)
        self.type = type
        self.coords = list(start_coords)
        self.damage = damage
        self.rect = pygame.Rect(self.coords[0] - 5, self.coords[1] - 5, 10, 10)
        self.distance_to_target = distance_to_target
        self.mob = mob
        self.end_coords = end_coords
        self.velocity = velocity
        self.angle = angle
        if end_coords:
            # Если конечную точку дали сразу, то снаряд просто летит туда, а если нет,
            # то конечная точка вычисляется исходя из движения моба-цели
            self.steps_to_target = distance_to_target / self.velocity
            self.step = (self.velocity * math.cos(self.angle),
                         self.velocity * -math.sin(self.angle))
        else:
            self.calculate_trajectory(mob, distance_to_target)
        self.image = pygame.transform.rotate(BULLETS_SPRITES[self.type][0], math.degrees(self.angle))

    def calculate_trajectory(self, mob, distance_to_target):
        """Рассчитывает маршрут полёта стрелы до противника и угол, под которым полетит стрела"""
        flight_time = distance_to_target / self.velocity
        self.end_coords = mob.get_position(flight_time)
        d_x, d_y = self.end_coords[0] - self.coords[0], self.end_coords[1] - self.coords[1]
        distance = math.hypot(d_x, d_y) + 1
        self.velocity = distance / flight_time
        self.step = (d_x / distance * self.velocity,
                     d_y / distance * self.velocity)
        self.steps_to_target = distance / self.velocity
        try:
            self.angle = -math.atan(d_y / d_x)
        except ZeroDivisionError:
            self.angle = math.pi / 2 * (d_y / abs(d_y))
        if d_x < 0:
            self.angle += math.pi

    def update(self):
        if self.steps_to_target > 0:
            self.coords[0] += self.step[0]
            self.coords[1] += self.step[1]
            self.rect.x = self.coords[0] - 5
            self.rect.y = self.coords[1] - 5
            self.steps_to_target -= 1
        else:
            self.mob.hit(self.damage)
            self.kill()

    def get_data(self):
        """Возвращает всю информацию о снаряде для сохранения в БД сохранений"""
        return (*self.coords, self.angle, *self.end_coords, self.type, self.velocity, self.damage)


class HomingBullet(pygame.sprite.Sprite):
    """Класс самонаводящегося снаряда"""
    def __init__(self, group, start_coords, damage, type, mob, angle=0):
        super().__init__(group)
        self.coords = list(start_coords)
        self.damage = damage
        self.type = type
        self.mob = mob
        self.velocity = 5
        self.animation_index = 0
        self.animation_length = 5
        self.rect = pygame.Rect(*self.coords, 40, 25)
        self.image = BULLETS_SPRITES[self.type][0]
        self.angle = angle

    def update(self):
        x, y = self.coords
        x1, y1 = self.mob.coords
        d_x, d_y = x1 - x, y - y1
        distance = math.hypot(d_x, d_y) + 1
        self.coords[0] += self.velocity * (d_x / distance)
        self.coords[1] += self.velocity * (-d_y / distance)
        self.rect.x, self.rect.y = self.coords
        try:
            self.angle = math.atan(d_y / d_x)
        except ZeroDivisionError:
            self.angle = math.pi / 2 * (d_y / abs(d_y))
        if d_x > 0:
            self.angle += math.pi
        self.image = pygame.transform.rotate(BULLETS_SPRITES[self.type][self.animation_index], math.degrees(self.angle))
        self.animation_index = (self.animation_index + 1) % self.animation_length
        if distance < 10 or self.mob.state == 'death':
            self.mob.hit(self.damage)
            self.kill()

    def get_data(self):
        """Возвращает всю информацию о снаряде для сохранения в БД сохранений"""
        return (*self.coords, self.angle, 0, 0, self.type, self.velocity, self.damage)


class AddTowerMenu(pygame.sprite.Sprite):
    """Меню выбора башни, выпадающее при нажатии на плент"""
    width = 400
    height = 180

    def __init__(self, group, plant, moblist, group_for_towers, group_for_bullets):
        super().__init__(group)
        self.coords = plant.rect.x, plant.rect.y
        self.plant = plant
        self.moblist = moblist
        self.group_for_towers = group_for_towers
        self.group_for_bullets = group_for_bullets
        self.image = ADD_TOWER_MENU_IMAGE
        self.rect = pygame.Rect(self.coords[0] - 70,
                                self.coords[1] - 100,
                                self.width,
                                self.height)
        self.buttons = pygame.sprite.Group()
        self.init_ui()

    def init_ui(self):
        """Инициализаця кнопок и подписей под ними"""
        self.bow_tower_button = Button(
            (self.coords[0] - 5, self.coords[1] - 60, 80, 80),
            'bow_tower_icon.png',
            self.buttons
        )
        self.cost1 = MOB_COST_FONT.render(str(BowTower.cost), True, (245, 189, 31))
        self.cannon_tower_button = Button(
            (self.coords[0] + 95, self.coords[1] - 60, 80, 80),
            'cannon_tower_icon.png',
            self.buttons
        )
        self.cost2 = MOB_COST_FONT.render(str(CannonTower.cost), True, (245, 189, 31))
        self.crystal_tower_button = Button(
            (self.coords[0] + 195, self.coords[1] - 60, 80, 80),
            'crystal_tower_icon.png',
            self.buttons
        )
        self.cost3 = MOB_COST_FONT.render(str(CrystalTower.cost), True, (245, 189, 31))

    def check_click(self, click):
        if click.colliderect(self.bow_tower_button):
            if Game.currency >= BowTower.cost:
                self.spawn_tower(BowTower)
        elif click.colliderect(self.cannon_tower_button):
            if Game.currency >= CannonTower.cost:
                self.spawn_tower(CannonTower)
        elif click.colliderect(self.crystal_tower_button):
            if Game.currency >= CrystalTower.cost:
                self.spawn_tower(CrystalTower)

    def spawn_tower(self, tower):
        if self.plant.tower is not None:  # если уже стоит башня
            if self.plant.tower.cost >= tower.cost:
                return  # нельзя заменить более дорогую башню на более дешёвую
            self.plant.tower.kill()
        self.plant.tower = tower(self.group_for_towers, self.coords, self.moblist, self.group_for_bullets)
        Game.currency -= tower.cost
        self.plant.image = load_image(os.path.join('sprites', 'nothing.png'))

    def draw_buttons(self, surface):
        self.buttons.draw(surface)
        # Отрисовка подписей под кнопками:
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
        """Появление крестика"""
        self.sprite.rect.x = x - 30
        self.sprite.rect.y = y - 30
        self.sprite.image = self.image
        self.size = 60
        self.exist = True

    def update_and_render(self, surface):
        if self.exist:
            self.sprite.image = pygame.transform.scale(self.image, (self.size, self.size))
            self.draw(surface)
            # Уменьшение размера крестика:
            self.size -= 2
            self.sprite.rect.x += 1
            self.sprite.rect.y += 1
            if self.size <= 0:
                self.exist = False


class Game:
    currency = 1000

    def __init__(self, screen):
        self.screen = screen
        self.level = 1
        self.mobs = {
            MASK: pygame.sprite.Group(),
            SKILLET: pygame.sprite.Group(),
            STONE_GOLEM: pygame.sprite.Group(),
            BOAR_WARRIOR: pygame.sprite.Group(),
            HORNY_DOG: pygame.sprite.Group(),
            CRYSTAL_GOLEM: pygame.sprite.Group()
        }
        self.towers = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.buttons = pygame.sprite.Group()
        self.add_tower_menus = pygame.sprite.Group()
        self.pause_button = Button((1800, 30, 80, 80), 'pause.png', self.buttons)
        self.on_pause = False
        self.mob_query = []
        self.moblist = []
        self.main_tower_group = pygame.sprite.Group()
        self.main_tower = MainTower(self.main_tower_group, MAINTOWERS_POSITIONS[self.level], self.moblist, self.bullets)
        self.mob_mark = MobMark()  # Крестик, которым можно помечать мобов
        self.playing = False  # playing == True когда игрок проходит кампанию

    def reset(self):
        """Сбрасывает текущее игровое состояние"""
        self.map = Map(self.level)
        Game.currency = 100
        self.plants = self.load_plants()
        self.main_tower.health = MainTower.full_hp
        self.add_tower_menus.empty()
        self.towers.empty()
        self.bullets.empty()
        self.kill_all_mobs()
        self.main_tower.set_position(MAINTOWERS_POSITIONS[self.level])
        self.tagged_mob = None  # Помеченный моб - тот, в которого в первую очередь стреляют башни
        self.time_in_game = 0
        self.on_pause = False
        self.level_completed = False

    def set_tagged_mob(self, mob, click_coords):
        if mob.state != 'death':
            mob.tagged = True
            if self.tagged_mob is not None and self.tagged_mob != mob:
                self.tagged_mob.tagged = False
            self.tagged_mob = mob
            self.mob_mark.place(*click_coords)

    def load_progress(self, save_slot_id):
        """Загружает игровой прогресс из базы данных"""
        con = sqlite3.connect(os.path.join('data', 'save_slots_db.sqlite3'))
        cur = con.cursor()
        main_data = cur.execute('''SELECT main_tower_hp, level, play_time, currency FROM slots 
                                   WHERE id = ?''', (save_slot_id,)).fetchone()
        if main_data and all(map(lambda v: v is not None, main_data)):  # Если в этом слоте лежат данные
            main_tower_hp, level, play_time, currency = main_data
            self.main_tower.health = main_tower_hp
            self.level = level
            self.main_tower.set_position(MAINTOWERS_POSITIONS[self.level])
            self.map = Map(self.level)
            self.plants = self.load_plants()
            self.time_in_game = play_time
            Game.currency = currency
            # Загрузка данных башен:
            towers_data = cur.execute('''SELECT * FROM towers
                                         WHERE slot_id = ?''', (save_slot_id,)).fetchall()
            towers = {'bow': BowTower, 'cannon': CannonTower, 'crystal': CrystalTower}
            for _, x, y, reloading, tower_type, animation_index in towers_data:
                tower = towers[tower_type]
                x -= tower.x_bias
                y -= tower.y_bias
                for plant in self.plants:
                    if plant.rect.x == x and plant.rect.y == y:
                        tower = tower(self.towers, (x, y), self.moblist, self.bullets, reloading, animation_index)
                        plant.tower = tower
                        plant.kill()
                        break
            # Загрузка данных мобов:
            mobs_data = cur.execute('''SELECT * FROM mobs
                                       WHERE slot_id = ?''', (save_slot_id,)).fetchall()
            for mob_data in mobs_data:
                mob = Mob(self.mobs[mob_data[1]], self.map.get_way(*mob_data[2:4]), *mob_data[1:],
                          target=self.main_tower)
                self.moblist.append(mob)
            # Загрузка данных снарядов:
            bullets_data = cur.execute('''SELECT * FROM bullets
                                          WHERE slot_id = ?''', (save_slot_id,)).fetchall()
            for _, x, y, angle, end_x, end_y, bullet_type, velocity, damage, mob_index in bullets_data:
                if bullet_type == 'sphere':
                    HomingBullet(self.bullets, (x, y), damage, bullet_type, self.moblist[mob_index], angle=angle)
                else:
                    distance = math.hypot(end_x - x, end_y - y)
                    Bullet(self.bullets, (x, y), damage, bullet_type, distance, self.moblist[mob_index],
                           end_coords=(end_x, end_y), velocity=velocity, angle=angle)
            con.close()

    def load_plants(self):
        """Загружает пленты(места под оборонительные башни)"""
        plants = pygame.sprite.Group()
        with open(os.path.join(self.map.dir, 'plants.csv'), 'r') as f:
            for line in f.readlines():
                plant_coords = tuple(map(lambda coord: float(coord) - 125, line.rstrip().split(';')))
                plant_sprite = pygame.sprite.Sprite(plants)
                plant_sprite.rect = pygame.Rect(*plant_coords, 250, 250)
                plant_sprite.image = PLANT_IMAGE
                plant_sprite.tower = None
        return plants

    def show_splash_screen(self):
        """Проигрывает игровую заставку"""
        frame_index = 1
        time = pygame.time.Clock()
        load_sound = pygame.mixer.Sound(os.path.join('sounds', 'Snake_load_sound.wav'))
        load_sound.play()

        while frame_index < 280:
            time.tick(FPS)
            frame = load_image(os.path.join('sprites', 'loading_screen', f'{frame_index}.png'))
            screen.blit(frame, (0, 0))
            frame_index += 1
            pygame.display.flip()
            # При какой-либо активности игрока заставка прекращается:
            for event in pygame.event.get():
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                    load_sound.stop()
                    return

        fade(self.screen, load_image(os.path.join('sprites', 'background_image.png')))

    def begin(self):
        """Отрисовывает главное меню и обрабатывает действия пользователя в главном меню"""
        def wait_and_close_server_error(background):
            sleep(3)
            if state == 'main_menu':
                # Заслоняем сообщение об ошибке сервера:
                self.screen.blit(background.subsurface((700, 330, 600, 100)), (700, 330))

        self.reset()
        # Фоновая музыка меню:
        background_menu_sound = pygame.mixer.Sound(os.path.join('sounds', 'Background_sound.wav'))
        background_menu_sound.play()
        # Инициализация фоновой картинки и кнопок:
        background = load_image(os.path.join('sprites', 'background_image.png'))
        menu = pygame.sprite.Group()
        menu_table = pygame.sprite.Sprite(menu)  # фоновая табличка главного меню, на которой расположены кнопки
        menu_table.rect = pygame.Rect(700, 400, 600, 450)
        menu_table.image = load_image(os.path.join('sprites', 'main_menu.png'))
        singleplayer_button = Button((800, 500, 350, 90), 'start_single_game.png', menu)
        multiplayer_button = Button((800, 650, 350, 90), 'start_online_game.png', menu)
        exit_button = Button((800, 800, 350, 90), 'exit.png', menu)
        state = 'main_menu'  # state может быть либо "main_menu" либо "choose_save_slot_menu"
        save_slot_buttons = []
        self.screen.blit(background, (0, 0))
        menu.draw(self.screen)
        # Ожидание нажатия игроком каких-либо кнопок и обработка этих нажатий:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    click = pygame.Rect(*event.pos, 1, 1)
                    if state == 'main_menu':
                        if click.colliderect(singleplayer_button):
                            # Открывается меню выбора слота сохранения
                            state = 'choose_save_slot_menu'
                            # Удаляем старые кнопки:
                            singleplayer_button.kill()
                            multiplayer_button.kill()
                            exit_button.kill()
                            # Изменяем табличку:
                            menu_table.rect.y -= 150
                            menu_table.image = load_image(os.path.join('sprites', 'save_slots_menu.png'))
                            # Создаём новые кнопки:
                            for save_slot in range(5):
                                save_slot_buttons.append(Button(
                                    (800, 400 + save_slot * 100, 340, 90),
                                    f'save_slot_{save_slot + 1}.png',
                                    menu
                                ))
                            self.screen.blit(background, (0, 0))
                            menu.draw(self.screen)
                        elif click.colliderect(multiplayer_button):
                            # Запускаем онлайн матч:
                            try:
                                Thread(target=start_or_stop_music, args=(background_menu_sound, True),
                                       daemon=True).start()
                                self.online_match()
                                return
                            except ServerError:
                                # Показываем ошибку:
                                server_error = load_image(os.path.join('sprites', 'server_error.png'))
                                self.screen.blit(server_error, (700, 330))
                                Thread(target=wait_and_close_server_error, args=[background]).start()
                        elif click.colliderect(exit_button):
                            self.quit()
                    else:  # когда игрок выбирает слот сохранения(state == "choose_save_slot_menu")
                        for index, button in enumerate(save_slot_buttons):
                            if click.colliderect(button.rect):
                                self.start_campaign(index + 1)
                                Thread(target=start_or_stop_music, args=(background_menu_sound, True),
                                       daemon=True).start()
                                return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_END:
                        self.quit()
                elif event.type == pygame.QUIT:
                    self.quit()
            pygame.display.flip()

    def start_campaign(self, save_slot):
        # Мелодия боя:
        self.background_fight_sound = pygame.mixer.Sound(os.path.join('sounds', 'Background_fight_sound.wav'))
        Thread(target=start_or_stop_music, args=(self.background_fight_sound,), daemon=True).start()

        self.save_slot = save_slot
        self.load_progress(save_slot)
        self.level_completed = False
        self.playing = True
        self.mobs_spawn_thread = Thread(target=self.spawn_mobs, daemon=True)
        self.mobs_spawn_thread.start()

    def start_next_level(self):
        fade(self.screen, BLACK_SCREEN, 2.5)
        if self.level < 4:
            self.reset()
            self.playing = True
            self.mobs_spawn_thread = Thread(target=self.spawn_mobs, daemon=True)
            self.mobs_spawn_thread.start()
            fade(self.screen, self.map.image, 5)
        else:
            self.end_game('win.png')

    def online_match(self):
        exit_state = play_online(self.screen)
        if exit_state == 'exit':
            self.begin()
        else:
            self.end_game(image=exit_state + '.png')

    def spawn_mobs(self):
        """Спавнит мобов по расписанию, заданному в константе SPAWN_DATA.
           Запускается в отдельном потоке"""
        start = self.time_in_game
        spawn_list = SPAWN_DATA[self.level]
        # Нужно пропустить часть мобов, которые уже были заспавнены(если игра была загружена из слота сохранения)
        # Для этого обрежем нужную часть списка spawn_list с начала:
        for index, (interval, road_index, mob_type) in enumerate(spawn_list):
            if interval <= start:
                start -= interval
            else:
                spawn_list = list(spawn_list[index:])
                spawn_list[0] = (interval - start, road_index, mob_type)
                spawn_list = tuple(spawn_list)
                break
        else:  # если все мобы уже появились
            spawn_list = []
        # Начинаем спавн:
        for interval, road_index, mob_type in spawn_list:
            # interval - промежуток времени до спавна последующего моба
            # Он будет разбит на малые итервалы по 0.1 секунды
            little_intervals_count = interval / 0.1
            little_intervals_counter = 0
            while little_intervals_count - little_intervals_counter > 0.05 and self.playing:
                sleep(0.1)  # спим малый интервал
                if not self.on_pause:
                    little_intervals_counter += 1
                    self.time_in_game += 0.1
            # Если игрок вышел в меню, спавн мобов прекращается:
            if not self.playing:
                break
            # Когда время пришло, моб добавляется в очередь спавна:
            self.mob_query.append((mob_type, road_index))
        else:
            self.level_completed = True

    def on_click(self, pos):
        click = pygame.Rect(*pos, 1, 1)
        for add_tower_menu in self.add_tower_menus:
            add_tower_menu.check_click(click)
            self.add_tower_menus.empty()
            return
        # Если пользователь нажал в любое место экрана, но не на кнопку в меню спавна башни,
        # то открытое меню спавна башни, если оно есть, закроется:
        self.add_tower_menus.empty()

        if click.colliderect(self.pause_button):
            self.update_and_render()
            self.pause()
            return

        for plant in self.plants:
            if click.colliderect(plant):
                AddTowerMenu(self.add_tower_menus, plant, self.moblist, self.towers, self.bullets)
                return

        for mob in self.moblist:
            if click.colliderect(mob):
                self.set_tagged_mob(mob, (click.x, click.y))
                return

    def on_keypress(self, key):
        if key == pygame.K_TAB or key == pygame.K_END:
            self.pause()

    def pause(self):
        """Ставит игру на паузу"""
        self.on_pause = True
        # Инициализация меню паузы
        menu = pygame.sprite.Group()
        menu_table = pygame.sprite.Sprite(menu)  # фоновая табличка меню паузы, на которой расположены кнопки
        menu_table.rect = pygame.Rect(660, 190, 600, 700)
        menu_table.image = load_image(os.path.join('sprites', 'pause_menu.png'))
        continue_button = Button((770, 300, 350, 90), 'continue.png', menu)
        x = 800 + self.background_fight_sound.get_volume() * 315  # Позиция слайдера-регулировщика громкости музыки
        music_slider = Button((x, 483, 20, 40), 'slider.png', menu)
        sounds_slider = Button((1115, 619, 20, 40), 'slider.png', menu)
        exit_button = Button((770, 680, 350, 90), 'exit.png', menu)
        menu.draw(self.screen)
        changing_music_volume = False  # изменяет ли игрок громкость музыки в данный момент
        changing_sounds_volume = False  # изменяет ли игрок громкость звука в данный момент
        volume_changing_bias = 0  # смещение курсора при регулировке громкости
        # Обработка взаимодействия пользователя с меню паузы:
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
                        self.playing = False
                        Thread(target=start_or_stop_music, args=(self.background_fight_sound, True),
                               daemon=True).start()
                        self.begin()
                        return
                elif event.type == pygame.MOUSEMOTION:
                    # Регулировка громкости музыки/звуков:
                    cursor_x_coord = event.pos[0] - volume_changing_bias
                    if 800 > cursor_x_coord:
                        next_pos = 800
                    elif 1115 < cursor_x_coord:
                        next_pos = 1115
                    else:
                        next_pos = cursor_x_coord
                    volume = (next_pos - 799) / 315
                    if changing_music_volume:
                        music_slider.rect.x = next_pos
                        self.background_fight_sound.set_volume(volume)
                    elif changing_sounds_volume:
                        sounds_slider.rect.x = next_pos
                    menu.draw(self.screen)  # перерисовываем меню, чтобы было видно что слайдер передвинулся
                elif event.type == pygame.MOUSEBUTTONUP:
                    changing_music_volume = False
                    changing_sounds_volume = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        self.on_pause = False
                        return
                    elif event.key == pygame.K_END:
                        self.save_progress()
                        self.playing = False
                        Thread(target=start_or_stop_music, args=(self.background_fight_sound, True),
                               daemon=True).start()
                        self.begin()
                pygame.display.flip()

    def render_currency(self):
        """Отрисовывает количество денег в левом верхнем углу экрана"""
        self.screen.blit(COIN_ICON, (20, 20))
        currency_text = CURRENCY_FONT.render(f': {Game.currency}', True, (245, 189, 31))
        self.screen.blit(currency_text, (130, 40))

    def update_and_render(self):
        # Проверка на проигранность игры
        if self.main_tower.health < 0:
            self.main_tower.health = self.main_tower.full_hp
            self.end_game()
        # Спавн мобов
        if self.mob_query:
            mob_type, road_index = self.mob_query.pop(-1)
            way, way_index = self.map.get_way(road_index)
            mob = Mob(self.mobs[mob_type], way, mob_type, road_index, way_index, target=self.main_tower)
            self.moblist.append(mob)
        # Отрисовка карты
        self.map.render(self.screen)
        # Обновление и отрисовка игровых объектов
        self.main_tower_group.update()
        self.main_tower_group.draw(self.screen)
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
        # Если уровень пройден, переходим на новый:
        if not any(self.mobs.values()) and self.level_completed:
            self.level += 1
            self.start_next_level()

    def save_progress(self):
        """Сохраняет прогресс в базу данных"""
        self.reset_progress()
        con = sqlite3.connect(os.path.join('data', 'save_slots_db.sqlite3'))
        cur = con.cursor()
        # Сохранение основной информации:
        cur.execute('INSERT INTO slots VALUES (?, ?, ?, ?, ?)',
                    (self.save_slot, self.main_tower.health, self.level, self.time_in_game, self.currency))
        # Чистка моб листа:
        for mob in self.moblist:
            if mob.state == 'death':
                self.moblist.remove(mob)
        # Сохранение информации о мобах:
        mobs_data = []
        for mob in self.moblist:
            mobs_data.append((self.save_slot, *mob.get_data()))
        if mobs_data:
            cur.execute('INSERT INTO mobs VALUES ' + ', '.join([str(mob_data) for mob_data in mobs_data]))
        # Сохранение информации о снарядах:
        bullets_data = []
        for bullet in self.bullets:
            bullets_data.append((self.save_slot, *bullet.get_data(), self.moblist.index(bullet.mob)))
        if bullets_data:
            cur.execute('INSERT INTO bullets VALUES ' + ', '.join([str(bullet_data) for bullet_data in bullets_data]))
        # Сохранение информации о башнях:
        towers_data = []
        for tower in self.towers:
            towers_data.append((self.save_slot, *tower.get_data()))
        if towers_data:
            cur.execute('INSERT INTO towers VALUES ' + ', '.join([str(tower_data) for tower_data in towers_data]))
        con.commit()
        con.close()

    def reset_progress(self):
        """Стирает из базы данных всю информацию о прогрессе на текущем слоте сохранения"""
        try:
            con = sqlite3.connect(os.path.join('data', 'save_slots_db.sqlite3'))
            cur = con.cursor()
            cur.execute('''DELETE FROM slots
                           WHERE id = ?''', (self.save_slot,))
            cur.execute('''DELETE FROM mobs
                           WHERE slot_id = ?''', (self.save_slot,))
            cur.execute('''DELETE FROM bullets
                           WHERE slot_id = ?''', (self.save_slot,))
            cur.execute('''DELETE FROM towers
                           WHERE slot_id = ?''', (self.save_slot,))
            con.commit()
            con.close()
        except AttributeError:  # Если не выбран текущий слот сохранения
            return

    def end_game(self, image='game_over.png'):
        """Плавно выводит на экран каритнку с какой-нибудь надписью, затем возвращает в главное меню"""
        try:
            Thread(target=start_or_stop_music, args=(self.background_fight_sound, True), daemon=True).start()
        except AttributeError:
            pass
        fade(self.screen, load_image(os.path.join('sprites', 'background_image.png')), 2)
        fade(self.screen, load_image(os.path.join('sprites', image)), 0.5)
        self.level = 1
        self.kill_all_mobs()
        self.reset_progress()
        self.begin()

    def kill_all_mobs(self):
        self.moblist.clear()
        for mob in self.mobs.keys():
            self.mobs[mob].empty()

    def quit(self):
        pygame.quit()
        sys.exit(0)


if __name__ == '__main__':
    screen = pygame.display.set_mode(SIZE)
    game = Game(screen)
    game.show_splash_screen()  # заставка
    game.begin()
    running = True
    fps_font = pygame.font.SysFont("Arial", 18)
    time = pygame.time.Clock()
    while running:
        time.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                game.on_click(event.pos)
            if event.type == pygame.KEYDOWN:
                game.on_keypress(event.key)
            elif event.type == pygame.QUIT:
                break
        screen.fill('black')
        game.update_and_render()
        fps_text = fps_font.render(str(int(time.get_fps())), True, (0, 255, 0))
        screen.blit(fps_text, (10, 0))
        pygame.display.flip()
    pygame.quit()
