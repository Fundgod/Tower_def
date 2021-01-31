import socket
import pickle
import math
from sprites import *
from exceptions import *
from threading import Thread
from utils import opponent
from pygame_functions import *


def load_mobs_data():
    """Загружает информацию о всех мобах из json файлов"""
    data = {}
    animations = load_mob_animations()
    for mob in MOBS:
        with open(os.path.join('mobs', mob, 'info.json'), 'r', encoding='utf-8') as info_file:
            data[mob] = json.load(info_file)
        data[mob]['animations'] = animations[mob]
    return data


def load_mob_spawn_zones():
    """Загружает зоны, в которых игроки могут спавнить мобов.
       Зона спавна представлена классом pygame.sprite.Sprite,
       но впоследствие нас будет интересовать только атрибут mask для того чтобы понять,
       по какой дороге должен идти моб, поставленный игроком - для каждой дороги своя зона спавна мобов"""
    zones = {
        PLAYER_1: [],
        PLAYER_2: []
    }
    path_to_roads = os.path.join('maps', 'online_game_map', 'ways')
    for road, rect1, rect2 in (('road1', (193, 404, 322, 372), (1420, 371, 326, 324)),
                               ('road2', (0, 0, 500, 547), (1420, 0, 500, 510)),
                               ('road3', (0, 621, 500, 459), (1420, 591, 543, 489))):
        p1_zone = pygame.sprite.Sprite()
        p1_zone.rect = pygame.Rect(*rect1)
        p1_zone.mask = pygame.mask.from_surface(load_image(os.path.join(path_to_roads, road, 'p1_mob_spawn_zone.png')))
        zones[PLAYER_1].append(p1_zone)

        p2_zone = pygame.sprite.Sprite()
        p2_zone.rect = pygame.Rect(*rect2)
        p2_zone.mask = pygame.mask.from_surface(load_image(os.path.join(path_to_roads, road, 'p2_mob_spawn_zone.png')))
        zones[PLAYER_2].append(p2_zone)
    return zones


def mirror_mob_icons():
    """Горизонтально отражает иконки мобов"""
    for mob in MOB_ICONS.keys():
        MOB_ICONS[mob] = pygame.transform.flip(MOB_ICONS[mob], True, False)


SERVER = '127.0.0.1'
PORT = 4444
ADDRESS = (SERVER, PORT)
MOBS_DATA = load_mobs_data()
ROAD_ZONES = load_mob_spawn_zones()


class AddTowerMenu(pygame.sprite.Sprite):
    """Меню выбора башни, выпадающее при нажатии на плент"""
    width = 400
    height = 180
    bow_tower_cost = 50
    cannon_tower_cost = 100
    crystal_tower_cost = 150

    def __init__(self, plant, client, currency, group):
        super().__init__(group)
        self.plant = plant
        self.coords = self.plant.rect.x, self.plant.rect.y
        self.client = client
        self.currency = currency
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
        self.cost1 = MOB_COST_FONT.render('50', True, (245, 189, 31))
        self.cannon_tower_button = Button(
            (self.coords[0] + 95, self.coords[1] - 60, 80, 80),
            'cannon_tower_icon.png',
            self.buttons
        )
        self.cost2 = MOB_COST_FONT.render('100', True, (245, 189, 31))
        self.crystal_tower_button = Button(
            (self.coords[0] + 195, self.coords[1] - 60, 80, 80),
            'crystal_tower_icon.png',
            self.buttons
        )
        self.cost3 = MOB_COST_FONT.render('150', True, (245, 189, 31))

    def check_click(self, click):
        """Проверяет, нажал ли игрок на кнопку спавна башни, если нажал то спавнит башню"""
        if click.colliderect(self.bow_tower_button):
            if self.currency >= self.bow_tower_cost:
                self.spawn_tower('bow')
        elif click.colliderect(self.cannon_tower_button):
            if self.currency >= self.cannon_tower_cost:
                self.spawn_tower('cannon')
        elif click.colliderect(self.crystal_tower_button):
            if self.currency >= self.crystal_tower_cost:
                self.spawn_tower('crystal')

    def spawn_tower(self, tower):
        """Отсылает серверу команду спавна башни и убирает плент, если он был"""
        self.client.send(str.encode(f"spawn_tower {tower} {';'.join(map(str, self.coords))}"))
        if self.plant.free:
            self.plant.free = False
            self.plant.image = load_image(os.path.join('sprites', 'nothing.png'))

    def draw_buttons(self, surface):
        self.buttons.draw(surface)
        costs_height = self.coords[1] + 20
        surface.blit(self.cost1, (self.coords[0] + 15, costs_height))
        surface.blit(self.cost2, (self.coords[0] + 105, costs_height))
        surface.blit(self.cost3, (self.coords[0] + 205, costs_height))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 45, costs_height + 3))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 150, costs_height + 3))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 250, costs_height + 3))


