from .errors import ClientException
from .models import Contains, GameObject, Contains, Script


# questions at the top of my head:

# - should name and description be moved to a GameObject's k/v data? and out of the sql schema?
# - should all objects have a script? should scripts exist outside of the objects they describe?
#   - in an unorphaned script world, how are scripts shared?
# - should i start off today with the /create command? that will force me to do
#   script refactoring and name/desc/shortname stuff. I'm concerned it is too
#   big a of a thing to start with, but if it is, i can back off.

# TODO exits
#
# ## Aside: shortnames

# As we talk more about this stuff, I'm thinking there are three useful strings for a given object:
# - name
#   This string is a "pretty" name for a thing. It likely has multiple words an
#   capitalization, like "Medical Bay". Ideally it's mutable but not changed
#   often. It is nonunique.
# - shortname
#   This string acts as an id for an object. It's unique and has no spaces and
#   lacks certain special characters. It's like a slug. For example,
#   "medical-bay" or "medical-bay-1". Ideally it's immutable.
# - description
#   This string is a long form description of an object. It can have line
#   breaks. It's mutable and potentially frequently changing due to scripts.
#
# For a user wandering the world, they're going to be dealing with the pretty
# name. For users creating and editing rooms and exits, they'll want to use
# shortnames. At any time, the pretty name can be used in quotes.
#
# #####
#
# ## What does /go look like behind the scenes?
#
# /go north
# 0. we check the room for an object with a pretty or short name that starts with "north"
# 1. we dispatch to it the "go" action
# 2. it tells the game world to move the action sender
#
# ## how is this stuff set up?
#
# /create exit door north
# - creates a gameobject that responds to the "go" action if action_args is "north"
#
# ## How should this be implemented?
#
# 0. add support for a /create command with these initial semantics:
#    - /create <type> <pretty name> <addtnl args>
#      where type is one of <room, exit, item>
#    - for room, addtnl args is just the description
#    - for exit, addtnl args are <direction> [<room shortname>], defaulting to the room the author is in
#    - for item, addtnl args are just description
# 1. for all types, return the shortname of the created thing.
#    - room shortnames are a slug of the pretty name, potentially with the author username for deduping
#    - exit shortnames are a slug based on the exit direction, room shortname, and possibly room shortname for deduping
#    - item shortnames are slug of pretty name, potentially with author username for deduping
# 2. each type is seeded with a templatized WITCH script that captures the
#    names* and basic behavior. this script can be modified (much) later with the
#    /edit command.
#    - room templatized scripts are no-ops
#    - exit templatized scripts have a go handler
#    - item templatized scripts are no-ops
#
# *: a big conceptual hurdle for tomorrow is figuring out how WITCH can be used
# *to modify persistent aspects of a game object like name and description.
# *right now scripts are generic and not attached to an specific object by
# *default. tomorrow, sketch out how script forking will work, since i want
# *scripts to be one-to-one with objects but also re-usable.




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
