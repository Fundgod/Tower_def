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
from utils import opponent, load_ways, calculate_distance_between_points


SERVER = '0.0.0.0'
PORT = 4444
P_2_WAYS = load_ways(os.path.join('maps', 'online_game_map'))
# Пути левого игрока - это "перевёрнутые" пути правого игрока:
P_1_WAYS = [[ways[::-1] for ways in road] for road in P_2_WAYS]

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.bind((SERVER, PORT))
except socket.error:
    print('Socket error')
    sys.exit(1)

s.listen(6)
print('Waiting for connection')


class Room:
    """Игровое лобби на двух игроков"""
    def __init__(self, player_1_connection, rooms):
        self.player_1 = (PLAYER_1, player_1_connection)
        self.rooms = rooms
        self.player_2 = None
        self.game = OnlineGame()

    def add_player(self, player_2_connection):
        self.player_2 = (PLAYER_2, player_2_connection)

    def start_game(self):
        Thread(target=self.game.start_mainloop).start()

    def is_full(self):
        if self.player_2 is not None:
            return True
        return False

    def close(self):
        if self.player_1 is not None:
            self.player_1[1].close()
            self.player_1 = None
            print('player 1 disconnected successfully')
        if self.player_2 is not None:
            self.player_2[1].close()
            self.player_2 = None
            print('player 2 disconnected successfully')
        if self in self.rooms:
            self.rooms.remove(self)


def clients_accepting():
    """Функция для приёма клиентов.
    Выполняется в отдельном потоке, после подключения клиента запускает client_processing"""
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
    """Обслживает одного клиента, регулярно отправляя состояние игры.
    Выполняется в отдельном потоке"""
    game = room.game
    try:
        # Сначала отправляется номер игрока - 1 или 2, далее регулярно высылаются игровые данные
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
    except Exception:
        conn.close()
        room.close()


def let_mobs_fight(mob1, mob2):
    """Ставит двух мобов друг напротив друга и заставляет их атаковать друг друга"""
    # Ставим мобов друг напротив друга:
    x = (mob1.coords[0] + mob2.coords[0]) / 2
    y = (mob1.coords[1] + mob2.coords[1]) / 2
    if mob1.player == PLAYER_1:
        mob1.coords = [x - 30, y]
        mob2.coords = [x + 30, y]
    else:
        mob1.coords = [x + 30, y]
        mob2.coords = [x - 30, y]
    # Заставляем мобов драться:
    mob1.attack(mob2)
    mob2.attack(mob1)


