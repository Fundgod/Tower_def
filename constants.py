SIZE = WIDTH, HEIGHT = 1920, 1080
PLAYER_1 = 1
PLAYER_2 = 2
FPS = 60
TICK = 1 / 60
MASK = 'mask'
SKILLET = 'skillet'
STONE_GOLEM = 'stone_golem'
BOAR_WARRIOR = 'boar_warrior'
HORNY_DOG = 'horny_dog'
CRYSTAL_GOLEM = 'crystal_golem'
MOBS = (MASK, SKILLET, STONE_GOLEM, BOAR_WARRIOR, HORNY_DOG, CRYSTAL_GOLEM)
CACHE_VELOCITY = 1 / 10
MAINTOWERS_POSITIONS = {
    1: (20, 670),  # Для первого уровня
    2: (-10, 340),  # Для второго уровня
    3: (-10, 353)  # Для третьего уровня
}
SPAWN_DATA = {
    1: (
        (1, 0, SKILLET),
        (1, 0, SKILLET),
        (1, 0, SKILLET),
        (12, 0, SKILLET),
        (1, 0, SKILLET),
        (1, 0, SKILLET),
        (1, 0, SKILLET),
        (1, 0, CRYSTAL_GOLEM),
        (1, 0, SKILLET),
        (1, 0, SKILLET),
        (2, 0, CRYSTAL_GOLEM),
        (4, 0, HORNY_DOG),
        (12, 0, BOAR_WARRIOR),
        (2, 0, MASK),
        (3, 0, STONE_GOLEM),
        (1, 0, HORNY_DOG),
        (1, 0, HORNY_DOG),
        (1, 0, CRYSTAL_GOLEM),
        (2, 0, SKILLET),
        (3, 0, BOAR_WARRIOR)
    ),
    2: (
        (1, 0, STONE_GOLEM),
        (1, 0, STONE_GOLEM),
        (1, 0, STONE_GOLEM),
        (1, 0, STONE_GOLEM),
        (1, 0, STONE_GOLEM),
        (2, 1, CRYSTAL_GOLEM),
        (15, 1, BOAR_WARRIOR),
        (2, 0, MASK),
        (3, 1, SKILLET),
        (2, 1, SKILLET),
        (0, 1, SKILLET),
        (1, 1, SKILLET),
        (1, 1, SKILLET),
        (1, 1, SKILLET),
        (1, 1, SKILLET),
        (1, 1, SKILLET),
        (1, 1, SKILLET),
        (16, 1, SKILLET),
        (1, 0, BOAR_WARRIOR),
        (1, 0, BOAR_WARRIOR),
        (1, 0, HORNY_DOG),
        (1, 1, STONE_GOLEM),
        (1, 1, STONE_GOLEM),
        (1, 1, STONE_GOLEM),
    ),
    3: (
        (1, 0, STONE_GOLEM),
        (2, 1, CRYSTAL_GOLEM),
        (3, 0, HORNY_DOG),
        (1, 1, BOAR_WARRIOR),
        (2, 0, MASK),
        (3, 1, SKILLET),
        (0.5, 0, CRYSTAL_GOLEM),
        (0, 1, STONE_GOLEM),
        (0.5, 0, CRYSTAL_GOLEM),
        (0, 1, STONE_GOLEM),
        (0.5, 0, CRYSTAL_GOLEM),
        (0, 1, STONE_GOLEM),
        (1, 0, HORNY_DOG),
        (2, 1, SKILLET)
    )
}