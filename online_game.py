import socket
import pickle
import math
from sprites import *


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
        self.plant.kill()
        Game.plants_count -= 1

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
    def __init__(self, rect, filename, group=None):
        super().__init__(group)
        self.rect = pygame.Rect(*rect)
        self.image = load_image(os.path.join('sprites', 'buttons', filename))


class Game:
    total_plants = 2
    plants_count = 2

    def __init__(self, screen):
        self.screen = screen
        self.plants = self.load_plants()
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(ADDRESS)
        data = pickle.loads(self.client.recv(1024))
        if isinstance(data, int):
            self.player_index = data
        else:
            self.handle_server_abort()
        remake_mob_icons(self.player_index)
        self.add_tower_menus = pygame.sprite.Group()
        self.main_towers_hp = {
            PLAYER_1: 1000,
            PLAYER_2: 1000
        }
        self.currency = 100
        self.spawn_mob_menu = SpawnMobMenu(self.player_index)

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
        self.spawn_mob_menu.check_click_down(click)
        for add_tower_menu in self.add_tower_menus:
            add_tower_menu.check_click(click)
            self.close_add_tower_menu()
            return
        self.close_add_tower_menu()
        for plant in self.plants:
            if click.colliderect(plant) and plant.free and plant.player == self.player_index:
                AddTowerMenu(plant, self.client, self.currency, self.add_tower_menus)
                return

    def on_release(self, pos):
        self.spawn_mob_menu.set_mouse_pos(pos)

    def on_click_up(self, pos):
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
        data = pickle.loads(b"".join(data))
        return data

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
        data = self.get_data_from_server(user_action)
        if data != 'Waiting for players':
            # Установка полученных значений:
            self.main_towers_hp[PLAYER_1] = data[3]
            self.main_towers_hp[PLAYER_2] = data[4]
            self.currency = data[5] if self.player_index == PLAYER_1 else data[6]
            # Если противник поставил башню, то нужно удалить соответствующий плент:
            if len(data[1]) != Game.total_plants - Game.plants_count:
                towers_positions = [tower_data[1] for tower_data in data[1]]
                for plant in self.plants:
                    for tower_position in towers_positions:
                        print()
                        if abs(plant.rect.x - tower_position[0]) <= 20 and abs(plant.rect.y - tower_position[1]) <= 100:
                            self.plants.remove(plant)
                            Game.plants_count -= 1
            # Отрисовка полученных объектов:
            self.screen.fill('black')
            self.screen.blit(MULTIPLAYER_MAP_IMAGE, (0, 0))
            self.render_main_towers()
            for mob_data in data[0]:
                draw_mob(*mob_data, self.screen)
            for tower_data in data[1]:
                draw_tower(*tower_data, self.screen)
            for bullet_data in data[2]:
                draw_bullet(*bullet_data, self.screen)
            self.plants.draw(self.screen)
            self.add_tower_menus.draw(self.screen)
            for add_tower_menu in self.add_tower_menus:
                add_tower_menu.draw_buttons(self.screen)
            self.render_currency()
            self.spawn_mob_menu.draw(self.screen)
        else:
            self.screen.blit(WAITING_PLAYERS_SCREEN, (0, 0))

    def close_add_tower_menu(self):
        for add_tower_menu in self.add_tower_menus:
            add_tower_menu.kill()

    def handle_server_abort(self):
        print('Here should be a screen with title like: server overflow, wait a bit and try again')
        pygame.quit()
        sys.exit(0)


def play_online(screen):
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


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    play_online(screen)
    pygame.quit()
