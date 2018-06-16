import re

from slugify import slugify

from .config import get_db
from .errors import ClientException
from .models import Contains, GameObject, Contains, Script

OBJECT_DENIED = 'You grab a hold of {} but no matter how hard you pull it stays rooted in place.'
OBJECT_NOT_FOUND = 'You look in vain for {}.'
DIRECTIONS = {'north', 'south', 'west', 'east', 'above', 'below'}
CREATE_TYPES = {'room', 'exit', 'item'}
CREATE_RE = re.compile(r'^([^ ]+) "([^"]+)" (.*)$')
CREATE_EXIT_ARGS_RE = re.compile(r'^([^ ]+) ([^ ]+) (.*)$')
PUT_ARGS_RE = re.compile(r'^(.+) in (.+)$')
REVERSE_DIRS = {
    'north': 'south',
    'south': 'north',
    'east': 'west',
    'west': 'east',
    'above': 'below',
    'below': 'above'}


class GameWorld:
    # TODO logging
    _sessions = {}

    @classmethod
    def reset(cls):
        cls._sessions = {}

    @classmethod
    def register_session(cls, user_account, user_session):
        # TODO check for this key already existing
        cls._sessions[user_account.id] = user_session

    @classmethod
    def get_session(cls, user_account_id):
        session = cls._sessions.get(user_account_id)
        if session is None:
            raise ClientException('No session found. Log in again.')

        return session

    @classmethod
    def client_state(cls, user_account):
        """Given a user account, returns a dictionary of information relevant
        to the game client."""
        player_obj = user_account.player_obj
        room = player_obj.contained_by
        exits = room.get_data('exits', {})
        exit_payload = {}

        for direction in DIRECTIONS:
            if direction not in exits:
                continue

            exit_obj = GameObject.get_or_none(GameObject.shortname==exits[direction])
            if exit_obj is None:
                continue

            target_room_name = exit_obj.get_data('target')
            if target_room_name is None:
                continue

            target_room = GameObject.get_or_none(GameObject.shortname==target_room_name)
            if target_room is None:
                continue

            exit_payload[direction] = dict(
                exit_name=exit_obj.name,
                room_name=target_room.name)

        return {
            'motd': 'welcome to tildemush',  # TODO
            'user': {
                'username': user_account.username,
                'display_name': player_obj.name,
                'description': player_obj.description
            },
            'room': {
                'name': room.name,
                'description': room.description,
                'contains': [dict(name=o.name, description=o.description)
                             for o in room.contains
                             if o.name != player_obj.name],
                'exits': exit_payload,
            },
            'inventory': cls.contains_tree(player_obj),
            'scripts': [s.name for s
                        in Script.select(Script.name).where(Script.author==user_account)],
        }

    @classmethod
    def send_client_update(cls, user_account):
        if user_account.id in cls._sessions:
            cls.get_session(user_account.id).handle_client_update(
                cls.client_state(user_account))

    @classmethod
    def contains_tree(cls, obj):
        """Given an object, this function recursively builds up the tree of
        objects it contains."""

        out = []
        for o in obj.contains:
            out.append({
                'name': o.name,
                'description': o.description,
                'contains': cls.contains_tree(o)
            })
        return out

    @classmethod
    def dispatch_action(cls, sender_obj, action, action_args):
        # TODO this list is only going to grow. these are commands that have
        # special meaning to the game (ie unlike something a game object merely
        # listens for like "pet"). I'm considering generalizing this as a list
        # of GAME_COMMANDS that map to a GameWorld handle_* method.

        # admin
        if action == 'announce':
            cls.handle_announce(sender_obj, action_args)

        # chatting
        if action == 'whisper':
            cls.handle_whisper(sender_obj, action_args)

        if action == 'look':
            cls.handle_look(sender_obj, action_args)

        # scripting
        if action == 'create':
            cls.handle_create(sender_obj, action_args)

        # TODO edit

        # movement
        if action == 'move':
            cls.handle_move(sender_obj, action_args)
            return
        if action == 'go':
            cls.handle_go(sender_obj, action_args)
            return

        # inventory commands
        if action == 'get':
            cls.handle_get(sender_obj, action_args)
        if action == 'drop':
            cls.handle_drop(sender_obj, action_args)
        if action == 'put':
            cls.handle_put(sender_obj, action_args)
        if action == 'remove':
            cls.handle_remove(sender_obj, action_args)

        aoe = cls.area_of_effect(sender_obj)
        for o in aoe:
            o.handle_action(cls, sender_obj, action, action_args)

    @classmethod
    def all_active_objects(cls):
        """This method assumes that if an object is contained by something
        else, it's "active" in the game; in other words, we're assuming that a
        player object connected to a not-logged-in user account won't exist in
        a room."""
        all_containing_objects = set(GameObject.select()\
                                               .join(Contains, on=Contains.outer_obj)\
                                               .distinct(GameObject.id))
        all_contained_objects = set(GameObject.select()\
                                              .join(Contains, on=Contains.inner_obj)\
                                              .distinct(GameObject.id))
        return all_containing_objects.union(all_contained_objects)

    @classmethod
    def handle_get(cls, sender_obj, action_args):
        """This action looks for an object:
           - in sender_obj's current room
           - that sender_obj has the carry permission for
           - whose full name or shortname match the provided object name

           Given an object with name "A Banana" and shortname "banana-user-id"
           this command should be invoked like:

           /get banana

           and will also match:
           /get a banana
           /get Banana
        """
        # TODO eventually, generalize object resolution for various scopes. Consider player objects.
        match_string = action_args
        found = None
        for obj in sender_obj.contained_by.contains:
            if obj.is_player_obj:
                continue
            if obj.fuzzy_match(match_string):
                found = obj
                break

        if found is None:
            raise ClientException(OBJECT_NOT_FOUND.format(match_string))

        if not sender_obj.can_carry(found):
            raise ClientException(OBJECT_DENIED.format(found.name))

        cls.put_into(sender_obj, found)
        cls.user_hears(sender_obj, sender_obj, 'You grab {}.'.format(found.name))

    @classmethod
    def handle_drop(cls, sender_obj, action_args):
        """Matches an object in sender_obj.contains and moves it to
        sender_obj.contained_by"""

        # TODO eventually, generalize object resolution for various scopes. Consider player objects.
        match_string = action_args
        found = None
        for obj in sender_obj.contains:
            if obj.fuzzy_match(match_string):
                found = obj
                break

        if found is None:
            raise ClientException('You look in vain for something called {}.'.format(obj_string))

        cls.put_into(sender_obj.contained_by, found)
        cls.user_hears(sender_obj, sender_obj, 'You drop {}.'.format(found.name))

    @classmethod
    def handle_put(cls, sender_obj, action_args):
        """Called like:

           /put phaser in bag

        we (somewhat disconcertingly) split on ' in '. TODO support quoting
        both object names in case a name ends up with ' in ' in it.

        Moves the first object into second_obj.contains.
        """
        match = PUT_ARGS_RE.fullmatch(action_args)
        if match is None:
            raise ClientException('Try /put some object in container object')
        target_obj_str, container_obj_str = match.groups()
        target_obj = None
        container_obj = None
        for obj in sender_obj.contains:
            if obj.fuzzy_match(target_obj_str):
                target_obj = obj
                break

        if target_obj is None:
            for obj in sender_obj.contained_by.contains:
                if obj.is_player_obj:
                    continue
                if obj.fuzzy_match(target_obj_str):
                    target_obj = obj
                    break
            if target_obj is None:
                raise ClientException(OBJECT_NOT_FOUND.format(target_obj_str))
            if not sender_obj.can_carry(target_obj):
                raise ClientException(OBJECT_DENIED.format(target_obj_str))

        container_obj = None
        for obj in sender_obj.contains:
            if obj.fuzzy_match(container_obj_str):
                container_obj = obj
                break

        if container_obj is None:
            for obj in sender_obj.contained_by.contains:
                if obj.is_player_obj:
                    continue
                if obj.fuzzy_match(container_obj_str):
                    container_obj = obj
                    break
            if container_obj is None:
                raise ClientException(OBJECT_NOT_FOUND.format(container_obj_str))
            if not sender_obj.can_carry(container_obj):
                raise ClientException(OBJECT_DENIED.format(container_obj_str))

        cls.put_into(container_obj, target_obj)

        cls.user_hears(sender_obj, sender_obj, 'You put {} in {}'.format(target_obj.name, container_obj.name))


    @classmethod
    def handle_remove(cls, sender_obj, action_args):
        pass

    @classmethod
    def handle_create(cls, sender_obj, action_args):
        """When a player runs /create, our goal is to create a default version
        of whatever thing they want. If they want to customize a thing further,
        they can run /edit on any object for which they are the author.

        For now, the types of things that can be created: room, exit, item.

        All three of these are just GameObjects. What is different are the
        initial behaviors attached to the objects. It's at this point
        theoretically possible to /create an item and then script it into an
        exit and I don't think that's a problem. It would just be super tedious
        to do that every time one just wants to make a room.

        For now, all pretty names must be in double quotes. In other words, a call to create should look like:

        /create room "Dank Hallway" The musty carpet here seems to ooze as you walk across it.
        """
        obj_type, name, additional_args = cls.parse_create(action_args)

        create_fn = None
        if obj_type == 'item':
            create_fn = cls.create_item
        elif obj_type == 'room':
            create_fn = cls.create_room
        elif obj_type == 'exit':
            create_fn = cls.create_exit

        with get_db().atomic():
            game_obj = create_fn(sender_obj, name, additional_args)

        cls.user_hears(sender_obj, sender_obj,
                       'You breathed light into a whole new {}. Its true name is {}'.format(
                           obj_type,
                           game_obj.shortname))

    @classmethod
    def parse_create(cls, action_args):
        match = CREATE_RE.fullmatch(action_args)
        if match is None:
            raise ClientException(
                'malformed call to /create. the syntax is /create object-type "pretty name" [additional arguments]')

        obj_type, name, additional_args = match.groups()
        if obj_type not in CREATE_TYPES:
            raise ClientException(
                'Unknown type for /create. Try one of {}'.format(CREATE_TYPES))

        return obj_type, name, additional_args

    @classmethod
    def derive_shortname(cls, owner_obj, *strings):
        slugged = [slugify(s) for s in strings] + [owner_obj.user_account.username]
        shortname = '-'.join(slugged)
        if GameObject.get_or_none(GameObject.shortname==shortname):
            obj_count = GameObject.select().where(GameObject.author==owner_obj.user_account).count()
            shortname += '-' + str(obj_count)
        return shortname

    @classmethod
    def create_item(cls, owner_obj, name, additional_args):
        shortname = cls.derive_shortname(owner_obj, name)
        item = GameObject.create_scripted_object(
            'item', owner_obj.user_account, shortname, {
            'name': name,
            'description': additional_args})
        cls.put_into(owner_obj, item)

        return item

    @classmethod
    def create_room(cls, owner_obj, name, additional_args):
        shortname = cls.derive_shortname(owner_obj, name)
        room = GameObject.create_scripted_object(
            'room', owner_obj.user_account, shortname, {
            'name': name,
            'description': additional_args})

        sanctum = GameObject.get(
            GameObject.author==owner_obj.user_account,
            GameObject.is_sanctum==True)

        portkey = cls.create_portkey(owner_obj, room)
        cls.put_into(sanctum, portkey)

        return room

    @classmethod
    def create_exit(cls, owner_obj, name, additional_args):
        # TODO consider having parse_create_exit that is called outside of this
        match = CREATE_EXIT_ARGS_RE.fullmatch(additional_args)
        if not match:
            raise ClientException('To make an exit, try /create exit "A Door" north foyer A rusted, metal door')
        direction, target_room_name, description = match.groups()
        if direction not in DIRECTIONS:
            raise ClientException('Try one of these directions: {}'.format(DIRECTIONS))

        current_room = owner_obj.contained_by
        target_room = GameObject.get_or_none(
            GameObject.shortname == target_room_name)
        if target_room is None:
            raise ClientException('Could not find a room with the ID {}'.format(target_room_name))
        if not owner_obj.user_account.is_god:
            if current_room.author != owner_obj.user_account:
                raise ClientException('In order to create an exit, run this command from a room you own.')

        # make the here_exit
        shortname = cls.derive_shortname(owner_obj, name)
        here_exit = GameObject.create_scripted_object(
            'exit', owner_obj.user_account, shortname, {
            'name': name,
            'description': description,
            'target_room_name': target_room.shortname})

        with get_db().atomic():
            exits = current_room.get_data('exits')
            if exits is None:
                exits = {}
            exits[direction] = here_exit.shortname
            current_room.set_data('exits', exits)
            cls.put_into(current_room, here_exit)


        if owner_obj.user_account.is_god or target_room.author == owner_obj.user_account:
            # make the there_exit
            shortname = cls.derive_shortname(owner_obj, name, 'reverse')
            there_exit = GameObject.create_scripted_object(
                'exit', owner_obj.user_account, shortname, {
                'name': name,
                'description': description,
                'target_room_name': current_room.shortname})
            rev_dir = REVERSE_DIRS[direction]
            with get_db().atomic():
                exits = target_room.get_data('exits')
                if exits is None:
                    exits = {}
                exits[rev_dir] = there_exit.shortname
                target_room.set_data('exits', exits)
                cls.put_into(target_room, there_exit)

        return here_exit

    @classmethod
    def create_portkey(cls, owner_obj, target, name=None):
        if name is None:
            name = 'Teleport Stone to {}'.format(target.name)
        description = 'Touching this stone will transport you to'.format(target.name)
        shortname = cls.derive_shortname(owner_obj, name)
        return GameObject.create_scripted_object(
            'portkey', owner_obj.user_account, shortname, {
            'name': name,
            'description': description,
            'target_room_name': target.shortname})

    @classmethod
    def handle_announce(cls, sender_obj, action_args):
        if not sender_obj.user_account.is_god:
            raise ClientException('you are not powerful enough to do that.')

        aoe = cls.all_active_objects()
        for o in aoe:
            o.handle_action(cls, sender_obj, 'announce', action_args)

    @classmethod
    def handle_whisper(cls, sender_obj, action_args):
        action_args = action_args.split(' ')
        if 0 == len(action_args):
            raise ClientException('try /whisper another_username some cool message')
        target_name = action_args[0]
        message = ' '.join(action_args[1:])
        if 0 == len(message):
            raise ClientException('try /whisper another_username some cool message')
        room = sender_obj.contained_by
        target_obj = [o for o in room.contains if o.shortname == target_name]
        if 0 == len(target_obj):
            raise ClientException('there is nothing named {} near you'.format(target_name))
        target_obj[0].handle_action(cls, sender_obj, 'whisper', message)


    @classmethod
    def handle_look(cls, sender_obj, action_args):
        # TODO it's arguable that this should make use of a look action
        # dispatched to a game object, but I kind of wanted reality fixed in
        # place with /look.
        #
        # I'm imagining that I want object descriptions that depend on a
        # GameObject's state, but I think that dynamism can go into an /examine
        # command. /look is for getting a bearing on what's in front of you.

        msgs = []
        room = sender_obj.contained_by
        room_desc = 'You are in the {}'.format(room.name)
        if room.description:
            room_desc += ', {}'.format(room.description)
        msgs.append(room_desc)

        for o in room.contains:
            if o.user_account:
                o_desc = 'You see {}'.format(o.name)
            else:
                o_desc = 'You see a {}'.format(o.name)

            if o.description:
                o_desc += ', {}'.format(o.description)
            msgs.append(o_desc)

        for m in msgs:
            cls.user_hears(sender_obj, sender_obj, m)

        # finally, alert everything in the room that it's been looked at. game
        # objects can hook off of this if they want. By default, this does
        # nothing.

        for o in cls.area_of_effect(sender_obj):
            o.handle_action(cls, sender_obj, 'look', action_args)

    @classmethod
    def handle_move(cls, sender_obj, action_args):
        # We need to move sender_obj to whatever room is specified by the
        # action_args string. Right now actions_args has to exactly match the
        # shortname of a room in the database. In the future we might need
        # fuzzy matching but for now I think moves are largely programmatic?
        room = GameObject.get_or_none(GameObject.shortname==action_args)
        cls.put_into(room, sender_obj)
        cls.user_hears(sender_obj, sender_obj, 'You materialize in a new place!')

    @classmethod
    def handle_go(cls, sender_obj, action_args):
        # Originally we discussed having exit items be found via their
        # shortname; ie, north-a-door-vilmibm. I realized this is terrifying
        # since any other user could create a drop a trap door named
        # north-something. The resolution of the door would become undefined.
        # Thus, while it pains me and I'm hoping for an alternative, I'm going
        # to add some structure to rooms. Namely, their kv data is going to
        # store a mapping of direction -> exit shortname. This data can only be
        # changed (TODO: actually ensure this is true) by the author of the
        # room.

        # TODO in the future, consider allowing "non authoritative" directional
        # exits. An exit obj exists in a room and has a direction and target
        # stored on it. this is valid until the owner of the room overrides it
        # with a blessed exit named in the room's exits hash.
        #
        # this is either redundant or additive if we also implement a "world
        # writable" mode for stuff.

        direction = action_args
        current_room = sender_obj.contained_by
        exits = current_room.get_data('exits')
        if direction not in exits:
            cls.user_hears(sender_obj, sender_obj, 'You cannot go that way.')
            return

        exit_obj_shortname = exits[direction]
        exit_obj = None
        for obj in current_room.contains:
            if obj.shortname == exit_obj_shortname:
                exit_obj = obj
                break

        if exit_obj is None:
            cls.user_hears(sender_obj, sender_obj, 'You cannot go that way.')
            return

        exit_obj.handle_action(cls, sender_obj, 'touch', '')

    @classmethod
    def area_of_effect(cls, sender_obj):
        """Given a game object, returns the set of objects that should
        receive events that object emits.
        We want a set that includes:
        - the sender (you can hear yourself)
        - objects that contain that player object
        - objects contained by player object
        - objects contained by objects that contain the player object

        these four categories can, for the most part, correspond to:
        - a player of the game
        - the room a player is in
        - the player's inventory
        - objects in the same room as the player

        thought experiment: the bag

        my player object has been put inside a bag. The bag _contains_ my
        player object, and is in a way my "room." it's my conceit that
        whatever thing contains that bag should not receive the events my
        player object generates.

        this is easier to implement and also means you can "muffle" an object
        by stuffing it into a box.
        """
        room = sender_obj.contained_by
        inventory = set(sender_obj.contains)
        adjacent_objs = set(room.contains)
        return {sender_obj, room} | inventory | adjacent_objs

    @classmethod
    def put_into(cls, outer_obj, inner_obj):
        if inner_obj.contained_by:
            Contains.delete().where(Contains.inner_obj==inner_obj).execute()
        Contains.create(outer_obj=outer_obj, inner_obj=inner_obj)

        outer_obj.handle_action(cls, inner_obj, 'contain',  'acquired')
        inner_obj.handle_action(cls, outer_obj, 'contain',  'entered')

    @classmethod
    def remove_from(cls, outer_obj, inner_obj):
        Contains.delete().where(
            Contains.outer_obj==outer_obj,
            Contains.inner_obj==inner_obj).execute()
        outer_obj.handle_action(cls, inner_obj, 'contain', 'lost')
        inner_obj.handle_action(cls, outer_obj, 'contain', 'freed')

    @classmethod
    def user_hears(cls, receiver_obj, sender_obj, msg):
        cls.get_session(receiver_obj.user_account.id).handle_hears(sender_obj, msg)