class SpawnMobMenu(pygame.sprite.Group):
    """Меню спавна мобов, которое находится в углу экрана"""
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.selected_mob = None
        self.mouse_pos = (0, 0)
        self.init_ui()

    def init_ui(self):
        self.background_image = pygame.sprite.Sprite(self)
        self.background_image.rect = pygame.Rect(0, 820, 319, 267)
        self.background_image.image = load_image(os.path.join('sprites', 'spawn_mob_menu.png'))
        self.mob_spawnable_zone = pygame.sprite.Sprite()  # будет выделяться прозрачно-зелёным цветом
        self.mob_spawnable_zone.rect = pygame.Rect(0, 0, 500, 1080)
        if self.player == PLAYER_2:
            self.mob_spawnable_zone.rect.x += 1520
        self.mob_spawnable_zone.image = load_image(os.path.join('sprites', 'mob_spawn_zone.png'))
        x_bias = 0
        if self.player == PLAYER_2:
            x_bias = 1605
        self.background_image.rect.x += x_bias
        self.buttons_dict = {
            Button((30 + x_bias, 845, 80, 80), SKILLET + '_icon.png', self): SKILLET,
            Button((120 + x_bias, 845, 80, 80), STONE_GOLEM + '_icon.png', self): STONE_GOLEM,
            Button((210 + x_bias, 845, 80, 80), CRYSTAL_GOLEM + '_icon.png', self): CRYSTAL_GOLEM,
            Button((30 + x_bias, 955, 80, 80), HORNY_DOG + '_icon.png', self): HORNY_DOG,
            Button((120 + x_bias, 955, 80, 80), BOAR_WARRIOR + '_icon.png', self): BOAR_WARRIOR,
            Button((210 + x_bias, 955, 80, 80), MASK + '_icon.png', self): MASK
        }

    def set_mouse_pos(self, pos):
        self.mouse_pos = pos

    def check_click_down(self, click):
        """Проверяет, нажал ли игрок на иконку одного из мобов"""
        for button in self.buttons_dict.keys():
            if click.colliderect(button):
                self.selected_mob = self.buttons_dict[button]
                self.add(self.mob_spawnable_zone)

    def check_click_up(self, click_rect):
        """Проверяет отпускание мыши. Если был выбран моб и игрок отпустил мышь в нужном месте,
           то возвращается команда спавна моба, в дальнейшем высылаемая на сервер"""
        click = pygame.sprite.Sprite()
        click.rect = click_rect
        click.mask = pygame.mask.Mask((1, 1), True)
        selected_mob = self.selected_mob
        self.selected_mob = None
        self.remove(self.mob_spawnable_zone)
        # Определение дороги моба:
        for road_index, road_zone in enumerate(ROAD_ZONES[self.player]):
            if selected_mob and pygame.sprite.collide_mask(click, road_zone):
                return f'spawn_mob {selected_mob} {road_index} {click.rect.x};{click.rect.y}'
        return 'ok'

    def draw(self, screen):
        super().draw(screen)
        # Если игрок перетаскивает моба на дорогу, то его нужно отрисовать:
        if self.selected_mob:
            screen.blit(MOB_ICONS[self.selected_mob], self.mouse_pos)


class Button(pygame.sprite.Sprite):
    def __init__(self, rect, filename, group):
        super().__init__(group)
        self.rect = pygame.Rect(*rect)
        self.image = load_image(os.path.join('sprites', 'buttons', filename))


