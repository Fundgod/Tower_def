SIZE = WIDTH, HEIGHT = 1920, 1080
FPS = 60
MASK = 'mask'
SKILLET = 'skillet'
STONE_GOLEM = 'stone_golem'
BOAR_WARRIOR = 'boar_warrior'
HORNY_DOG = 'horny_dog'
CRYSTAL_GOLEM = 'crystal_golem'

MOBS = {
    1: (
        #(1, 0, STONE_GOLEM),
        #(2, 0, CRYSTAL_GOLEM),
        (1, 0, HORNY_DOG),
        #(1, 0, BOAR_WARRIOR),
        #(2, 0, MASK),
        #(3, 0, SKILLET),
        #(1, 0, HORNY_DOG),
        #(2, 0, SKILLET),
        #(3, 0, BOAR_WARRIOR)
    ),
    2: (
        (1, 0, STONE_GOLEM),
        (2, 1, CRYSTAL_GOLEM),
        (3, 0, HORNY_DOG),
        (1, 1, BOAR_WARRIOR),
        (2, 0, MASK),
        (3, 1, SKILLET),
        (1, 0, HORNY_DOG),
        (2, 1, SKILLET),
        (3, 0, BOAR_WARRIOR)
    )
}