class Mob:
    def __init__(self, player, type, road_index, coords, opponent_main_tower):
        self.player = player
        self.type = type
        self.road = road_index
        self.coords = list(coords)
        self.opponent_main_tower = opponent_main_tower
        self.way = self.define_way()
        self.pos = 0  # индекс проходимой точки в маршруте моба
        self.load_info(self.type)
        self.set_state('move')
        self.steps_to_next_point = 0  # сколько шагов осталось пройти до следующей точки маршрута
        self.tagged = False
        self.target = None

    def define_way(self):
        # Случайно определяется путь моба:
        way = (P_1_WAYS if self.player == PLAYER_1 else P_2_WAYS)[self.road][random.randint(0, 1)]
        # Далее определяется точка, с которой начинается путь:
        if self.player == 1:
            direction = 1
        else:
            direction = -1
        for index, point in enumerate(way):
            if (point[0] - self.coords[0]) * direction > 100:
                return tuple([self.coords] + list(way[index:]))

    def load_info(self, type):
        """Загружает параметры моба из json файла"""
        with open(os.path.join('mobs', type, 'info.json'), 'r', encoding='utf-8') as info_file:
            self.info = json.load(info_file)
        self.velocity = self.info['velocity'] / FPS
        self.health = self.max_health = self.info['health']
        self.damage = self.info['damage']
        self.cost = self.info['cost']

    def set_state(self, state):
        """В разных состояниях моб(спрайт моба) разного размера,
        поэтому при смене состояния моба приходится менять и некоторые другие параметры"""
        self.state = state
        self.half_width = self.info[self.state]['width'] / 2
        self.half_height = self.info[self.state]['height'] / 2
        self.animation_speed = self.info[state]['animation_speed']
        self.animation_length = self.info[state]['animation_length']
        self.animation_index = 0.

    def get_current_coords(self):
        """Возвращает координаты левого верхнего угла моба для отправки клиенту"""
        return (self.coords[0] - self.half_width,
                self.coords[1] - self.half_height)

    def get_position(self, delta_steps):
        """Возвращает координату, в которой окажется моб через заданное количество шагов"""
        index = self.pos
        steps = self.steps_to_next_point
        way_len = len(self.way)
        # Будет просчитываться движение моба до тех пор, пока он не пройдёт нужное количество шагов
        while index < way_len - 1:
            if steps < delta_steps:
                delta_steps -= steps
            else:
                if index > self.pos:
                    way_point_1 = self.way[index - 1]
                else:
                    way_point_1 = self.coords
                way_point_2 = self.way[index]
                d_x, d_y = way_point_2[0] - way_point_1[0], way_point_2[1] - way_point_1[1]
                return (way_point_1[0] + d_x / steps * delta_steps,
                        way_point_1[1] + d_y / steps * delta_steps)
            start_point = self.way[index]
            index += 1
            next_point = self.way[index]
            d_x, d_y = next_point[0] - start_point[0], next_point[1] - start_point[1]
            steps = math.hypot(d_x, d_y) / self.velocity
        else:
            return self.way[-1]

    def update(self):
        self.animation_index = (self.animation_index + self.animation_speed) % self.animation_length
        if self.health <= 0 and self.state != 'death':
            self.set_state('death')
        if self.state == 'move':
            # Совершается перемещение(шаг)
            try:
                if self.steps_to_next_point <= 0:
                    start_point = self.way[self.pos]
                    self.pos += 1
                    next_point = self.way[self.pos]
                    d_x, d_y = next_point[0] - start_point[0], next_point[1] - start_point[1]
                    self.steps_to_next_point = math.hypot(d_x, d_y) // self.velocity
                    if self.steps_to_next_point == 0:
                        self.steps_to_next_point = 1
                    self.x_velocity = d_x / self.steps_to_next_point
                    self.y_velocity = d_y / self.steps_to_next_point
                self.steps_to_next_point -= 1
                self.coords[0] += self.x_velocity
                self.coords[1] += self.y_velocity
            except IndexError:
                self.attack(self.opponent_main_tower)
        elif self.state == 'attack':
            # Если проигрывается последний кадр анимации атаки, то цели наносится урон:
            if int(self.animation_index) == self.animation_length - 1:
                self.target.hit(self.damage)
                # Если цель умерла, то двигаемся дальше:
                if self.target.health <= 0:
                    self.target = None
                    self.set_state('move')
        elif self.state == 'death' and round(self.animation_index) == self.animation_length:
            self.state = 'killed'

    def attack(self, target):
        if self.state != 'attack':
            self.target = target
            self.set_state('attack')

    def hit(self, damage):
        self.health -= damage

    def get_data(self):
        """Возвращает всю информацию о мобе для отправки клиенту"""
        return self.player, self.type, self.get_current_coords(), self.state, int(self.animation_index), self.health


class BowTower:
    cost = 50
    time_to_reload = 100
    shooting_range = 600
    damage = 10
    animation_index = 0
    x_bias = 125
    y_bias = -25

    def __init__(self, player, coords, mobs, bullets):
        self.player = player
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.mobs = mobs
        self.bullets = bullets
        self.reloading = 0  # сколько времени осталось до выстрела(сек/60)

    def get_coords(self):
        """Возвращает координаты левого верхнего угла башни для отправки клиенту"""
        return self.coords[0] - self.x_bias, self.coords[1] + self.y_bias

    def update(self):
        if not self.reloading:
            for mob in self.mobs[opponent(self.player)]:
                if mob.state != 'death':
                    distance = calculate_distance_between_points(*self.coords, *mob.coords)
                    if distance <= self.shooting_range:
                        self.bullets.append(Bullet(self.coords, self.damage, 'arrow', 600, mob, distance))
                        self.reloading = self.time_to_reload
                        return
        else:
            self.reloading -= 1

    def get_data(self):
        """Возвращает всю информацию о башне для отправки клиенту"""
        return 'bow', self.get_coords(), int(self.animation_index)