class Pause:
    """Класс, ответственный за паузу в игре"""
    def __init__(self, screen, game):
        self.screen = screen
        self.game = game
        self.changing_music_volume = False  # изменяет ли игрок громкость музыки в данный момент
        self.changing_sounds_volume = False  # изменяет ли игрок громкость звука в данный момент
        self.volume_changing_bias = 0  # смещение курсора при регулировке громкости
        self.on_pause = False
        self.init_ui()

    def init_ui(self):
        self.menu = pygame.sprite.Group()
        self.menu_table = pygame.sprite.Sprite(self.menu)  # фоновая табличка меню паузы, на которой расположены кнопки
        self.menu_table.rect = pygame.Rect(660, 190, 600, 700)
        self.menu_table.image = load_image(os.path.join('sprites', 'pause_menu.png'))
        self.continue_button = Button((770, 300, 350, 90), 'continue.png', self.menu)
        self.music_slider = Button((1115, 483, 20, 40), 'slider.png', self.menu)
        self.sounds_slider = Button((1115, 619, 20, 40), 'slider.png', self.menu)
        self.exit_button = Button((770, 680, 350, 90), 'exit.png', self.menu)
        self.pause_button_rect = pygame.Rect(1800, 30, 80, 80)
        self.pause_button_image = load_image(os.path.join('sprites', 'buttons', 'pause.png'))

    def check_click_down(self, click):
        """Проверяет, нажал ли игрок на какую-либо из кнопок"""
        if self.on_pause:
            # Проверка на нажатие кнопок меню:
            if click.colliderect(self.continue_button):
                self.on_pause = False
            elif click.colliderect(self.music_slider):
                self.changing_music_volume = True
                self.volume_changing_bias = click.x - self.music_slider.rect.x
            elif click.colliderect(self.sounds_slider):
                self.changing_sounds_volume = True
                self.volume_changing_bias = click.x - self.sounds_slider.rect.x
            elif click.colliderect(self.exit_button):
                raise Exit
        else:
            # Проверка на нажатие кнопки паузы:
            if click.colliderect(self.pause_button_rect):
                self.on_pause = True

    def check_release(self, pos):
        """Осуществряет регулировку громкости музыки/звуков при перетаскивании бегунка"""
        if self.changing_music_volume or self.changing_sounds_volume:
            cursor_x_coord = pos[0] - self.volume_changing_bias
            if 800 > cursor_x_coord:
                next_pos = 800
            elif 1115 < cursor_x_coord:
                next_pos = 1115
            else:
                next_pos = cursor_x_coord
            volume = (next_pos - 799) / 315
            if self.changing_music_volume:
                self.music_slider.rect.x = next_pos
                self.game.background_fight_sound.set_volume(volume)
            else:
                self.sounds_slider.rect.x = next_pos
            self.menu.draw(self.screen)  # Если бегунок был передвинут, нужно перерисовать экран

    def check_click_up(self):
        self.changing_music_volume = False
        self.changing_sounds_volume = False

    def check_keypress(self, key):
        if self.on_pause:
            if key == pygame.K_TAB:
                self.on_pause = False
            elif key == pygame.K_END:
                raise Exit
        else:
            if key == pygame.K_TAB or key == pygame.K_END:
                self.on_pause = True

    def render(self):
        if self.on_pause:  # Если игра на паузе, отрисовывается меню паузы
            self.menu.draw(self.screen)
        else:  # Иначе отрисовывается кнопка паузы
            self.screen.blit(self.pause_button_image, (1800, 10))

    def __bool__(self):
        return self.on_pause


