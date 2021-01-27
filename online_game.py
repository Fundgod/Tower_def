import socket
import pickle
import math
from sprites import *
from exceptions import *
from time import sleep
from threading import Thread


def load_mobs_data():
    data = {}
    animations = load_mob_animations()
    for mob in MOBS:
        with open(os.path.join('mobs', mob, 'info.json'), 'r', encoding='utf-8') as info_file:
            data[mob] = json.load(info_file)
        data[mob]['animations'] = animations[mob]
    return data


def load_road_zones():
    zones = {
        PLAYER_1: [],
        PLAYER_2: []
    }
    path_to_roads = os.path.join('online_game_map', 'ways')
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


SERVER = '127.0.0.1'  # '109.226.242.226'  # '127.0.0.1'
PORT = 4444
ADDRESS = (SERVER, PORT)
MOBS_DATA = load_mobs_data()
ROAD_ZONES = load_road_zones()


def remake_mob_icons(player):
    if player == PLAYER_1:
        for mob in MOB_ICONS.keys():
            MOB_ICONS[mob] = pygame.transform.flip(MOB_ICONS[mob], True, False)


def draw_mob(player, mob_type, coords, state, animation_index, health, screen):
    image = MOBS_DATA[mob_type]['animations'][state][animation_index]
    if player == 1:
        image = pygame.transform.flip(image, True, False)
    screen.blit(image, coords)
    # Отрисовка полоски ХП
    health_line_bias_x = MOBS_DATA[mob_type]['health_line_bias']['x']
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
        screen
    )


def draw_tower(tower_type, coords, animation_index, screen):
    image = TOWERS_SPRITES[tower_type][animation_index]
    screen.blit(image, coords)


def draw_bullet(bullet_type, coords, angle, animation_index, screen):
    image = pygame.transform.rotate(BULLETS_SPRITES[bullet_type][animation_index], math.degrees(angle))
    screen.blit(image, coords)


def draw_health_indicator(x, y, health, max_health, indicator_width, indicator_height, screen):
    pygame.draw.rect(screen, 'red', (x, y, indicator_width, indicator_height))
    pygame.draw.rect(screen, 'green', (x, y, indicator_width * health / max_health, indicator_height))


def start_or_stop_music(music, stop=False):
    for i in range(0, 10):
        music.set_volume(1 + 0.1 * stop * i)
        sleep(0.1)
    if stop:
        music.stop()


class AddTowerMenu(pygame.sprite.Sprite):
    width = 400
    height = 180

    def __init__(self, plant, client, currency, group):
        super().__init__(group)
        self.coords = plant.rect.x, plant.rect.y
        self.client = client
        self.currency = currency
        self.plant = plant
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
        self.cost1 = SMALL_FONT.render('50', True, (245, 189, 31))
        self.cannon_tower_button = Button(
            (self.coords[0] + 95, self.coords[1] - 60, 80, 80),
            'cannon_tower_icon.png',
            self.buttons
        )
        self.cost2 = SMALL_FONT.render('100', True, (245, 189, 31))
        self.crystal_tower_button = Button(
            (self.coords[0] + 195, self.coords[1] - 60, 80, 80),
            'crystal_tower_icon.png',
            self.buttons
        )
        self.cost3 = SMALL_FONT.render('150', True, (245, 189, 31))

    def check_click(self, click):
        if click.colliderect(self.bow_tower_button):
            if self.currency >= 50:
                self.spawn_tower('bow')
        elif click.colliderect(self.cannon_tower_button):
            if self.currency >= 100:
                self.spawn_tower('cannon')
        elif click.colliderect(self.crystal_tower_button):
            if self.currency >= 150:
                self.spawn_tower('crystal')

    def spawn_tower(self, tower):
        self.client.send(str.encode(f"spawn_tower {tower} {';'.join(map(str, self.coords))}"))
        self.plant.free = False
        self.plant.image = load_image(os.path.join('sprites', 'nothing.png'))

    def draw_buttons(self, surface):
        self.buttons.draw(surface)
        costs_height = self.coords[1] + 20
        surface.blit(self.cost1, (self.coords[0] + 15, costs_height))
        surface.blit(self.cost2, (self.coords[0] + 105, costs_height))
        surface.blit(self.cost3, (self.coords[0] + 205, costs_height))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 45, costs_height))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 150, costs_height))
        surface.blit(SMALL_COIN_ICON, (self.coords[0] + 250, costs_height))


