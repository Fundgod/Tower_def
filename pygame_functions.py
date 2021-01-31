import pygame
from time import sleep


def draw_health_indicator(x, y, health, max_health, indicator_width, indicator_height, screen):
    """Отрисовывает полоску жизни"""
    if health < 0:
        health = 0
    pygame.draw.rect(screen, 'red', (x, y, indicator_width, indicator_height))
    pygame.draw.rect(screen, 'green', (x, y, indicator_width * health / max_health, indicator_height))


def start_or_stop_music(music, stop=False):
    """Плавно включает/выключает музыку"""
    max_volume = 10
    if stop:
        max_volume = int(music.get_volume() * 10)
    else:
        music.play()
    try:
        for i in range(0, max_volume):
            music.set_volume(1 + 0.1 * stop * i)
            sleep(0.1)
        if stop:
            music.stop()
    except pygame.error:
        return


def fade(screen, image, speed=1.):
    """Плавно отрисовывает картинку"""
    alpha = 0
    while alpha < 255:
        image.set_alpha(int(alpha))
        screen.blit(image, (0, 0))
        pygame.display.update()
        pygame.time.delay(5)
        alpha += speed
        for event in pygame.event.get():
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                image.set_alpha(255)
                screen.blit(image, (0, 0))
                return
