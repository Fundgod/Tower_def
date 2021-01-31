from constants import PLAYER_1, PLAYER_2
import os
import math


# В этом файле лежат функции общего назначения, используемые в различных модулях проекта


def opponent(player):
    if player == PLAYER_1:
        return PLAYER_2
    return PLAYER_1


def load_ways(map_dir):
    """Загружает пути для мобов на конкретной карте из csv файла и возмращает кортеж из точек маршрута"""
    ways = []
    path_to_roads = os.path.join(map_dir, 'ways')
    for road in sorted(os.listdir(path_to_roads)):
        ways.append([])
        path_to_ways = os.path.join(path_to_roads, road)
        for way_file in os.listdir(path_to_ways):
            if '.csv' in way_file:
                with open(os.path.join(path_to_ways, way_file), 'r') as f:
                    ways[-1].append([])
                    for line in f.readlines():
                        ways[-1][-1].append(tuple(map(float, line.rstrip().split(';'))))
                    ways[-1][-1] = tuple(ways[-1][-1])
    return ways


def calculate_distance_between_points(x, y, x1, y1):
    return math.hypot(x - x1, y - y1)