class CannonTower:
    cost = 100
    time_to_reload = 200
    shooting_range = 800
    damage = 40
    x_bias = 125
    y_bias = 75
    # bias - смещение точки, из которой вылетает снаряд, от левого верхнего угла плента, на котором спавнится башня
    animation_length = 16

    def __init__(self, player, coords, mobs, bullets):
        self.player = player
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.mobs = mobs
        self.bullets = bullets
        self.reloading = 0  # сколько времени осталось до выстрела(сек/60)
        self.animation_index = 0

    def get_coords(self):
        """Возвращает координаты левого верхнего угла башни для отправки клиенту"""
        return self.coords[0] - self.x_bias, self.coords[1] - self.y_bias

    def update(self):
        if not self.reloading:
            for mob in self.mobs[opponent(self.player)]:
                if mob.state != 'death':
                    distance = calculate_distance_between_points(*self.coords, *mob.coords)
                    if distance <= self.shooting_range:
                        bullet = Bullet(self.coords, self.damage, 'shell', 1200, mob, distance)
                        self.bullets.append(bullet)
                        self.animation_index = round(bullet.angle / (math.pi / 8)) % self.animation_length
                        self.reloading = self.time_to_reload
                        return
        else:
            self.reloading -= 1

    def get_data(self):
        """Возвращает всю информацию о башне для отправки клиенту"""
        return 'cannon', self.get_coords(), int(self.animation_index)


class CrystalTower:
    cost = 150
    time_to_reload = 30
    shooting_range = 700
    damage = 5
    x_bias = 125
    y_bias = -50
    # bias - смещение точки, из которой вылетает снаряд, от левого верхнего угла плента, на котором спавнится башня
    animation_length = 27

    def __init__(self, player, coords, mobs, bullets):
        self.player = player
        self.coords = (coords[0] + self.x_bias, coords[1] + self.y_bias)
        self.mobs = mobs
        self.bullets = bullets
        self.reloading = 0  # сколько времени осталось до выстрела(сек/60)
        self.animation_index = 0

    def get_coords(self):
        """Возвращает координаты левого верхнего угла башни для отправки клиенту"""
        return self.coords[0] - self.x_bias, self.coords[1] + self.y_bias

    def update(self):
        if not self.reloading:
            for mob in self.mobs[opponent(self.player)]:
                if mob.state != 'death':
                    distance = calculate_distance_between_points(*self.coords, *mob.coords)
                    if distance <= self.shooting_range:
                        self.bullets.append(HomingBullet(self.coords, self.damage, 'sphere', 300, mob))
                        self.reloading = self.time_to_reload
                        return
        else:
            self.reloading -= 1
        self.animation_index = (self.animation_index + 0.3) % self.animation_length

    def get_data(self):
        """Возвращает всю информацию о башне для отправки клиенту"""
        return 'crystal', self.get_coords(), int(self.animation_index)


class MainTower(BowTower):
    health = 1000
    full_hp = 1000
    time_to_reload = 60

    def __init__(self, player, mobs, bullets):
        if player == PLAYER_1:
            coords = (98, 462)
        else:
            coords = (1828, 470)
        super().__init__(player, coords, mobs, bullets)

    def hit(self, damage):
        self.health -= damage


class BaseBullet:
    """Класс-родитель для классов конкретных пуль"""
    def __init__(self, start_coords, damage, type, velocity, mob):
        self.coords = list(start_coords)
        self.damage = damage
        self.type = type
        self.velocity = velocity / FPS
        self.mob = mob
        self.angle = 0
        self.animation_index = 0
        self.killed = False

    def get_data(self):
        """Возвращает всю информацию о снаряде для отправки клиенту"""
        return self.type, self.coords, self.angle, int(self.animation_index)


class Bullet(BaseBullet):
    """Класс прямолетящего снаряда"""
    def __init__(self, start_coords, damage, type, velocity, mob, distance_to_target):
        super().__init__(start_coords, damage, type, velocity, mob)
        self.distance_to_target = distance_to_target
        self.calculate_trajectory(mob, distance_to_target)

    def calculate_trajectory(self, mob, distance_to_target):
        """Рассчитывает маршрут полёта стрелы до противника и угол, под которым полетит стрела"""
        flight_time = distance_to_target / self.velocity
        self.end_coords = mob.get_position(flight_time)
        d_x, d_y = self.end_coords[0] - self.coords[0], self.end_coords[1] - self.coords[1]
        distance = math.hypot(d_x, d_y)
        if distance == 0:
            distance = 1
        self.velocity = distance / flight_time
        self.step = (d_x / distance * self.velocity,
                     d_y / distance * self.velocity)
        self.steps_to_target = distance / self.velocity
        self.angle = -math.atan(d_y / d_x)
        if d_x < 0:
            self.angle += math.pi

    def update(self):
        if self.steps_to_target > 0:
            self.coords[0] += self.step[0]
            self.coords[1] += self.step[1]
            self.steps_to_target -= 1
        else:
            self.mob.hit(self.damage)
            self.killed = True


