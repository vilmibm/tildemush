from .errors import ClientException
from .models import Contains, GameObject, Contains

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
            sender_obj.user_account.hears(cls, sender_obj, m)

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
        outer_obj.put_into(inner_obj)

    @classmethod
    def remove_from(cls, outer_obj, inner_obj):
        outer_obj.remove_from(inner_obj)


    @classmethod
    def data_request(cls, user_account, path):
        # TODO generalize a bit
        # TODO add 'world' path for dumping the world state. consider threading
        # since it could lock up the CPU.
        if path == 'roominfo':
            room = user_account.player_obj.contained_by
            return {'name': room.name,
                    'description': room.description,
                    'objects': [dict(name=o.name,
                                     description=o.description)
                                for o in room.contains]}
        elif path == 'playerinfo':
            player_obj = user_account.player_obj
            return {'username': user_account.username,
                    'playername': player_obj.name,
                    'description': player_obj.description}
        else:
            raise ClientException('Unknown data API path {}'.format(path))
