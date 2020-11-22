from datetime import datetime
from hashlib import md5
import itertools
import re

from slugify import slugify

from .config import get_db
from .constants import DIRECTIONS, REVERSE_DIRS
from .errors import RevisionError, WitchError, ClientError, UserError
from .mapping import render_map
from .models import Contains, GameObject, Script, ScriptRevision, Permission, Editing, LastSeen, ScheduledTask
from .util import strip_color_codes, split_args, ARG_RE

OBJECT_DENIED = 'You grab a hold of {} but no matter how hard you pull it stays rooted in place.'
OBJECT_NOT_FOUND = 'You look in vain for {}.'
CREATE_TYPES = {'room', 'exit', 'item'}
CREATE_RE = re.compile(r'^([^ ]+) "([^"]+)" (.*)$')
CREATE_EXIT_ARGS_RE = re.compile(r'^([^ ]+) ([^ ]+) (.*)$')
PUT_ARGS_RE = re.compile(r'^(.+) in (.+)$')
REMOVE_ARGS_RE = re.compile(r'^(.+) from (.+)$')


class GameWorld:
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
        # We try to clean up orphaned player objects on disconnect, but
        # sometimes exceptions still leave orphaned players. Ideally this next
        # line wouldn't be here but it's going to make development easier:
        Contains.delete().where(Contains.inner_obj==player_obj).execute()

        ls = LastSeen.get_or_none(user_account=user_account)
        room = None
        if ls is None:
            room = GameObject.get(GameObject.shortname=='god/foyer')
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

        Editing.delete().where(Editing.user_account==user_account).execute()
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
            'motd': 'welcome to tildemush',
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
        # The following are commands that have special meaning to the game. Some of them also get
        # passed to objects in a player's scope; some don't. This is pretty ugly right now but it's
        # not worth investing in refactoring until post-beta, I don't think.

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
        elif action == 'read':
            cls.handle_read(sender_obj, action_args)
            return
        elif action == 'mode':
            cls.handle_mode(sender_obj, action_args)

        # movement
        elif action == 'go':
            cls.handle_go(sender_obj, action_args)
            return
        elif action == 'home':
            cls.move_obj(sender_obj, '{}/sanctum'.format(sender_obj.user_account.username))
        elif action == 'foyer':
            cls.move_obj(sender_obj, 'god/foyer')

        # inventory commands
        elif action == 'get':
            cls.handle_get(sender_obj, action_args)
        elif action == 'drop':
            cls.handle_drop(sender_obj, action_args)
        elif action == 'put':
            cls.handle_put(sender_obj, action_args)
        elif action == 'remove':
            cls.handle_remove(sender_obj, action_args)

        # if we make it here it means we've encountered a command to which
        # objects in the area should have a chance to respond.
        aoe = cls.area_of_effect(sender_obj)
        for o in aoe:
            is_transitive, _ = o.handle_action(cls, sender_obj, action, action_args)
            if is_transitive:
                # If a user just wanted to interact with a single object, don't
                # continue allowing other objects to respond to the action.
                break

        # this is going to often be redundant and in the future we should be
        # smarter, but too many cases weren't triggering a client update.
        for o in aoe:
            if o.is_player_obj:
                cls.send_client_update(o.user_account)

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
        aoe = cls.area_of_effect(sender_obj)
        for o in aoe:
            if o.is_player_obj and o != sender_obj:
                cls.user_hears(o, o, '{} picks up {}'.format(sender_obj.name, found.name))

    @classmethod
    def handle_drop(cls, sender_obj, action_args):
        """Matches an object in sender_obj.contains and moves it to
        sender_obj's first contained by object."""

        found = cls.resolve_obj(sender_obj.contains, action_args)

        if found is None:
            raise UserError(OBJECT_NOT_FOUND.format(action_args))

        cls.put_into(list(sender_obj.contained_by)[0], found)
        cls.user_hears(sender_obj, sender_obj, 'You drop {}.'.format(found.name))
        aoe = cls.area_of_effect(sender_obj)
        for o in aoe:
            if o.is_player_obj and o != sender_obj:
                cls.user_hears(o, o, '{} drops {}'.format(sender_obj.name, found.name))

    @classmethod
    def handle_put(cls, sender_obj, action_args):
        """Called like:

           /put phaser in bag

        we (somewhat disconcertingly) split on ' in '.

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

        aoe = cls.area_of_effect(sender_obj)
        for o in aoe:
            if o.is_player_obj and o != sender_obj:
                cls.user_hears(o, o, '{} puts {} into {}'.format(sender_obj.name, target_obj.name, container_obj.name))

    @classmethod
    def handle_remove(cls, sender_obj, action_args):
        """Called like:

           /remove phaser from bag

        we (somewhat disconcertingly) split on ' from '.

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

        aoe = cls.area_of_effect(sender_obj)
        for o in aoe:
            if o.is_player_obj and o != sender_obj:
                cls.user_hears(o, o, '{} puts {} into {}'.format(sender_obj.name, target_obj.name, container_obj.name))

    @classmethod
    def handle_edit(cls, sender_obj, action_args):
        """When a user runs /edit, we don't do a ton on the server. This handler:

           - sets the editing property to user's fk
           - clears the editing property for anything still edited by user
           - sends an OBJECT payload to the client
        """
        # we use aoe here because we want to be able to target a current room.
        # usually when resolving (like grabbing stuff) we def don't want to
        # include the current room, just the stuff in it.
        obj = cls.resolve_obj(cls.area_of_effect(sender_obj), action_args)

        if obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(action_args))

        # TODO #87 these types of errors should appear in the witch error console
        if not sender_obj.can_write(obj):
            raise UserError('You lack the authority to edit {}'.format(obj.name))

        if Editing.select().where(Editing.game_obj==obj).count() > 0:
            raise UserError('That object is already being edited')

        with get_db().atomic():
            Editing.delete().where(Editing.user_account==sender_obj.user_account).execute()
            Editing.create(
                user_account=sender_obj.user_account,
                game_obj=obj)

        cls.send_object_state(sender_obj.user_account, obj, edit=True)

    @classmethod
    def handle_read(cls, sender_obj, action_args):
        """
        When a user runs /read, we take a similar approach as we do to /edit. We use the read perm
        and don't worry about locking anything, though -- we just need to pass a readonly flag to
        indicate that the client shouldn't bother opening a proper editor.
        """
        obj = cls.resolve_obj(cls.area_of_effect(sender_obj), action_args)
        if obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(action_args))

        # TODO #87 these types of errors should appear in the witch error console
        if not sender_obj.can_read(obj):
            raise UserError('You lack the authority to read {}'.format(obj.name))

        cls.send_object_state(sender_obj.user_account, obj, read=True)

    @classmethod
    def send_object_state(cls, user_account, game_obj, edit=False, read=False):
        if user_account.id in cls._sessions:
            state = cls.object_state(game_obj)
            state['edit'] = edit
            state['read'] = read
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

        room.set_perm('carry', 'owner')

        sanctum = GameObject.get(
            GameObject.author==owner_obj.user_account,
            GameObject.is_sanctum==True)

        portkey = cls.create_portkey(owner_obj, room)
        cls.put_into(sanctum, portkey)

        return room

    @classmethod
    def create_exit(cls, owner_obj, name, additional_args):
        """
        Create an exit in the room an actor is in that goes somewhere else. Requires write
        permission in both the current and target rooms. Direction is relative to the current room;
        ie, /create exit "a door" north god/foyer wooden door means "from the current room, make a
        door that goes north to the foyer".
        """
        if not owner_obj.is_player_obj:
            # TODO #180 log
            return
        match = CREATE_EXIT_ARGS_RE.fullmatch(additional_args)
        if not match:
            raise UserError('To make an exit, try /create exit "A Door" north god/foyer A rusted, metal door')
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
            new_exit.set_perm('carry', 'owner')
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
        description = 'Touching this stone will transport you to {}'.format(target.name)
        shortname = cls.derive_shortname(owner_obj, name)
        return GameObject.create_scripted_object(
            owner_obj.user_account, shortname, 'portkey', {
            'name': name,
            'description': description,
            'target_room_name': target.shortname})

    @classmethod
    def handle_mode(cls, sender_obj, action_args):
        try:
            obj_str, permission, value = split_args(action_args)
        except ValueError:
            raise UserError('try /mode object permission value')

        target_obj = cls.resolve_obj(cls.area_of_effect(sender_obj), obj_str)
        if target_obj is None:
            raise UserError(OBJECT_NOT_FOUND.format(obj_str))

        if not Permission.valid_perm(permission):
            raise UserError('invalid permission. valid permissions are {}'.format(
                ', '.join(Permission.PERMISSIONS)))

        if not Permission.valid_value(value):
            raise UserError('invalid value. valid values are {}'.format(
                ', '.join(Permission.VALUES)))

        if sender_obj.user_account != target_obj.author:
            raise UserError("you lack the authority to mess with this object's permissions.")

        target_obj.set_perm(permission, value)
        cls.user_hears(sender_obj, sender_obj,
                       'The world seems to gently vibrate around you. You have updated the {} permission to {}.'.format(
                       permission, value))

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
        """
        This command is handled by the server to allow a user to always have a fixed handle on
        reality. it reports on every visible object (ie, not in a container) in the room the caller
        is in.

        Complementing this command is /examine (TODO #181) which is targeted at a single object and
        can be scripted.
        """
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
            raise UserError('You cannot move to yourself')

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

        for old_outer_obj in inner_obj.contained_by:
            Contains.delete().where(Contains.inner_obj==inner_obj).execute()

        Contains.create(outer_obj=outer_obj, inner_obj=inner_obj)

        for old_outer_obj in inner_obj.contained_by:
            for o in old_outer_obj.contains:
                if o.is_player_obj:
                    cls.send_client_update(o.user_account)

        for o in outer_obj.contains:
            if o.is_player_obj:
                cls.send_client_update(o.user_account)

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
        if receiver_obj.user_account.id in cls._sessions:
            cls.get_session(receiver_obj.user_account.id).handle_hears(sender_obj, msg)

    @classmethod
    def object_state(cls, game_obj):
        code = game_obj.get_code()
        return {
            'shortname': game_obj.shortname,
            'data': game_obj.data,
            'permissions': game_obj.perms.as_dict(),
            'current_rev': game_obj.script_revision.id,
            'code': code}

    @classmethod
    def handle_revision(cls, owner_obj, shortname, code, current_rev):
        result = None
        with get_db().atomic():
            # TODO #87 should be caught and logged to witch error console
            obj = GameObject.get(GameObject.shortname==shortname)
            result = cls.object_state(obj)

            # this is probably bad, but for now we're assuming that
            # REVISION implies a user edited a witch script and closed their
            # editor, meaning they're done editing. In the future other things
            # might use REVISION and this assumption might be bad; in that
            # case, we can add another verb like UNLOCK.
            Editing.delete().where(Editing.user_account==owner_obj.user_account).execute()

            # this is probably wonky now with the live data change and not
            # worth it, but it shouldn't break anything really:
            if obj.script_revision.code == code.strip():
                #  this was originally an error, but it felt weird.
                return cls.object_state(obj)

            error = None
            if not (owner_obj.can_write(obj) or owner_obj.user_account == obj.author):
                error = 'Tried to edit illegal object'
            elif obj.script_revision.id != current_rev:
                error = 'Revision mismatch'

            if error:
                raise RevisionError(error, payload=result)

            rev = ScriptRevision.create(
                code=code,
                script=obj.script_revision.script)

            # i may regret allowing broken code to be saved, but otherwise
            # you essentially can't save works in progress--your work is held
            # hostage in the WITCH pane until it works. There might be a more
            # elegant solution but for now I'm going with allowing buggy code
            # to save.
            obj.script_revision = rev
            obj.save()

            witch_errors = []

            try:
                obj.init_scripting(use_db_data=False)
            except WitchError as e:
                # i don't actually have a good reason for errors being a list yet
                witch_errors.append(str(e))

            result = cls.object_state(obj)
            result['errors'] = witch_errors

        if not result['errors']:
            aoe = cls.area_of_effect(owner_obj)
            for o in aoe:
                if o.is_player_obj:
                    cls.send_client_update(o.user_account)

        return result

    @classmethod
    def handle_map(cls, player_obj):
        return render_map(cls, player_obj.room, distance=2)

    @classmethod
    def add_scheduled_task(cls, obj, interval, units, cb):
        """This method expects to be called in a transaction; specifically,
        one that is wrapping any changes to an object's code and revision."""
        pg_interval = None
        if units == 'hours':
            pg_interval = f'{interval} H'
        elif units == 'minutes':
            pg_interval = f'{interval} M'
        else:
            raise ValueError(f'Got illegal value for units: {units}. Expected hours or minutes.')

        cbhash = md5(cb.__code__.co_code).hexdigest()
        if ScheduledTask.select().where(
                obj=obj,
                cbhash=cbhash,
                revision=obj.revision,
                interval=pg_interval).count() > 0:
            return

        ScheduledTask.create(
                obj=obj,
                cbhash=cbhash,
                revision=obj.revision,
                interval=pg_interval)

    @classmethod
    def next_run_tasks(cls):
        return ScheduledTask.select().where(
                ScheduledTask.last_run+ScheduledTask.interval <= datetime.utcnow())

    @classmethod
    def run_scheduled_task(cls, task):
        # TODO find and run CB
        # I haven't actually planned this out. I'm thinking that add_scheduled_task should also add
        # the task to an in-memory dict of cbs; this way when we re-evaluate the code here we won't
        # re-add it to the db (bc hashing) but it'll go in the in-memory store. Next step is to do
        # the in-memory store. that can even be stored at the game world level..? think that
        # through, it might be premature optimization
        pass