class HomingBullet(BaseBullet):
    """Класс самонаводящегося снаряда"""
    def __init__(self, start_coords, damage, type, velocity, mob):
        super().__init__(start_coords, damage, type, velocity, mob)
        self.animation_length = 5

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


class OnlineGame:
    def __init__(self):
        self.mobs = {
            PLAYER_1: [],
            PLAYER_2: []
        }
        self.bullets = []
        self.main_towers = {
            PLAYER_1: MainTower(PLAYER_1, self.mobs, self.bullets),
            PLAYER_2: MainTower(PLAYER_2, self.mobs, self.bullets)
        }
        self.players_cache = {
            PLAYER_1: 1000,
            PLAYER_2: 1000
        }
        self.towers = {
            PLAYER_1: [],
            PLAYER_2: []
        }
        self.action_query = []  # очередь действий пользователей
        self.data_to_send = pickle.dumps('Waiting for players')

    def start_mainloop(self):
        while True:
            start_time = time.time()
            self.update()
            sleep_time = 0.9 * TICK - (time.time() - start_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def update(self):
        if self.action_query:
            self.handle_player_action(*self.action_query.pop(-1))
        # Очистка списков мобов(удаление умерших мобов) и формирование боёв между мобами:
        for mob in self.mobs[PLAYER_1]:
            mob.update()
            if mob.state == 'killed':
                self.mobs[PLAYER_1].remove(mob)
        for mob in self.mobs[PLAYER_2]:
            mob.update()
            if mob.state == 'killed':
                self.mobs[PLAYER_2].remove(mob)
                continue
            # Формирование стычек между мобами:
            for opponent_mob in self.mobs[PLAYER_1]:
                if calculate_distance_between_points(*mob.coords, *opponent_mob.coords) < 100:
                    states = {mob.state, opponent_mob.state}
                    if 'move' in states and 'death' not in states:
                        let_mobs_fight(mob, opponent_mob)

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

        self.update_sending_data()

    def update_sending_data(self):
        """Обновляет атрибут data_to_send, который отправляется клиентам в функции client_processing"""
        mobs_data = []
        for mob in self.mobs[PLAYER_1] + self.mobs[PLAYER_2]:
            mobs_data.append(mob.get_data())

        towers_data = []
        for tower in self.towers[PLAYER_1] + self.towers[PLAYER_2]:
            towers_data.append(tower.get_data())

        bullets_data = []
        for bullet in self.bullets:
            bullets_data.append(bullet.get_data())

        self.data_to_send = pickle.dumps((tuple(mobs_data), tuple(towers_data), tuple(bullets_data),
                                          self.main_towers[1].health, self.main_towers[2].health,
                                          int(self.players_cache[PLAYER_1]), int(self.players_cache[PLAYER_2])))

    def get_player_action(self, player, action, data):
        self.action_query.append((player, action, data))

    def handle_player_action(self, player, action, data):
        if action == 'spawn_mob':
            mob_type = data[0]
            road_index = int(data[1])
            coords = tuple(map(int, data[2].split(';')))
            mob = Mob(player, mob_type, road_index, coords, self.main_towers[opponent(player)])
            if self.players_cache[player] >= mob.cost:
                if (player == PLAYER_1 and coords[0] < WIDTH / 4) or (player == PLAYER_2 and coords[0] > WIDTH / 4 * 3):
                    self.mobs[player].append(mob)
                    self.players_cache[player] -= mob.cost
        elif action == 'spawn_tower':
            tower_type = data[0]
            coords = tuple(map(int, data[1].split(';')))
            tower = {'bow': BowTower, 'cannon': CannonTower, 'crystal': CrystalTower}[tower_type]
            towers = self.towers[player]
            for i in range(len(towers)):
                if calculate_distance_between_points(*coords, *towers[i].get_coords()) <= 142:
                    if towers[i].cost < tower.cost:
                        towers[i] = tower(player, coords, self.mobs, self.bullets)
                    else:
                        break
            else:
                towers.append(tower(player, coords, self.mobs, self.bullets))
            self.players_cache[player] -= tower.cost


if __name__ == '__main__':
    clients_accepting()
