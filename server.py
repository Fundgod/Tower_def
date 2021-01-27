import socket
import sys
import os
import time
import json
import math
import random
import pickle
from threading import Thread
from constants import *


def opponent(player):
    if player == PLAYER_1:
        return PLAYER_2
    return PLAYER_1


server = "0.0.0.0"
port = 4444

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.bind((server, port))
except socket.error:
    print('Socket error')
    sys.exit(1)

s.listen(6)
print('Waiting for connection')


class Room:
    def __init__(self, player_1_connection, rooms):
        self.player_1 = (PLAYER_1, player_1_connection)
        self.rooms = rooms
        self.player_2 = None
        self.game = OnlineGame()

    def add_player(self, player_2_connection):
        self.player_2 = (PLAYER_2, player_2_connection)

    def start_game(self):
        Thread(target=self.game.start).start()

    def is_full(self):
        if self.player_2 is not None:
            return True
        return False

    def close(self):
        if self.player_1 is not None:
            self.player_1[1].close()
            self.player_1 = None
            print('player 1 disconnected succesfully')
        if self.player_2 is not None:
            self.player_2[1].close()
            self.player_2 = None
            print('player 2 disconnected succesfully')
        if self in self.rooms:
            self.rooms.remove(self)


def clients_accepting():
    rooms = []
    while True:
        conn, addr = s.accept()
        print(f'Connected to {addr}')
        if rooms and not rooms[-1].is_full() == 1:
            room = rooms[-1]
            room.add_player(conn)
            Thread(target=client_processing, args=[conn, PLAYER_2, room]).start()
            room.start_game()
        else:
            room = Room(conn, rooms)
            rooms.append(room)
            Thread(target=client_processing, args=[conn, PLAYER_1, room]).start()


def client_processing(conn, player, room):
    game = room.game
    try:
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
        room.close()
    except:
        conn.close()
        room.close()


def load_ways():
    ways = []
    path_to_roads = os.path.join('maps', 'online_game_map', 'ways')
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


class Mob:
    def __init__(self, player, type, road_index, coords, opponent_main_tower):
        self.player = player
        self.type = type
        self.road = road_index
        self.coords = list(coords)
        self.opponent_main_tower = opponent_main_tower
        self.way = self.define_way()
        #self.way, self.road = self.define_way(self.coords)
        self.pos = 0
        self.load_info(self.type)
        self.set_state('move')
        self.steps = [0, 0]
        self.tagged = False
        self.target = None

    def define_way(self):
        way = (P_1_WAYS if self.player == PLAYER_1 else P_2_WAYS)[self.road][random.randint(0, 1)]
        # Далее определяется точка с которой начинается путь:
        if self.player == 1:
            direction = 1
        else:
            direction = -1
        for index, point in enumerate(way):
            if (point[0] - self.coords[0]) * direction > 100:
                return tuple([self.coords] + list(way[index:]))

    def load_info(self, type):
        with open(os.path.join('mobs', type, 'info.json'), 'r', encoding='utf-8') as info_file:
            self.info = json.load(info_file)
        self.velocity = self.info['velocity'] / FPS
        self.health = self.max_health = self.info['health']
        self.damage = self.info['damage']
        self.cost = self.info['cost']

    def set_state(self, state):
        self.state = state
        self.half_width = self.info[self.state]['width'] / 2
        self.half_height = self.info[self.state]['height'] / 2
        self.animation_speed = self.info[state]['animation_speed']
        self.animation_length = self.info[state]['animation_length']
        self.animation_index = 0.

    def get_coords(self):
        return (self.coords[0] - self.half_width,
                self.coords[1] - self.half_height)

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
        if self.health <= 0 and self.state != 'death':
            self.set_state('death')
        if self.state == 'move':
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
                self.attack(self.opponent_main_tower)
        elif self.state == 'attack':
            if int(self.animation_index) == self.animation_length - 1:
                self.target.hit(self.damage)
                if self.target.health <= 0:
                    self.target = None
                    self.set_state('move')
        elif self.state == 'death' and round(self.animation_index) == self.animation_length:
            self.state = 'killed'

    def get_state(self):
        return self.player, self.type, self.get_coords(), self.state, int(self.animation_index), self.health

    def attack(self, target):
        if self.state != 'attack':
            self.target = target
            self.set_state('attack')

    def hit(self, damage):
        self.health -= damage


