import pygame
import json
import sys
import os
from constants import *


# В этом файле загружаются спрайты для игры


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
    """Разрезает картинку на кадры шириной width и высотой height"""
    image = load_image(os.path.join(path_to_image))
    x, y = image.get_size()
    frames = []
    for i in range(y // height):
        for j in range(x // width):
            frame_location = (width * j, height * i)
            frame = image.subsurface(pygame.Rect(frame_location, (width, height)))
            frames.append(frame)
    return frames


def load_towers_sprites():
    """Загружает словарь анимаций всех башен"""
    towers_sprites = {}
    path = os.path.join('sprites', 'towers')
    for tower in os.listdir(path):
        towers_sprites[tower] = []
        for sprite in sorted(os.listdir(os.path.join(path, tower)), key=lambda x: int(x.split('.')[0])):
            towers_sprites[tower].append(load_image(os.path.join(path, tower, sprite)))
    return towers_sprites


def load_mob_animations():
    """Загружает словарь анимаций всех мобов"""
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


def load_mob_icons():
    """Загружает словарь иконок мобов"""
    mob_icons = {}
    path = 'mobs'
    for mob in MOBS:
        mob_icons[mob] = load_image(os.path.join(path, mob, 'sprites', 'icon.png'))
    return mob_icons


def load_bullets_sprites():
    """Загружает словарь анимаций всех снарядов"""
    bullets_sprites = {}
    path = os.path.join('sprites', 'bullets')
    for bullet, width, height in (('arrow', 25, 25), ('shell', 25, 25), ('sphere', 40, 25)):
        bullets_sprites[bullet] = load_animation(os.path.join(path, bullet + '.png'), width, height)
    return bullets_sprites


pygame.init()
pygame.display.set_mode(SIZE)

MOB_ANIMATIONS = load_mob_animations()
BULLETS_SPRITES = load_bullets_sprites()
MAINTOWER_IMAGE = pygame.transform.scale(load_image(os.path.join('sprites', 'main_tower.png')), (300, 300))
ADD_TOWER_MENU_IMAGE = load_image(os.path.join('sprites', 'add_tower_menu.png'))
TOWERS_SPRITES = load_towers_sprites()
PLANT_IMAGE = load_image('sprites/plant.png')
COIN_ICON = load_image(os.path.join('sprites', 'coin.png'))
SMALL_COIN_ICON = pygame.transform.scale(COIN_ICON, (20, 20))
MOB_MARK_SPRITE = load_image(os.path.join('sprites', 'mark.png'))
CURRENCY_FONT = pygame.font.SysFont('Arial', 60)
MOB_COST_FONT = pygame.font.SysFont('Arial', 25)
BLACK_SCREEN = load_image(os.path.join('sprites', 'black_screen.png'))
# Спрайты для мультиплеера:
MULTIPLAYER_MAP_IMAGE = load_image(os.path.join('maps', 'online_game_map', 'image.png'))
MOB_ICONS = load_mob_icons()
WAITING_PLAYERS_SCREEN = load_image(os.path.join('sprites', 'waiting_players_screen.png'))
SERVER_ERROR = load_image(os.path.join('sprites', 'server_error.png'))