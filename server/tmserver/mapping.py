from .models import GameObject
from .world import GameWorld, DIRECTIONS

# There are three phases to mapping:
# 1. walking rooms
# 2. generating the mapfile
# 3. calling out to Graph::Easy and passing the mapfile.
#
# a mapfile looks like this:
#
# [ Room Name 0 ] -- direction --> [ Room Name 1 ]
# [ Room Name 1 ] -- direction --> [ Room Name 2]
# ...

def from_room(room_obj, distance=3):
    if distance < 0:
        raise ValueError('distance must be greater than 0')

    mapfile = []

    for d in DIRECTIONS:
        room = room_obj
        done = False
        travelled = 0
        while not done:
            e = GameWorld.resolve_exit(room, d)
            if e is None:
                # We've gone as far as we can in this direction; time for the
                # next direction.
                done = True
                continue
            route = e.get_data('exit').get(room.shortname)
            target_room = GameObject.get_or_none(GameObject.shortname==route[1])
            mapfile.append('[ {from_room} ] -- {direction} --> [ {to_room} ]'.format(
                from_room=room.name,
                direction=d,
                to_room=target_room.name))
            travelled += 1
            room = target_room
            if travelled >= distance:
                # We've performed distance hops; we should be mapping distance nodes + source node
                done = True

    return '\n'.join(mapfile)

