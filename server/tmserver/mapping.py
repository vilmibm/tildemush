# There are three phases to mapping:
# 1. walking rooms
# 2. generating the mapfile
# 3. calling out to Graph::Easy and passing the mapfile
#
# a mapfile looks like this:
#
# [ Room Name 0 ] -- direction --> [ Room Name 1 ]
# [ Room Name 1 ] -- direction --> [ Room Name 2]
#
# To save visual space on the map, we don't mark return edges; ie, if room A is
# connected to the east to room B, we only map the eastern connection: not the
# corresponding western direction.
#
# TODO This code is pretty slow right now and should have plenty of room for
# optimization
import subprocess
from collections import OrderedDict
from importlib import resources

from .constants import DIRECTIONS
from .models import GameObject

def render_map(world, room, distance=2):
    mapfile = from_room(world, room, distance)
    return graph_easy(mapfile)


def graph_easy(mapfile_content):
    with resources.path(__package__, 'boxgraph') as p:
        completed = subprocess.run([p],
                             input=mapfile_content,
                             capture_output=True,
                             text=True)
        # TODO error handling
        return completed.stdout

def mapfile_for_room(world, mapped, room):
    return [
        '[ {from_room} ] -- {direction} --> [ {to_room} ]'.format(
            from_room=room.name,
            direction=d,
            to_room=r.name)
        for d,r in adjacent(world, room)
        if r.shortname not in mapped]

def adjacent(world, room):
    out = []
    for d in DIRECTIONS:
        e = world.resolve_exit(room, d)
        if e is None: continue
        route = e.get_data('exit').get(room.shortname)
        target_room = GameObject.get_or_none(GameObject.shortname==route[1])
        out.append((d,target_room))

    return out

def build_queue(world, queue, room):
    if queue[room.shortname] == 0:
        return
    else:
        for d,r in adjacent(world, room):
            if r.shortname in queue: continue
            queue[r.shortname] = queue[room.shortname] - 1
            build_queue(world, queue, r)

def from_room(world, room, distance=3):
    if distance < 0:
        raise ValueError('distance must be greater than 0')

    queue = OrderedDict()
    queue[room.shortname] = distance
    build_queue(world, queue, room)
    mapped = set()
    mapfile = []
    for room_name in queue.keys():
        room = GameObject.get(GameObject.shortname==room_name)
        mapfile.extend(mapfile_for_room(world, mapped, room))
        mapped.add(room_name)

    return '\n'.join(mapfile)