class BowTower:
    cost = 50
    time_to_reload = 100
    shooting_range = 600
    damage = 10
    animation_index = 0
    x_bias = 125
    y_bias = -25

    def __init__(self, player, coords, game):
        self.player = player
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.game = game
        self.reloading = 0

    def get_coords(self):
        return self.coords[0] - self.x_bias, self.coords[1] + self.y_bias

    def update(self):
        if not self.reloading:
            for mob in self.game.mobs[opponent(self.player)]:
                distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                if distance <= self.shooting_range and mob.state != 'death':
                    self.game.bullets.append(Bullet(self.coords, self.damage, 'arrow', distance, mob))
                    self.reloading = self.time_to_reload
                    return
        else:
            self.reloading -= 1

    def get_state(self):
        return 'bow', self.get_coords(), int(self.animation_index)


class CannonTower:
    cost = 100
    time_to_reload = 200
    shooting_range = 800
    damage = 40
    x_bias = 125
    y_bias = 75

    def __init__(self, player, coords, game):
        self.player = player
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.game = game
        self.reloading = 0
        self.animation_index = 0

    def get_coords(self):
        return self.coords[0] - self.x_bias, self.coords[1] - self.y_bias

    def update(self):
        if not self.reloading:
            for mob in self.game.mobs[opponent(self.player)]:
                distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                if distance <= self.shooting_range and mob.state != 'death':
                    bullet = Bullet(self.coords, self.damage, 'shell', distance, mob)
                    self.game.bullets.append(bullet)
                    angle = bullet.angle
                    if angle < 2 * math.pi:
                        angle += 2 * math.pi
                    self.animation_index = round(angle / (math.pi / 8)) % 16
                    self.reloading = self.time_to_reload
                    return
        else:
            self.reloading -= 1

    def get_state(self):
        return 'cannon', self.get_coords(), int(self.animation_index)


class CrystalTower:
    cost = 150
    time_to_reload = 30
    shooting_range = 700
    damage = 5
    x_bias = 125
    y_bias = -50
    animation_length = 27

    def __init__(self, player, coords, game):
        self.player = player
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.game = game
        self.reloading = 0
        self.animation_index = 0

    def get_coords(self):
        return self.coords[0] - self.x_bias, self.coords[1] + self.y_bias

    def update(self):
        if not self.reloading:
            for mob in self.game.mobs[opponent(self.player)]:
                distance = math.hypot(self.coords[0] - mob.coords[0], self.coords[1] - mob.coords[1])
                if distance <= self.shooting_range and mob.state != 'death':
                    self.game.bullets.append(HomingBullet(self.coords, self.damage, 'sphere', mob))
                    self.reloading = self.time_to_reload
                    return
        else:
            self.reloading -= 1
        self.animation_index = (self.animation_index + 0.3) % self.animation_length

    def get_state(self):
        return 'crystal', self.get_coords(), int(self.animation_index)


class MainTower:
    health = 1000
    full_hp = 1000

    def __init__(self, player, game):
        self.player = player
        self.game = game
        if player == PLAYER_1:
            self.coords = (98, 462)
        else:  # player == PLAYER_2
            self.coords = (1828, 470)
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
        self.animation_index = 0.
        self.killed = False

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
            self.killed = True

    def get_state(self):
        return self.type, self.coords, self.angle, int(self.animation_index)


class HomingBullet:
    def __init__(self, start_coords, damage, type, mob):
        self.coords = list(start_coords)
        self.damage = damage
        self.type = type
        self.mob = mob
        self.velocity = 5
        self.angle = 0
        self.animation_index = 0
        self.animation_length = 5
        self.killed = False

    def update(self):
        x, y = self.coords
        x1, y1 = self.mob.coords
        d_x, d_y = x1 - x, y - y1
        distance = math.hypot(d_x, d_y)
        self.coords[0] += self.velocity * (d_x / distance)
        self.coords[1] += self.velocity * (-d_y / distance)
        self.angle = math.atan(d_y / d_x)
        if d_x > 0:
            self.angle += math.pi
        self.animation_index = (self.animation_index + 1) % self.animation_length
        if distance < 10 or self.mob.state == 'death':
            self.mob.hit(self.damage)
            self.killed = True

    def get_state(self):
        return self.type, self.coords, self.angle, int(self.animation_index)