class SpawnMobMenu(pygame.sprite.Group):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.background_image = pygame.sprite.Sprite(self)
        self.background_image.rect = pygame.Rect(0, 820, 319, 267)
        self.background_image.image = load_image(os.path.join('sprites', 'spawn_mob_menu.png'))
        self.spawnable_zone = pygame.sprite.Sprite()
        self.spawnable_zone.rect = pygame.Rect(0, 0, 500, 1080)
        if player == PLAYER_2:
            self.spawnable_zone.rect.x += 1520
        self.spawnable_zone.image = load_image(os.path.join('sprites', 'mob_spawn_zone.png'))
        x_bias = 0
        if player == PLAYER_2:
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
        self.selected_mob = None
        self.mouse_pos = (0, 0)

    def set_mouse_pos(self, pos):
        self.mouse_pos = pos

    def check_click_down(self, click):
        for button in self.buttons_dict.keys():
            if click.colliderect(button):
                self.selected_mob = self.buttons_dict[button]
                self.add(self.spawnable_zone)

    def check_click_up(self, click_rect):
        click = pygame.sprite.Sprite()
        click.rect = click_rect
        click.mask = pygame.mask.Mask((1, 1), True)
        selected_mob = self.selected_mob
        self.selected_mob = None
        self.remove(self.spawnable_zone)
        for road_index, road_zone in enumerate(ROAD_ZONES[self.player]):
            if selected_mob and pygame.sprite.collide_mask(click, road_zone):
                return f'spawn_mob {selected_mob} {road_index} {click.rect.x};{click.rect.y}'
        return 'ok'

    def draw(self, screen):
        super().draw(screen)
        if self.selected_mob:
            screen.blit(MOB_ICONS[self.selected_mob], self.mouse_pos)


class Button(pygame.sprite.Sprite):
    def __init__(self, rect, filename, group):
        super().__init__(group)
        self.rect = pygame.Rect(*rect)
        self.image = load_image(os.path.join('sprites', 'buttons', filename))


class Pause:
    def __init__(self, screen, background_fight_sound):
        self.screen = screen
        self.game = background_fight_sound
        self.menu = pygame.sprite.Group()
        self.menu_table = pygame.sprite.Sprite(self.menu)
        self.menu_table.rect = pygame.Rect(660, 190, 600, 700)
        self.menu_table.image = load_image(os.path.join('sprites', 'pause_menu.png'))
        self.continue_button = Button((770, 300, 350, 90), 'continue.png', self.menu)
        self.music_slider = Button((1115, 483, 20, 40), 'slider.png', self.menu)
        self.sounds_slider = Button((1115, 619, 20, 40), 'slider.png', self.menu)
        self.exit_button = Button((770, 680, 350, 90), 'exit.png', self.menu)
        self.pause_button_rect = pygame.Rect(1800, 30, 80, 80)
        self.pause_button_image = load_image(os.path.join('sprites', 'buttons', 'pause.png'))
        self.changing_music_volume = False
        self.changing_sounds_volume = False
        self.volume_changing_bias = 0
        self.on_pause = False

    def check_click_down(self, click):
        if self.on_pause:
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
            if click.colliderect(self.pause_button_rect):
                self.on_pause = True

    def check_release(self, pos):
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
        elif self.changing_sounds_volume:
            self.sounds_slider.rect.x = next_pos
            #self.background_fight_sound.set_volume(volume)
        self.menu.draw(self.screen)

    def check_click_up(self):
        self.changing_music_volume = False
        self.changing_sounds_volume = False

    def render(self):
        if self.on_pause:
            self.menu.draw(self.screen)
        else:
            self.screen.blit(self.pause_button_image, (1800, 10))

    def __bool__(self):
        return self.on_pause