class OnlineGame:
    total_plants = 2  # Всего мест под спавн башен

    def __init__(self, screen):
        self.screen = screen
        self.plants = self.load_plants()
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(ADDRESS)
        self.data_from_server = pickle.loads(self.client.recv(1024))
        self.player_index = self.data_from_server
        if self.player_index == PLAYER_1:
            mirror_mob_icons()
        self.add_tower_menus = pygame.sprite.Group()
        self.main_towers_hp = {
            PLAYER_1: 1000,
            PLAYER_2: 1000
        }
        self.currency = 100
        self.spawn_mob_menu = SpawnMobMenu(self.player_index)
        self.background_fight_sound = pygame.mixer.Sound(os.path.join('sounds', 'Background_fight_sound.wav'))
        Thread(target=start_or_stop_music, args=(self.background_fight_sound,), daemon=True).start()
        self.pause = Pause(self.screen, self)
        self.buttons = pygame.sprite.Group()
        self.back_to_menu_button = Button((20, 20, 270, 100), 'back.png', self.buttons)

    def load_plants(self):
        """Загружает список мест для установки башен - плентов"""
        plants = pygame.sprite.Group()
        with open(os.path.join('maps', 'online_game_map', 'plants.csv'), 'r') as f:
            for line in f.readlines():
                x, y = tuple(map(lambda coord: float(coord) - 125, line.split()[0].split(';')))
                player = int(line.split()[1])
                plant_sprite = pygame.sprite.Sprite(plants)
                plant_sprite.rect = pygame.Rect(x, y, 250, 250)
                plant_sprite.image = PLANT_IMAGE
                plant_sprite.free = True
                plant_sprite.player = player
        return plants

    def on_click_down(self, pos):
        """Обрабатывает нажатие мыши"""
        click = pygame.Rect(*pos, 1, 1)
        self.pause.check_click_down(click)
        if not self.pause and self.data_from_server != 'Waiting for players':
            # Проверяем, нажал ли игрок на меню спавна мобов:
            self.spawn_mob_menu.check_click_down(click)
            # Проверяем, нажал ли игрок на меню спавна башен:
            for add_tower_menu in self.add_tower_menus:  # в self.add_tower_menus всегда не более одного меню
                add_tower_menu.check_click(click)
                self.add_tower_menus.empty()
                return
            # Проверяем, нажал ли игрок на плент/башню:
            for plant in self.plants:
                if click.colliderect(plant) and plant.player == self.player_index:
                    AddTowerMenu(plant, self.client, self.currency, self.add_tower_menus)
                    return
        elif self.data_from_server == 'Waiting for players':
            if click.colliderect(self.back_to_menu_button):
                raise Exit

    def on_release(self, pos):
        if self.pause:
            self.pause.check_release(pos)
        else:
            self.spawn_mob_menu.set_mouse_pos(pos)

    def on_click_up(self, pos):
        """Если игрок перетаскивал моба и отпустил его в зоне спавна, то возвращается команда спавна моба, иначе 'ok'"""
        if self.pause:
            self.pause.check_click_up()
            return 'ok'
        else:
            click = pygame.Rect(*pos, 1, 1)
            return self.spawn_mob_menu.check_click_up(click)

    def on_keypress(self, key):
        self.pause.check_keypress(key)

    def get_data_from_server(self, my_data='ok'):
        self.client.send(str.encode(my_data))  # 'ok' - дефолтное сообщение, не вызывает никакой реакции сервера
        data = []
        while True:  # получем пакеты пока не прийдут все нужные данные
            packet = self.client.recv(2048)
            data.append(packet)
            if len(packet) != 2048:  # если пакет не полный, значит он последний
                break
        try:
            data = pickle.loads(b"".join(data))
            return data
        except EOFError:
            raise OpponentExitError
        except ConnectionResetError:
            raise OpponentExitError

    def render_currency(self):
        """Отрисовывает количество валюты и иконку монеты в левом верхнем углу"""
        self.screen.blit(COIN_ICON, (20, 20))
        currency_text = CURRENCY_FONT.render(f': {self.currency}', True, (245, 189, 31))
        self.screen.blit(currency_text, (130, 40))

    def render_main_towers(self):
        self.screen.blit(MAINTOWER_IMAGE, (-50, 370))
        self.screen.blit(MAINTOWER_IMAGE, (1680, 380))
        # Отрисовка хп
        pygame.draw.rect(self.screen, 'blue', (45, 400, 110, 20))
        pygame.draw.rect(self.screen, 'blue', (1775, 410, 110, 20))
        draw_health_indicator(50, 405, self.main_towers_hp[PLAYER_1], 1000, 100, 10, self.screen)
        draw_health_indicator(1780, 415, self.main_towers_hp[PLAYER_2], 1000, 100, 10, self.screen)

    def draw_mob(self, player, mob_type, coords, state, animation_index, health):
        image = MOBS_DATA[mob_type]['animations'][state][animation_index]
        if player == 1:
            image = pygame.transform.flip(image, True, False)
        self.screen.blit(image, coords)
        # Отрисовка полоски ХП
        health_line_bias_x = MOBS_DATA[mob_type]['health_line_bias']['x']  # смещения полоски ХП относительно моба
        health_line_bias_y = MOBS_DATA[mob_type]['health_line_bias']['y']
        if player == 1:
            health_line_bias_x = MOBS_DATA[mob_type][state]['width'] - health_line_bias_x - 30
        draw_health_indicator(
            coords[0] + health_line_bias_x,
            coords[1] - health_line_bias_y,
            health,
            MOBS_DATA[mob_type]['health'],
            30,
            5,
            self.screen
        )

    def draw_tower(self, tower_type, coords, animation_index):
        image = TOWERS_SPRITES[tower_type][animation_index]
        self.screen.blit(image, coords)

    def draw_bullet(self, bullet_type, coords, angle, animation_index):
        image = pygame.transform.rotate(BULLETS_SPRITES[bullet_type][animation_index], math.degrees(angle))
        self.screen.blit(image, coords)

    def update_and_render(self, user_action='ok'):
        # Получение данных:
        self.data_from_server = self.get_data_from_server(user_action)
        mobs_data, towers_data, bullets_data = self.data_from_server[:3]
        if self.data_from_server != 'Waiting for players':
            # Установка полученных значений:
            self.main_towers_hp[PLAYER_1] = self.data_from_server[3]
            self.main_towers_hp[PLAYER_2] = self.data_from_server[4]
            self.currency = self.data_from_server[5] if self.player_index == PLAYER_1 else self.data_from_server[6]
            # Если противник поставил башню, то нужно удалить соответствующий плент:
            free_plants = [plant for plant in self.plants if plant.free]
            if len(towers_data) != self.total_plants - len(free_plants):
                towers_positions = [tower_data[1] for tower_data in towers_data]
                for plant in self.plants:
                    for x, y in towers_positions:
                        if plant.free and abs(plant.rect.x - x) <= 20 and abs(plant.rect.y - y) <= 100:
                            plant.free = False
                            plant.image = load_image(os.path.join('sprites', 'nothing.png'))
            # Отрисовка полученных объектов:
            self.screen.fill('black')
            self.screen.blit(MULTIPLAYER_MAP_IMAGE, (0, 0))
            self.render_main_towers()
            for mob_data in mobs_data:
                self.draw_mob(*mob_data)
            for tower_data in towers_data:
                self.draw_tower(*tower_data)
            for bullet_data in bullets_data:
                self.draw_bullet(*bullet_data)
            self.plants.draw(self.screen)
            self.add_tower_menus.draw(self.screen)
            for add_tower_menu in self.add_tower_menus:
                add_tower_menu.draw_buttons(self.screen)
            self.render_currency()
            self.spawn_mob_menu.draw(self.screen)
            self.pause.render()
            # Проверка на выигрыш/проигрыш:
            if self.main_towers_hp[self.player_index] <= 0:
                raise Lose
            elif self.main_towers_hp[opponent(self.player_index)] <= 0:
                raise Win
        else:
            self.screen.blit(WAITING_PLAYERS_SCREEN, (0, 0))
            self.buttons.draw(self.screen)


