import pygame
import os


# В этом файле загружаются все игровые звуки


sounds_dir = 'sounds'
splash_screen_sound = pygame.mixer.Sound(os.path.join(sounds_dir, 'Snake_load_sound.wav'))
background_menu_sound = pygame.mixer.Sound(os.path.join(sounds_dir, 'Background_sound.wav'))
background_fight_sound = pygame.mixer.Sound(os.path.join(sounds_dir, 'Background_fight_sound.wav'))
bow_shot_sound = pygame.mixer.Sound(os.path.join(sounds_dir, 'bow_shot.wav'))
cannon_shot_sound = pygame.mixer.Sound(os.path.join(sounds_dir, 'cannon_shot.wav'))
crystal_shot_sound = pygame.mixer.Sound(os.path.join(sounds_dir, 'crystal_shot.wav'))
mob_hit_sound = pygame.mixer.Sound(os.path.join(sounds_dir, 'mob_hit.wav'))

SOUNDS = {
    'bow_shot': bow_shot_sound,
    'cannon_shot': cannon_shot_sound,
    'crystal_shot': crystal_shot_sound,
    'mob_hit': mob_hit_sound
}


def change_sounds_volume(volume):
    bow_shot_sound.set_volume(volume)
    cannon_shot_sound.set_volume(volume)
    crystal_shot_sound.set_volume(volume)
    mob_hit_sound.set_volume(volume)
