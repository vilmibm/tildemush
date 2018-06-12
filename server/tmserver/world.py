import re

from slugify import slugify

from .config import get_db
from .errors import ClientException
from .models import Contains, GameObject, Contains, Script, ScriptRevision
from .scripting import get_template
CREATE_TYPES = {'room', 'exit', 'item'}
CREATE_RE = re.compile(r'^([^ ]+) "([^"]+)" (.*)$')


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
                'exits': {
                    # TODO
                    'north': None,
                    'south': None,
                    'east': None,
                    'west': None,
                    'above': None,
                    'below': None,
                }
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
        if action == 'announce':
            cls.handle_announce(sender_obj, action_args)
        if action == 'whisper':
            cls.handle_whisper(sender_obj, action_args)
        if action == 'look':
            cls.handle_look(sender_obj, action_args)
        if action == 'create':
            cls.handle_create(sender_obj, action_args)
        if action == 'move':
            cls.handle_move(sender_obj, action_args)

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

        # TODO having description be an argument is stupid, maybe?; you can't
        # make anything long form. I think the first change this needs is just
        # dropping description. Want to test what I've just written first,
        # though. I guess for simple things it's handy to not have to drop into WITCH...
        """
        obj_type, pretty_name, additional_args = cls.parse_create(action_args)

        # TODO these can all be collapsed into
        # create_scripted_object(owner_obj, obj_type, pretty_name, addtl_args).
        # The branches here can decide where to put an object.
        create_fn = None
        if obj_type == 'item':
            create_fn = cls.create_item
        elif obj_type == 'room':
            create_fn = cls.create_room
        elif obj_type == 'exit':
            create_fn = cls.create_exit

        # TODO see if repeatedly calling get_db is bad
        with get_db().atomic():
            game_obj = create_fn(sender_obj, pretty_name, additional_args)

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

        obj_type, pretty_name, additional_args = match.groups()
        if obj_type not in CREATE_TYPES:
            raise ClientException(
                'Unknown type for /create. Try one of {}'.format(CREATE_TYPES))

        return obj_type, pretty_name, additional_args

    @classmethod
    def derive_shortname(cls, sender_obj, *strings):
        slugged = [slugify(s) for s in strings] + [sender_obj.user_account.username]
        shortname = '-'.join(slugged)
        if GameObject.get_or_none(GameObject.shortname==shortname):
            obj_count = GameObject.select().where(GameObject.author==sender_obj.user_account).count()
            shortname += '-' + str(obj_count)
        return shortname

    # TODO I think the splitting out of script vs. scriptrevision vs.
    # gameobject ought to be cleaned up...for now to reduce the number of
    # things in flight i'm going with it, but it was originally inteded to
    # have scripts exist outside of GameObject rows.

    @classmethod
    def create_item(cls, sender_obj, pretty_name, additional_args):
        shortname = cls.derive_shortname(sender_obj, pretty_name)
        script = Script.create(
            author=sender_obj.user_account,
            name=shortname)
        # TODO the redundancy of pretty_name and description is due to those
        # things not yet being moved to a gameobject's key value data yet.
        # clean that up.
        script_code = get_template('item', pretty_name, additional_args)
        scriptrev = ScriptRevision.create(
            script=script,
            code=script_code)
        item = GameObject.create(
            author=sender_obj.user_account,
            name=pretty_name,
            description=additional_args,
            shortname=shortname,
            script_revision=scriptrev)

        cls.put_into(sender_obj, item)

        return item

    # TODO rename sender_obj -> owner in this and above method
    @classmethod
    def create_room(cls, sender_obj, pretty_name, additional_args):
        # This is going to end up nearly a clone of create_item, but where the
        # resulting GameObject is inserted is different: this doesn't go into
        # someone's inventory.
        # open questions:
        # * where *should* a new room go? Until someone with the authority
        #   links your initial node, your room is in the void. Options:
        #   * Have a shared hub room where all new rooms are automatically
        #     connected via a portkey.
        #   * Have each player get a private hub they can only access with a
        #     command, like /home. This hub acts like the hub above, but only
        #     for the player to which it belongs. When a structure is ready,
        #     an existing player can link to it. In case the room author doesn't
        #     clean up the automatic connection to their private hub, we can
        #     disallow anyone but them from entering the hub.
        #
        # I like the private hub idea a lot. This also gives players an
        # automatic homebase like the one they get in Habitat.
        #
        # * In case a user gets stranded on a node, how do they get back?
        #   * I propse a /foyer command that teleports someone back to the
        #     shared foyer.
        # * Should /create exit be supported first?
        #   * I'm going to start with /create room...I don't think it matters a
        #     ton. I recognize I'm procrastinating on move semantics until the
        #     last possible moment; that's not entirely unintentional. I'm
        #     hoping to shake out requirements by doing everything I possibly
        #     can around those semantics first.
        shortname = cls.derive_shortname(sender_obj, pretty_name)
        script = Script.create(
            author=sender_obj.user_account,
            name=shortname)
        # TODO the redundancy of pretty_name and description is due to those
        # things not yet being moved to a gameobject's key value data yet.
        # clean that up.
        script_code = get_template('room', pretty_name, additional_args)
        scriptrev = ScriptRevision.create(
            script=script,
            code=script_code)
        room = GameObject.create(
            author=sender_obj.user_account,
            name=pretty_name,
            description=additional_args,
            shortname=shortname,
            script_revision=scriptrev)

        # TODO hub creation
        sanctum = GameObject.get(
            GameObject.author==sender_obj.user_account,
            GameObject.is_sanctum==True)
        portkey = cls.create_portkey(sender_obj, room)
        cls.put_into(sanctum, portkey)

        return room

    @classmethod
    def create_exit(cls, owner, pretty_name, additional_args):
        # TODO
        pass

    @classmethod
    def create_portkey(cls, owner_obj, target, pretty_name=None):
        if pretty_name is None:
            pretty_name = 'Teleport Stone to {}'.format(target.name)
        shortname = cls.derive_shortname(owner_obj, pretty_name)
        script = Script.create(
            author=owner_obj.user_account,
            name=shortname)
        # TODO this additional format is Gross and also is going to make
        # create_* generalization harder later.
        # TODO get_template should just take an arbitrary payload dict to give
        # to format.
        script_code = get_template('portkey', pretty_name, additional_args).format(
            target_room_name=target.shortname)
        scriptrev = ScriptRevision.create(
            script=script,
            code=script_code)
        return GameObject.create(
            author=owner_obj.user_account,
            # TODO deprecating name/desc
            name=pretty_name,
            description='Touching this stone will transport you to'.format(target.name),
            shortname=shortname,
            script_revision=scriptrev)

    @classmethod
    def handle_announce(cls, sender_obj, action_args):
        if not sender_obj.user_account.god:
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
        target_obj = [o for o in room.contains if o.name == target_name]
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
        room = GameObject.get_or_none(
            GameObject.shortname==action_args,
            GameObject.is_sanctum==False)
        cls.put_into(room, sender_obj)
        cls.user_hears(sender_obj, sender_obj, 'You materalize in a new place!')

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
