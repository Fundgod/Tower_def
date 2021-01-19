from threading import Thread
import socket
import sys
import os
import time
import json
import math
import random
import pickle
from constants import *


PLAYER_1 = 1
PLAYER_2 = 2


def opponent(player):
    if player == PLAYER_1:
        return PLAYER_2
    return PLAYER_1


server = "0.0.0.0"  # "192.168.20.36"  # "127.0.0.1"
port = 44444

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.bind((server, port))
except socket.error:
    print('Socket error')
    sys.exit(1)

s.listen(2)
print('Waiting for connection')


def client_processing(conn, player):
    conn.send(pickle.dumps(player))
    while True:
        try:
            data = conn.recv(1024).decode().split()
            if not data:
                print('disconnected')
                break
            elif len(data) > 1:
                game.get_player_action(player, data[0], data[1:])
            conn.sendall(game.data_to_send)
            conn.sendall(b"")
        except Exception as err:
            print('Error:', err)
            break

    print('connection is lost')
    conn.close()


def clients_accepting():
    players = []
    while True:
        conn, addr = s.accept()

        print(f'Connected to {addr}')
        if len(players) < 2:
            if len(players) == 1:
                if players[0] == 1:
                    player_number = 2
                    players.append(player_number)
                else:  # players = [1]
                    player_number = 1
                    players.insert(1, player_number)
            else:  # len(players) = 0
                player_number = 1
                players.append(player_number)
            Thread(target=client_processing, args=[conn, player_number]).start()
        else:
            conn.sendall(bytes('abort'))
            conn.close()


def load_ways():
    ways = []
    path_to_roads = os.path.join('online_game_map', 'ways')
    for road in os.listdir(path_to_roads):
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


