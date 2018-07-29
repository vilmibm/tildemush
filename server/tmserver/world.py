import itertools
import re

from slugify import slugify

from .config import get_db
from .errors import RevisionError, WitchError, ClientError, UserError
from .models import Contains, GameObject, Script, ScriptRevision, Permission, Editing, LastSeen
from .util import strip_color_codes, split_args, ARG_RE

OBJECT_DENIED = 'You grab a hold of {} but no matter how hard you pull it stays rooted in place.'
OBJECT_NOT_FOUND = 'You look in vain for {}.'
DIRECTIONS = {'north', 'south', 'west', 'east', 'above', 'below'}
CREATE_TYPES = {'room', 'exit', 'item'}
CREATE_RE = re.compile(r'^([^ ]+) "([^"]+)" (.*)$')
CREATE_EXIT_ARGS_RE = re.compile(r'^([^ ]+) ([^ ]+) (.*)$')
PUT_ARGS_RE = re.compile(r'^(.+) in (.+)$')
REMOVE_ARGS_RE = re.compile(r'^(.+) from (.+)$')
REVERSE_DIRS = {
    'north': 'south',
    'south': 'north',
    'east': 'west',
    'west': 'east',
    'above': 'below',
    'below': 'above'}
SPECIAL_HANDLING = {'say'} # TODO i thought there were others but for now it's just say. might not need a set in the end.


