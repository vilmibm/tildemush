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
        if action == 'announce':
            cls.handle_announce(sender_obj, action_args)
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
            o.handle_action(cls, sender_obj, 'say', action_args)


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

