# Выход из онлайн матча любым возможным способом сопровождается вызовом одного из следующих исключений:


class ServerError(Exception):
    """Вызывается в случае любой непредвиденной ошибки в онлайн режиме"""
    pass


class OpponentExitError(Exception):
    """Вызывается когда противник покинул игру"""
    pass


class Win(Exception):
    """Вызывается при завершении онлойн матча в пользу игрока"""
    pass


class Lose(Exception):
    """Вызывается у игрока когда тот проигрывает онлайн матч"""
    pass


class Exit(Exception):
    """Вызывается когда игрок вышел из онлайн режима"""
    pass