class OnlineGame:
    def __init__(self):
        self.main_towers = {
            PLAYER_1: MainTower(PLAYER_1, self),
            PLAYER_2: MainTower(PLAYER_2, self)
        }
        self.players_cache = {
            PLAYER_1: 1000,
            PLAYER_2: 1000
        }
        self.mobs = {
            PLAYER_1: [],
            PLAYER_2: []
        }
        self.towers = {
            PLAYER_1: [],
            PLAYER_2: []
        }
        self.bullets = []
        self.action_query = []
        self.data_to_send = pickle.dumps('Waiting for players')

    def start(self):
        while True:
            start_time = time.time()
            self.update()
            self.update_sending_data()
            sleep_time = 0.9 * TICK - (time.time() - start_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def let_mobs_fight(self, mob1, mob2):
        x = (mob1.coords[0] + mob2.coords[0]) / 2
        y = (mob1.coords[1] + mob2.coords[1]) / 2
        if mob1.player == PLAYER_1:
            mob1.coords = [x - 30, y]
            mob2.coords = [x + 30, y]
        else:
            mob1.coords = [x + 30, y]
            mob2.coords = [x - 30, y]
        mob1.attack(mob2)
        mob2.attack(mob1)

    def update(self):
        if self.action_query:
            self.handle_player_action(*self.action_query.pop(-1))
        for mob in self.mobs[PLAYER_1]:
            mob.update()
            if mob.state == 'killed':
                self.mobs[PLAYER_1].remove(mob)
        for mob in self.mobs[PLAYER_2]:
            mob.update()
            if mob.state == 'killed':
                self.mobs[PLAYER_2].remove(mob)
                continue
            x, y = mob.coords
            for opponent_mob in self.mobs[PLAYER_1]:
                x1, y1 = opponent_mob.coords
                if opponent_mob.road == mob.road and abs(x - x1) < 80:
                    states = {mob.state, opponent_mob.state}
                    if 0 < abs(y - y1) < 200 and 'move' in states and 'death' not in states:
                        self.let_mobs_fight(mob, opponent_mob)
        for tower in self.towers[PLAYER_1] + self.towers[PLAYER_2]:
            tower.update()
        self.main_towers[PLAYER_1].update()
        self.main_towers[PLAYER_2].update()
        for bullet in self.bullets:
            bullet.update()
            if bullet.killed:
                self.bullets.remove(bullet)
        self.players_cache[PLAYER_1] += CACHE_VELOCITY
        self.players_cache[PLAYER_2] += CACHE_VELOCITY

    def update_sending_data(self):
        mobs_data = []
        for mob in self.mobs[PLAYER_1] + self.mobs[PLAYER_2]:
            mobs_data.append(mob.get_state())
        towers_data = []
        for tower in self.towers[PLAYER_1] + self.towers[PLAYER_2]:
            towers_data.append(tower.get_state())
        bullets_data = []
        for bullet in self.bullets:
            bullets_data.append(bullet.get_state())
        self.data_to_send = pickle.dumps((tuple(mobs_data), tuple(towers_data), tuple(bullets_data),
                                          self.main_towers[1].health, self.main_towers[2].health,
                                          int(self.players_cache[PLAYER_1]), int(self.players_cache[PLAYER_2])))

    def handle_player_action(self, player, action, data):
        if action == 'spawn_mob':
            mob_type = data[0]
            road_index = int(data[1])
            coords = tuple(map(int, data[2].split(';')))
            mob = Mob(player, mob_type, road_index, coords, self.main_towers[opponent(player)])
            if self.players_cache[player] >= mob.cost:
                if ((player == 1 and coords[0] < WIDTH / 4) or (player == 2 and coords[0] > WIDTH / 4 * 3)):
                    self.mobs[player].append(mob)
                    self.players_cache[player] -= mob.cost
        elif action == 'spawn_tower':
            tower_type = data[0]
            coords = tuple(map(int, data[1].split(';')))
            tower = {'bow': BowTower, 'cannon': CannonTower, 'crystal': CrystalTower}[tower_type]
            towers = self.towers[player]
            x, y = coords
            for i in range(len(towers)):
                x1, y1 = towers[i].get_coords()
                if abs(x - x1) <= 100 and abs(y - y1) <= 100:
                    if towers[i].cost < tower.cost:
                        towers[i] = tower(player, coords, self)
                    else:
                        break
            else:
                towers.append(tower(player, coords, self))
            self.players_cache[player] -= tower.cost
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
    P_2_WAYS = load_ways()
    P_1_WAYS = [[ways[::-1] for ways in road] for road in P_2_WAYS]
    clients_accepting_thread = Thread(target=clients_accepting)
    clients_accepting_thread.start()