def play_online(screen, background_music=None):
    try:
        game = OnlineGame(screen)
        if background_music is not None:  # Если играла музыка главного меню, нужно её выключить
            Thread(target=start_or_stop_music, args=(background_music, True), daemon=True).start()
        time = pygame.time.Clock()
        fps_font = pygame.font.SysFont("Arial", 18)
        user_action = 'ok'
        running = True
        while running:
            game.update_and_render(user_action)
            user_action = 'ok'
            time.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    game.on_click_down(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    game.on_release(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    user_action = game.on_click_up(event.pos)
                elif event.type == pygame.KEYDOWN:
                    game.on_keypress(event.key)
                elif event.type == pygame.QUIT:
                    running = False
            fps_text = fps_font.render(str(int(time.get_fps())), True, (0, 255, 0))
            screen.blit(fps_text, (10, 0))
            pygame.display.flip()
    except Win:
        return 'win'
    except Exit:
        return 'exit'
    except Lose:
        return 'game_over'
    except OpponentExitError:
        return 'opponent_disconnected'
    except ConnectionResetError:
        return 'opponent_disconnected'
    except Exception:
        raise ServerError


if __name__ == '__main__':  # Предполагается что данный файл - это модуль проекта, но возможен и автономный запуск
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    play_online(screen)
    pygame.quit()