class Mob:
    def __init__(self, player, type, coords):
        self.player = player
        self.type = type
        self.coords = list(coords)
        self.way = self.define_way(self.coords)
        self.pos = 0
        self.state = 'move'
        self.load_info(self.type)
        self.resize('move')
        self.animation_index = 0.
        self.steps = [0, 0]
        self.tagged = False
        self.target = None
        self.killed = False

    def define_way(self, coords):
        x, y = coords
        if x < WIDTH / 3:
            road = 0
        elif x > WIDTH / 3 * 2:
            road = 2
        else:
            road = 1
        # FIXME
        road = 0
        way = WAYS[road][random.randint(0, 1)]
        if self.player == 1:
            way = way[::-1]
            for index, point in enumerate(way):
                if point[0] > x:
                    return tuple([coords] + list(way[index:]))
        else:  # self.player == 2:
            for index, point in enumerate(way):
                if point[0] < x:
                    return tuple([coords] + list(way[index:]))

    def load_info(self, type):
        with open(os.path.join('mobs', type, 'info.json'), 'r', encoding='utf-8') as info_file:
            self.info = json.load(info_file)
        self.velocity = self.info['velocity'] / FPS
        self.health = self.max_health = self.info['health']
        self.damage = self.info['damage']
        self.cost = self.info['cost']
        self.animation_speed = self.info[self.state]['animation_speed']
        self.animation_length = self.info[self.state]['animation_length']

    def get_position(self, time):
        """Возвращает координату, в которой окажется моб через заданное кол-во обновлений экрана"""
        # time - кол-во обновлений экрана
        index = self.pos
        steps = self.steps[1] - self.steps[0]
        way_len = len(self.way)
        while index < way_len - 1:
            if steps < time:
                time -= steps
            else:
                if index > self.pos:
                    way_point_1 = self.way[index - 1]
                else:
                    way_point_1 = self.coords
                way_point_2 = self.way[index]
                d_x, d_y = way_point_2[0] - way_point_1[0], way_point_2[1] - way_point_1[1]
                return (way_point_1[0] + d_x / steps * time,
                        way_point_1[1] + d_y / steps * time)
            start_point = self.way[index]
            index += 1
            end_point = self.way[index]
            d_x, d_y = end_point[0] - start_point[0], end_point[1] - start_point[1]
            steps = math.hypot(d_x, d_y) / self.velocity
        else:
            return self.way[-1]

    def update(self):
        self.animation_index = (self.animation_index + self.animation_speed) % self.animation_length
        if self.state == 'move' and self.health > 0:
            try:
                if self.steps[0] >= self.steps[1]:
                    start_point = self.way[self.pos]
                    self.pos += 1
                    end_point = self.way[self.pos]
                    d_x, d_y = end_point[0] - start_point[0], end_point[1] - start_point[1]
                    self.steps = [0, math.hypot(d_x, d_y) // self.velocity]
                    if self.steps[1] == 0:
                        self.steps[1] = 1
                    self.x_velocity = d_x / self.steps[1]
                    self.y_velocity = d_y / self.steps[1]
                self.steps[0] += 1
                self.coords[0] += self.x_velocity
                self.coords[1] += self.y_velocity
            except IndexError:
                self.attack(game.main_towers[opponent(self.player)])
        elif self.state == 'attack' and int(self.animation_index) == self.animation_length - 1:
            self.target.hit(self.damage)
            if self.target.health <= 0:
                self.target = None
                self.state = 'move'
                self.resize('move')
                self.animation_speed = self.info['move']['animation_speed']
                self.animation_index = 0 - self.animation_speed
                self.animation_length = self.info['move']['animation_length']
        elif self.state != 'death' and self.health <= 0:
            self.kill()
        elif self.state == 'death' and round(self.animation_index) == self.animation_length:
            self.killed = True

    def resize(self, state):
        """У разных анимаций разные размерыб поэтому каждый раз когда измеяется анимация нужно менять размер моба"""
        try:
            self.coords[0] += self.width / 2
            self.coords[1] += self.health / 2
        except AttributeError:
            pass
        self.width = self.info[state]['width']
        self.height = self.info[state]['height']
        self.coords[0] -= self.width / 2
        self.coords[1] -= self.health / 2

    def attack(self, target):
        if self.state != 'attack':
            self.target = target
            self.state = 'attack'
            self.resize('attack')
            self.animation_speed = self.info['attack']['animation_speed']
            self.animation_index = 0 - self.animation_speed
            self.animation_length = self.info['attack']['animation_length']

    def hit(self, damage):
        self.health -= damage

    def kill(self):
        self.state = 'death'
        self.resize('death')
        self.animation_index = 0.
        self.animation_length = self.info[self.state]['animation_length']
        self.animation_speed = self.info['death']['animation_speed']


class BowTower:
    cost = 50

    def __init__(self, player, coords, game):
        self.player = player
        self.coords = (coords[0] + 125, coords[1] - 25)
        self.game = game
        self.reloading = 0
        self.animation_index = 0.
        self.time_to_reload = 100
        self.shooting_range = 600
        self.damage = 10

    def update(self):
        if not self.reloading:
            for mob in sorted(self.game.mobs[opponent(self.player)], key=lambda mob_: not mob_.tagged):
                distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                if distance <= self.shooting_range and mob.state != 'death':
                    self.game.bullets.append(Bullet(self.coords, self.damage, 'arrow', distance, mob))
                    self.reloading = self.time_to_reload
                    return
        else:
            self.reloading -= 1

    def __str__(self):
        return 'bow'


class GunTower:
    cost = 100

    def __str__(self):
        return 'gun'


class RocketTower:
    cost = 150

    def __str__(self):
        return 'rocket'


class MainTower:
    health = 1000
    full_hp = 1000

    def __init__(self, player, game):
        self.player = player
        self.game = game
        if player == PLAYER_1:
            self.coords = (20, 500)
        else:  # player == PLAYER_2
            self.coords = (1900, 500)
        self.reloading = 0
        self.time_to_reload = 60
        self.shooting_range = 600
        self.damage = 10

    def update(self):
        if self.health > 0:
            if not self.reloading:
                for mob in sorted(self.game.mobs[opponent(self.player)], key=lambda mob_: not mob_.tagged):
                    distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                    if distance <= self.shooting_range and mob.state != 'death':
                        self.game.bullets.append(Bullet(self.coords, self.damage, 'arrow', distance, mob))
                        self.reloading = self.time_to_reload
                        return
            else:
                self.reloading -= 1
        else:
            # Здесь завершается игра и обоим игрокам показываются результаты
            del self

    def hit(self, damage):
        self.health -= damage


class Bullet:
    def __init__(self, start_coords, damage, type, distance_to_target, mob):
        self.type = type
        self.coords = list(start_coords)
        self.damage = damage
        self.distance_to_target = distance_to_target
        self.mob = mob
        self.velocity = 600 / FPS
        self.steps, self.steps_to_target = 0, None
        self.calculate_trajectory(mob, distance_to_target)

    def calculate_trajectory(self, mob, distance_to_target):
        """Рассчитывает маршрут полёта стрелы до противника и угол, под которым полетит стрела"""
        flight_time = distance_to_target / self.velocity
        self.end_coords = mob.get_position(flight_time)
        d_x, d_y = self.end_coords[0] - self.coords[0], self.end_coords[1] - self.coords[1]
        distance = math.hypot(d_x, d_y)
        self.velocity = distance / flight_time
        self.step = (d_x / distance * self.velocity,
                     d_y / distance * self.velocity)
        self.steps_to_target = distance / self.velocity
        self.angle = -math.atan(d_y / d_x)
        if d_x < 0:
            self.angle += math.pi

    def update(self):
        if self.steps < self.steps_to_target:
            self.coords[0] += self.step[0]
            self.coords[1] += self.step[1]
            self.steps += 1
        else:
            self.mob.hit(self.damage)
            del self


class OnlineGame:
    players_cache = {
        PLAYER_1: 100,
        PLAYER_2: 100
    }

    def __init__(self):
        self.mobs = {
            PLAYER_1: [],
            PLAYER_2: []
        }
        self.main_towers = {
            PLAYER_1: MainTower(PLAYER_1, self),
            PLAYER_2: MainTower(PLAYER_2, self)
        }
        self.towers = []
        self.bullets = []
        self.action_query = []
        self.data_to_send = None

    def start(self):
        while True:
            start_time = time.time()
            self.update()
            self.update_sending_data()
            sleep_time = TICK - (time.time() - start_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def update(self):
        if self.action_query:
            self.handle_player_action(*self.action_query.pop(-1))
        for mob in self.mobs[PLAYER_1]:
            if mob.killed:
                self.mobs[PLAYER_1].remove(mob)
                continue
            mob.update()
        for mob in self.mobs[PLAYER_2]:
            if mob.killed:
                self.mobs[PLAYER_2].remove(mob)
                continue
            mob.update()
            x, y = mob.coords
            for opponent_mob in self.mobs[PLAYER_1]:
                x1, y1 = opponent_mob.coords
                if math.hypot(x - x1, y - y1) < 80:
                    states = {mob.state, opponent_mob.state}
                    if y != y1 and 'move' in states and 'death' not in states:
                        y = (y + y1) / 2
                        mob.coords[1] = y
                        opponent_mob.coords[1] = y
                        mob.attack(opponent_mob)
                        opponent_mob.attack(mob)
        for tower in self.towers:
            tower.update()
        for bullet in self.bullets:
            bullet.update()

    def update_sending_data(self):
        mobs_data = []
        for mob in self.mobs[1] + self.mobs[2]:
            mobs_data.append((mob.player, mob.type, mob.coords, mob.state, int(mob.animation_index), mob.health))
        towers_data = []
        for tower in self.towers:
            towers_data.append((tower.player, tower.type, tower.coords, int(tower.animation_index)))
        bullets_data = []
        for bullet in self.bullets:
            bullets_data.append((bullet.type, bullet.coords, bullet.angle))
        self.data_to_send = pickle.dumps((tuple(mobs_data), tuple(towers_data), tuple(bullets_data),
                                          self.main_towers[1].health, self.main_towers[2].health))

    def handle_player_action(self, player, action, data):
        if action == 'spawn_mob':
            mob_type = data[0]
            coords = tuple(map(int, data[1].split(';')))
            if (player == 1 and coords[0] < WIDTH / 4) or (player == 2 and coords[0] > WIDTH / 4 * 3):
                self.mobs[player].append(Mob(player, mob_type, coords))
        elif action == 'spawn_tower':
            tower_type, coords = data
            tower = {'bow': BowTower, 'gun': GunTower, 'rocket': RocketTower}[tower_type]
            self.towers.append(tower(player, coords, self))
        else:  # action == 'mark_mob'
            for mob in self.mobs[player]:
                mob.tagged = False
            mob_index = data[0]
            if player == 1:
                self.mobs[player][mob_index].tagged = True
            else:  # player == 2
                self.mobs[player][mob_index].tagged = True

    def get_player_action(self, player, action, data):
        self.action_query.append((player, action, data))


if __name__ == '__main__':
    WAYS = load_ways()
    clients_accepting_thread = Thread(target=clients_accepting)
    clients_accepting_thread.start()
    game = OnlineGame()
    game.start()