class Game:
    total_plants = 2

    def __init__(self, screen):
        self.screen = screen
        self.plants = self.load_plants()
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(ADDRESS)
        self.data_from_server = pickle.loads(self.client.recv(1024))
        self.player_index = self.data_from_server
        remake_mob_icons(self.player_index)
        self.add_tower_menus = pygame.sprite.Group()
        self.main_towers_hp = {
            PLAYER_1: 1000,
            PLAYER_2: 1000
        }
        self.currency = 100
        self.spawn_mob_menu = SpawnMobMenu(self.player_index)
        self.background_fight_sound = pygame.mixer.Sound(os.path.join('sounds', 'Background_fight_sound.wav'))
        self.background_fight_sound.set_volume(0)
        self.background_fight_sound.play()
        Thread(target=start_or_stop_music, args=(self.background_fight_sound,), daemon=True).start()
        self.pause = Pause(self.screen, self)
        self.buttons = pygame.sprite.Group()
        self.back_button = Button((20, 20, 270, 100), 'back.png', self.buttons)

    def load_plants(self):
        plants = pygame.sprite.Group()
        plant_image = load_image('sprites/plant.png')
        with open(os.path.join('online_game_map', 'plants.csv'), 'r') as f:
            for line in f.readlines():
                x, y = tuple(map(lambda coord: float(coord) - 125, line.split()[0].split(';')))
                player = int(line.split()[1])
                plant_sprite = pygame.sprite.Sprite(plants)
                plant_sprite.rect = pygame.Rect(x, y, 250, 250)
                plant_sprite.image = plant_image
                plant_sprite.free = True
                plant_sprite.player = player
        return plants

    def on_click_down(self, pos):
        click = pygame.Rect(*pos, 1, 1)
        self.pause.check_click_down(click)
        if not self.pause and self.data_from_server != 'Waiting for players':
            self.spawn_mob_menu.check_click_down(click)
            for add_tower_menu in self.add_tower_menus:
                add_tower_menu.check_click(click)
                self.close_add_tower_menu()
                return
            self.close_add_tower_menu()
            for plant in self.plants:
                if click.colliderect(plant) and plant.player == self.player_index:
                    AddTowerMenu(plant, self.client, self.currency, self.add_tower_menus)
                    return
        elif self.data_from_server == 'Waiting for players':
            if click.colliderect(self.back_button):
                raise Exit

    def on_release(self, pos):
        if self.pause:
            self.pause.check_release(pos)
        else:
            self.spawn_mob_menu.set_mouse_pos(pos)

    def on_click_up(self, pos):
        if self.pause:
            self.pause.check_click_up()
            return 'ok'
        else:
            click = pygame.Rect(*pos, 1, 1)
            return self.spawn_mob_menu.check_click_up(click)

    def get_data_from_server(self, my_data='ok'):
        self.client.send(str.encode(my_data))
        data = []
        while True:
            packet = self.client.recv(2048)
            data.append(packet)
            if len(packet) != 2048:
                break
        try:
            data = pickle.loads(b"".join(data))
            return data
        except EOFError:
            raise OpponentExitError

    def render_currency(self):
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

    def update_and_render(self, user_action='ok'):
        # Получение данных:
        self.data_from_server = self.get_data_from_server(user_action)
        if self.data_from_server != 'Waiting for players':
            # Установка полученных значений:
            self.main_towers_hp[PLAYER_1] = self.data_from_server[3]
            self.main_towers_hp[PLAYER_2] = self.data_from_server[4]
            self.currency = self.data_from_server[5] if self.player_index == PLAYER_1 else self.data_from_server[6]
            # Если противник поставил башню, то нужно удалить соответствующий плент:
            if len(self.data_from_server[1]) != Game.total_plants - len([plant for plant in self.plants if plant.free]):
                towers_positions = [tower_data[1] for tower_data in self.data_from_server[1]]
                for plant in self.plants:
                    for x, y in towers_positions:
                        if plant.free and abs(plant.rect.x - x) <= 20 and abs(plant.rect.y - y) <= 100:
                            plant.free = False
                            plant.image = load_image(os.path.join('sprites', 'nothing.png'))
            # Отрисовка полученных объектов:
            self.screen.fill('black')
            self.screen.blit(MULTIPLAYER_MAP_IMAGE, (0, 0))
            self.render_main_towers()
            for mob_data in self.data_from_server[0]:
                draw_mob(*mob_data, self.screen)
            for tower_data in self.data_from_server[1]:
                draw_tower(*tower_data, self.screen)
            for bullet_data in self.data_from_server[2]:
                draw_bullet(*bullet_data, self.screen)
            self.plants.draw(self.screen)
            self.add_tower_menus.draw(self.screen)
            for add_tower_menu in self.add_tower_menus:
                add_tower_menu.draw_buttons(self.screen)
            self.render_currency()
            self.spawn_mob_menu.draw(self.screen)
            self.pause.render()
        else:
            self.screen.blit(WAITING_PLAYERS_SCREEN, (0, 0))
            self.buttons.draw(self.screen)

    def close_add_tower_menu(self):
        for add_tower_menu in self.add_tower_menus:
            add_tower_menu.kill()


def play_online(screen):
    try:
        game = Game(screen)
        running = True
        time = pygame.time.Clock()
        fps_font = pygame.font.SysFont("Arial", 18)
        user_action = 'ok'
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
    except Exception:
        raise ServerError


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    play_online(screen)
    pygame.quit()