class GameWorld:
    # TODO logging
    _sessions = {}

    @classmethod
    def reset(cls):
        cls._sessions = {}

    @classmethod
    def register_session(cls, user_account, user_session):
        if user_account.id in cls._sessions:
            raise ClientError('User {} already logged in.'.format(user_account))

        cls._sessions[user_account.id] = user_session

        player_obj = user_account.player_obj
        ls = LastSeen.get_or_none(user_account=user_account)
        room = None
        if ls is None:
            room = GameObject.get(GameObject.shortname=='foyer')
        else:
            room = ls.room
        cls.put_into(room, player_obj)
        LastSeen.delete().where(LastSeen.user_account==user_account).execute()
        affected = (o for o in room.contains if o.is_player_obj and o != player_obj)
        for o in affected:
            cls.user_hears(o, player_obj, '{} fades in.'.format(player_obj.name))

    @classmethod
    def unregister_session(cls, user_account):
        if user_account.id in cls._sessions:
            del cls._sessions[user_account.id]

        player_obj = user_account.player_obj
        room = player_obj.room
        if room is not None:
            cls.remove_from(player_obj.room, player_obj)
            affected = (o for o in room.contains if o.is_player_obj)
            for o in affected:
                cls.user_hears(o, player_obj, '{} fades out.'.format(player_obj.name))

            LastSeen.create(user_account=user_account, room=room)

    @classmethod
    def get_session(cls, user_account_id):
        session = cls._sessions.get(user_account_id)
        if session is None:
            raise ClientError('No session found. Log in again.')

        return session

    @classmethod
    def client_state(cls, user_account):
        """Given a user account, returns a dictionary of information relevant
        to the game client."""
        player_obj = user_account.player_obj
        room = player_obj.room

        exits = [o for o in room.contains if o.get_data('exit')]
        exit_payload = {}
        for e in exits:
            route = e.get_data('exit', {}).get(room.shortname)
            if route is None: continue

            target_room_shortname = route[1]
            target_room = GameObject.get_or_none(GameObject.shortname==target_room_shortname)
            if target_room is None: continue

            exit_payload[route[0]] = {
                'exit_name': e.name,
                'room_name': target_room.name}

        return {
            'motd': 'welcome to tildemush',  # TODO
            'user': {
                'username': user_account.username,
                'display_name': player_obj.name,
                'description': player_obj.description
            },
            'room': {
                'name': room.name,
                'shortname': room.shortname,
                'description': room.description,
                'contains': [dict(name=o.name, description=o.description, shortname=o.shortname)
                             for o in room.contains],
                'exits': exit_payload,
            },
            'inventory': cls.contains_tree(player_obj),
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
                'shortname': o.shortname,
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

        # TODO add destroy action
        # TODO teleport, either 'home' or 'foyer'

        # admin
        if action == 'announce':
            cls.handle_announce(sender_obj, action_args)

        # chatting
        elif action == 'whisper':
            cls.handle_whisper(sender_obj, action_args)

        elif action == 'look':
            cls.handle_look(sender_obj, action_args)

        # scripting
        elif action == 'create':
            cls.handle_create(sender_obj, action_args)

        elif action == 'edit':
            cls.handle_edit(sender_obj, action_args)
            return

        elif action == 'go':
            cls.handle_go(sender_obj, action_args)
            return

        # inventory commands
        elif action == 'get':
            cls.handle_get(sender_obj, action_args)
        elif action == 'drop':
            cls.handle_drop(sender_obj, action_args)
        elif action == 'put':
            cls.handle_put(sender_obj, action_args)
        elif action == 'remove':
            cls.handle_remove(sender_obj, action_args)
        elif action in SPECIAL_HANDLING:
            # TODO this is utterly filthy, but some commands definitely never
            # need transitive parsing (ie say and contain) but aren't special
            # cased in this if/else chain. we have this artificial check just
            # to avoid falling into the transitive branch. i hate it.
            pass
        else:
            # it's not a pre-defined action. we now want to see if it's
            # targeted at some object.
            args = split_args(action_args)
            if len(args) > 0:
                target_search_str = args[0]
                target = cls.resolve_obj(cls.area_of_effect(sender_obj), target_search_str)
                without_target = ARG_RE.sub('', action_args, count=1).rstrip().lstrip()
                if target:
                    target.handle_action(cls, sender_obj, action, without_target)
                    return

        # if we make it here it means we've encountered a command that objects
        # in the area should all "hear"
        aoe = cls.area_of_effect(sender_obj)
        for o in aoe:
            o.handle_action(cls, sender_obj, action, action_args)

    @classmethod
    def resolve_obj(cls, scope, search_str, ignore=lambda o: False):
        """Given a list of GameObjects as scope, a search string, and an
        optional list of GameObjects to ignore, searches for the first object
        in scope for which .fuzzy_match(search_str) is True."""
        for obj in scope:
            if ignore(obj):
                continue
            if obj.fuzzy_match(search_str):
                return obj
        return None

    @classmethod
    def resolve_exit(cls, room, direction):
        resolved = None
        for o in room.contains:
            if o.is_player_obj: continue

            exits_map = o.get_data('exit')
            if exits_map is None: continue

            route = exits_map.get(room.shortname)
            if route is None: continue

            if route[0] == direction:
                resolved = o
                break

        return resolved

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
        found = cls.resolve_obj(sender_obj.neighbors, action_args, lambda o: o.is_player_obj)

        if found is None:
            raise UserError(OBJECT_NOT_FOUND.format(action_args))

        if not sender_obj.can_carry(found):
            raise UserError(OBJECT_DENIED.format(found.name))

        if found.get_data('exit'):
            raise UserError("You can't pick up an exit, only destroy it.")

        cls.put_into(sender_obj, found)
        cls.user_hears(sender_obj, sender_obj, 'You grab {}.'.format(found.name))

    @classmethod
    def handle_drop(cls, sender_obj, action_args):
        """Matches an object in sender_obj.contains and moves it to
        sender_obj's first contained by object."""

        # TODO this doesn't seem to trigger a state update?

        found = cls.resolve_obj(sender_obj.contains, action_args)

        if found is None:
            raise UserError('You look in vain for something called {}.'.format(obj_string))

        cls.put_into(list(sender_obj.contained_by)[0], found)
        cls.user_hears(sender_obj, sender_obj, 'You drop {}.'.format(found.name))

    @classmethod
    def handle_put(cls, sender_obj, action_args):
        """Called like:

           /put phaser in bag

        we (somewhat disconcertingly) split on ' in '. TODO support quoting
        both object names in case a name ends up with ' in ' in it.

        Moves the first object into second_obj.contains.

        If the player doesn't have execute permission on the container, the
        attempt fails. They also need carry permission for the first object if
        they're grabbing it from the room they're in (instead of their
        inventory).
        """
        match = PUT_ARGS_RE.fullmatch(action_args)
        if match is None:
            raise UserError('Try /put some object in container object')
        target_obj_str, container_obj_str = match.groups()

        target_obj = cls.resolve_obj(
            itertools.chain(sender_obj.contains, sender_obj.neighbors),
            target_obj_str, lambda o: o.is_player_obj)

        if target_obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(target_obj_str))

        if not sender_obj.can_carry(target_obj):
            raise UserError(OBJECT_DENIED.format(target_obj.name))

        container_obj = cls.resolve_obj(
            itertools.chain(sender_obj.contains, sender_obj.neighbors),
            container_obj_str, lambda o: o.is_player_obj)

        if container_obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(container_obj_str))

        if not sender_obj.can_execute(container_obj):
            raise UserError(
                'You try as hard as you can, but you are unable to pry open {}'.format(
                    container_obj.name))

        cls.put_into(container_obj, target_obj)

        cls.user_hears(sender_obj, sender_obj, 'You put {} in {}'.format(target_obj.name, container_obj.name))

    @classmethod
    def handle_remove(cls, sender_obj, action_args):
        """Called like:

           /remove phaser from bag

        we (somewhat disconcertingly) split on ' from '.
        TODO support quoting both object names in case a name ends up with '
        from ' in it.

        Removes the first object into second_obj.contains and adds it to the
        player's inventory.

        If the player doesn't have execute permission on the container, the
        attempt fails. They also need carry permission for the first object.
        """
        match = REMOVE_ARGS_RE.fullmatch(action_args)
        if match is None:
            raise UserError('Try /remove some object from container object')
        target_obj_str, container_obj_str = match.groups()

        container_obj = cls.resolve_obj(
            itertools.chain(sender_obj.contains, sender_obj.neighbors),
            container_obj_str, lambda o: o.is_player_obj)

        if container_obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(container_obj_str))

        if not sender_obj.can_execute(container_obj):
            raise UserError(
                'You try as hard as you can, but you are unable to pry open {}'.format(
                    container_obj))

        target_obj = cls.resolve_obj(container_obj.contains, target_obj_str)

        if target_obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(target_obj_str))

        if not sender_obj.can_carry(target_obj):
            raise UserError(OBJECT_DENIED.format(target_obj.name))

        cls.put_into(sender_obj, target_obj)
        cls.user_hears(sender_obj, sender_obj, 'You remove {} from {} and carry it with you.'.format(
            target_obj.name,
            container_obj.name))

    @classmethod
    def handle_edit(cls, sender_obj, action_args):
        """When a user runs /edit, we don't do a ton on the server. This handler:

           - sets the editing property to user's fk
           - clears the editing property for anything still edited by user
           - sends an OBJECT payload to the client
        """
        # TODO a lot of the editing stuff depends on people only being allowed
        #      to have one active client at a time. i think that's an ok
        #      limitation for now, but we should actually enforce it.

        # we use aoe here because we want to be able to target a current room.
        # usually when resolving (like grabbing stuff) we def don't want to
        # include the current room, just the stuff in it.
        obj = cls.resolve_obj(cls.area_of_effect(sender_obj), action_args)

        if obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(action_args))

        # TODO if we're switching users to the WITCH tab when they run /edit,
        # they might miss these errors. they can always switch back to the main
        # tab though if nothing appears in the WITCH tab.
        if not sender_obj.can_write(obj):
            raise UserError('You lack the authority to edit {}'.format(obj.name))

        if Editing.select().where(Editing.game_obj==obj).count() > 0:
            raise UserError('That object is already being edited')

        # TODO Ensure that part of disconnecting is clearing out Editing table.
        # It should also be cleared out on server start.
        with get_db().atomic():
            Editing.delete().where(Editing.user_account==sender_obj.user_account).execute()
            Editing.delete().where(Editing.game_obj==obj).execute()
            Editing.create(
                user_account=sender_obj.user_account,
                game_obj=obj)

        cls.send_object_state(sender_obj.user_account, obj, edit=True)

    @classmethod
    def send_object_state(cls, user_account, game_obj, edit=False):
        if user_account.id in cls._sessions:
            state = cls.object_state(game_obj)
            if edit:
                state['edit'] = True
            cls.get_session(user_account.id).send_object_state(state)

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
            raise UserError('try /create object-type "pretty name" [additional arguments]')

        obj_type, name, additional_args = match.groups()
        if obj_type not in CREATE_TYPES:
            raise UserError(
                'Unknown type for /create. Try one of {}'.format(CREATE_TYPES))

        return obj_type, name, additional_args

    @classmethod
    def derive_shortname(cls, owner_obj, *strings):
        if len(strings) == 0:
            strings = ['object']
        shortname_tmpl = '{username}/{slugged}'
        shortname = shortname_tmpl.format(
            username=owner_obj.user_account.username,
            slugged='-'.join([slugify(strip_color_codes(s)) for s in strings]))
        if GameObject.get_or_none(GameObject.shortname==shortname):
            obj_count = GameObject.select().where(GameObject.author==owner_obj.user_account).count()
            shortname += '-' + str(obj_count)
        return shortname

    @classmethod
    def create_item(cls, owner_obj, name, additional_args):
        shortname = cls.derive_shortname(owner_obj, name)
        item = GameObject.create_scripted_object(
            owner_obj.user_account, shortname, 'item', {
            'name': name,
            'description': additional_args})
        cls.put_into(owner_obj, item)

        return item

    @classmethod
    def create_room(cls, owner_obj, name, additional_args):
        shortname = cls.derive_shortname(owner_obj, name)
        room = GameObject.create_scripted_object(
            owner_obj.user_account, shortname, 'room', {
            'name': name,
            'description': additional_args})

        sanctum = GameObject.get(
            GameObject.author==owner_obj.user_account,
            GameObject.is_sanctum==True)

        portkey = cls.create_portkey(owner_obj, room)
        cls.put_into(sanctum, portkey)

        return room

    # TODO audit error handling for non-user execution paths. UserErrors and
    # ClientErrors initiating from a script engine and not the server core are
    # going to crash the server.

    @classmethod
    def create_exit(cls, owner_obj, name, additional_args):
        # TODO consider having parse_create_exit that is called outside of this
        # TODO currently the perms for adding exit to a room use write; should we use execute?
        if not owner_obj.is_player_obj:
            # TODO log
            return
        match = CREATE_EXIT_ARGS_RE.fullmatch(additional_args)
        if not match:
            raise UserError('To make an exit, try /create exit "A Door" north foyer A rusted, metal door')
        direction, target_room_name, description = match.groups()
        direction = cls.process_direction(direction)
        if direction not in DIRECTIONS:
            raise UserError('Try one of these directions: {}'.format(DIRECTIONS))

        current_room = owner_obj.room
        target_room = GameObject.get_or_none(
            GameObject.shortname == target_room_name)

        if target_room is None:
            raise UserError('Could not find a room with the ID {}'.format(target_room_name))

        if not (owner_obj.user_account.is_god \
                or current_room.author == owner_obj.user_account \
                or owner_obj.can_write(current_room)):
            raise UserError('You lack the power to create an exit here.')

        # Check if exit for this dir already exists
        current_exit = cls.resolve_exit(current_room, direction)
        if current_exit:
            raise UserError('An exit already exists in this room for that direction.')

        # make the exit and add it to the creator's current room
        with get_db().atomic():
            shortname = cls.derive_shortname(owner_obj, name)
            new_exit = GameObject.create_scripted_object(
                owner_obj.user_account, shortname, 'exit', {
                'name': name,
                'description': description})

            new_exit.set_data('exit',
                              {current_room.shortname: (direction, target_room.shortname),
                               target_room.shortname: (REVERSE_DIRS[direction], current_room.shortname)})
            # exits inherit the write permission from the rooms they are
            # created in
            if current_room.perms.write == Permission.WORLD:
                new_exit.set_perm('write', 'world')
            cls.put_into(current_room, new_exit)

        # Expose the exit to the target room if able
        if owner_obj.user_account.is_god \
           or target_room.author == owner_obj.user_account \
           or owner_obj.can_write(target_room):
            Contains.create(outer_obj=target_room, inner_obj=new_exit)

        return new_exit

    @classmethod
    def create_portkey(cls, owner_obj, target, name=None):
        if name is None:
            name = 'Teleport Stone to {}'.format(target.name)
        description = 'Touching this stone will transport you to'.format(target.name)
        shortname = cls.derive_shortname(owner_obj, name)
        return GameObject.create_scripted_object(
            owner_obj.user_account, shortname, 'portkey', {
            'name': name,
            'description': description,
            'target_room_name': target.shortname})

    @classmethod
    def handle_announce(cls, sender_obj, action_args):
        if not sender_obj.user_account.is_god:
            raise UserError('you are not powerful enough to do that.')

        aoe = cls.all_active_objects()
        for o in aoe:
            o.handle_action(cls, sender_obj, 'announce', action_args)

    @classmethod
    def handle_whisper(cls, sender_obj, action_args):
        action_args = action_args.split(' ')
        if 0 == len(action_args):
            raise UserError('try /whisper another_username some cool message')
        target_name = action_args[0]
        message = ' '.join(action_args[1:])
        if 0 == len(message):
            raise UserError('try /whisper another_username some cool message')
        target_obj = cls.resolve_obj(sender_obj.neighbors, target_name)
        if target_obj is None:
            raise UserError('there is nothing named {} near you'.format(target_name))
        target_obj.handle_action(cls, sender_obj, 'whisper', message)

    @classmethod
    def handle_look(cls, sender_obj, action_args):
        # TODO it's arguable that this should make use of a look action
        # dispatched to a game object, but I kind of wanted reality fixed in
        # place with /look.
        #
        # I'm imagining that I want object descriptions that depend on a
        # GameObject's state, but I think that dynamism can go into an /examine
        # command. /look is for getting a bearing on what's in front of you.

        if sender_obj.is_player_obj:
            msgs = []
            room = sender_obj.room
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
    def move_obj(cls, target_obj, target_room_name):
        target_room = GameObject.get_or_none(GameObject.shortname==target_room_name)
        if target_room is None:
            raise UserError('illegal move') # should have been caught earlier
        if target_obj.is_player_obj and target_obj == target_room:
            cls.user_hears(target_obj, target_obj, "You can't move to yourself.")
            return

        cls.put_into(target_room, target_obj)
        if target_obj.is_player_obj:
            cls.user_hears(target_obj, target_obj, 'You materialize in a new place!')

    @classmethod
    def handle_go(cls, sender_obj, action_args):
        direction = cls.process_direction(action_args)
        current_room = sender_obj.room
        exit_obj = cls.resolve_exit(sender_obj.room, direction)
        if exit_obj is None:
            raise UserError('You cannot go that way.')

        exit_obj.handle_action(cls, sender_obj, 'go', direction)

    @classmethod
    def process_direction(cls, input_direction):
        """
        Given a direction, checks through a list of aliases and returns the true
        direction.
        """

        dir_map = {'north': {'north', 'n'},
                   'south': {'south', 's'},
                   'east': {'east', 'e'},
                   'west': {'west', 'w'},
                   'above': {'above', 'a', 'up', 'u'},
                   'below': {'below', 'b', 'down', 'd'}}

        for direction in dir_map:
            if input_direction in dir_map.get(direction):
                return direction

        return input_direction

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
        inventory = set(sender_obj.contains)
        parent_objs = set(sender_obj.contained_by)
        adjacent_objs = set(sender_obj.neighbors)
        return {sender_obj} | parent_objs | inventory | adjacent_objs

    @classmethod
    def put_into(cls, outer_obj, inner_obj):
        if outer_obj == inner_obj:
            raise UserError('Cannot put something into itself.')
        # TODO for exits, i need to be able to put them into two rooms at once.
        # Right now i'm thinking of just doing a raw Contains call when detecting
        # an exit.
        for old_outer_obj in inner_obj.contained_by:
            Contains.delete().where(Contains.inner_obj==inner_obj).execute()
            for o in old_outer_obj.contains:
                if o.is_player_obj:
                    cls.send_client_update(o.user_account)

        Contains.create(outer_obj=outer_obj, inner_obj=inner_obj)

        outer_obj.handle_action(cls, inner_obj, 'contain',  'acquired')
        inner_obj.handle_action(cls, outer_obj, 'contain',  'entered')

    @classmethod
    def remove_from(cls, outer_obj, inner_obj):
        """This is only useful for player objects for when they disconnect;
        otherwise all object moving is done via put_into."""
        Contains.delete().where(
            Contains.outer_obj==outer_obj,
            Contains.inner_obj==inner_obj).execute()

        outer_obj.handle_action(cls, inner_obj, 'contain', 'lost')
        inner_obj.handle_action(cls, outer_obj, 'contain', 'freed')

        for o in outer_obj.contains:
            if o.is_player_obj and o != inner_obj:
                cls.send_client_update(o.user_account)

    @classmethod
    def user_hears(cls, receiver_obj, sender_obj, msg):
        cls.get_session(receiver_obj.user_account.id).handle_hears(sender_obj, msg)

    @classmethod
    def object_state(cls, game_obj):
        return {
            'shortname': game_obj.shortname,
            'data': game_obj.data,
            'permissions': game_obj.perms.as_dict(),
            'current_rev': game_obj.script_revision.id,
            'code': game_obj.script_revision.code}

    @classmethod
    def handle_revision(cls, owner_obj, shortname, code, current_rev):
        result = None
        with get_db().atomic():
            # TODO this is going to maybe create sadness; should be handled and
            # user gently told
            obj = GameObject.get(GameObject.shortname==shortname)
            result = cls.object_state(obj)

            error = None
            if not (owner_obj.can_write(obj) or owner_obj.user_account == obj.author):
                error = 'Tried to edit illegal object'
            elif obj.script_revision.id != current_rev:
                error = 'Revision mismatch'
            elif obj.script_revision.code == code.lstrip().rstrip():
                error = 'No change to code'

            if error:
                raise RevisionError(error, payload=result)

            rev = ScriptRevision.create(
                code=code,
                script=obj.script_revision.script)

            # TODO i may regret allowing broken code to be saved, but otherwise
            # you essentially can't save works in progress--your work is held
            # hostage in the WITCH pane until it works. There might be a more
            # elegant solution but for now I'm going with allowing buggy code
            # to save.
            obj.script_revision = rev
            obj.save()

            witch_errors = []

            try:
                obj.init_scripting()
            except WitchError as e:
                # TODO i don't actually have a good reason for errors being a
                # list yet
                witch_errors.append(str(e))

            result = cls.object_state(obj)
            result['errors'] = witch_errors

        return result
