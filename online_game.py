import pygame
import socket
import pickle
import os
import json
from constants import *
from main import load_image, load_animation, load_mob_animations, load_bullet_sprites, draw_health_indicator


def load_mobs_data():
    data = {}
    animations = load_mob_animations()
    for mob in (MASK, SKILLET, STONE_GOLEM, BOAR_WARRIOR, HORNY_DOG, CRYSTAL_GOLEM):
        with open(os.path.join('mobs', mob, 'info.json'), 'r', encoding='utf-8') as info_file:
            data[mob] = json.load(info_file)
        data[mob]['animations'] = animations[mob]
    return data


SERVER =   # '127.0.0.1'
PORT = 4444
ADDRESS = (SERVER, PORT)

def draw_mob(player, mob_type, coords, state, animation_index, health, screen):
    x, y = coords
    image = MOBS_DATA[mob_type]['animations'][state][animation_index]
    if player == 1:
        image = pygame.transform.flip(image, True, False)
    mob_coords = (x - MOBS_DATA[mob_type][state]['width'] / 2, y - MOBS_DATA[mob_type][state]['height'] / 2)
    screen.blit(image, mob_coords)
    draw_health_indicator(
        x - MOBS_DATA[mob_type]['health_line_bias']['x'],
        mob_coords[1] - MOBS_DATA[mob_type]['health_line_bias']['y'],
        health,
        MOBS_DATA[mob_type]['health'],
        30,
        screen
    )


class Game:
    def __init__(self, screen):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(ADDRESS)
        self.player_index = pickle.loads(self.client.recv(2048))
        self.screen = screen

    def on_click(self, pos):
        click = pygame.Rect(*pos, 1, 1)

    def get_data_from_server(self, my_data='ok'):
        self.client.send(str.encode(my_data))
        data = []
        while True:
            packet = self.client.recv(2048)
            data.append(packet)
            if len(packet) != 2048:
                break
        data_from_server = pickle.loads(b"".join(data))
        #data_from_server = pickle.loads(self.client.recv(2048))
        return data_from_server

    def update_and_render(self, user_action='ok'):
        # Получение данных:
        data = self.get_data_from_server(user_action)
        # Отрисовка полученных объектов:
        screen.fill('black')
        self.screen.blit(MAP_IMAGE, (0, 0))
        for mob_data in data[0]:
            draw_mob(*mob_data, self.screen)
        for tower in data[1]:
            pass
        for bullet in data[2]:
            pass


def play_online(screen):
    game = Game(screen)
    running = True
    time = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 18)
    while running:
        time.tick(FPS)
        user_action = 'ok'
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos
                if event.button == 1:
                    user_action = f'spawn_mob skillet {x};{y}'
                elif event.button == 2:
                    user_action = f'spawn_mob stone_golem {x};{y}'
                elif event.button == 3:
                    user_action = f'spawn_mob mask {x};{y}'
                elif event.button == 4:
                    user_action = f'spawn_mob boar_warrior {x};{y}'
            elif event.type == pygame.QUIT:
                running = False
        game.update_and_render(user_action)
        fps_text = font.render(str(int(time.get_fps())), True, (0, 255, 0))
        screen.blit(fps_text, (10, 0))
        pygame.display.flip()
    pygame.quit()


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    MOBS_DATA = load_mobs_data()
    MAP_IMAGE = load_image(os.path.join('online_game_map', 'image.png'))
    play_online(screen)
