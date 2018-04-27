from .models import Contains

class GameWorld:

    @classmethod
    def dispatch_action(cls, user_account, action, action_args):
        aoe = cls.area_of_effect(user_account)
        po = user_account.player_obj
        for o in aoe:
            o.handle_action(po, action, action_args)

    @classmethod
    def area_of_effect(cls, user_account):
        """Given a user_account, returns the set of objects that should
        receive events the account emits.
        We want a set that includes:
        - the user_account's player object
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
        room = user_account.player_obj.contained_by
        inventory = set(user_account.player_obj.contains)
        adjacent_objs = set(room.contains)
        return {user_account.player_obj, room} | inventory | adjacent_objs


    # TODO it's arguable these should be defined on Contains
    @classmethod
    def put_into(cls, outer_obj, inner_obj):
        Contains.create(outer_obj=outer_obj, inner_obj=inner_obj)

    @classmethod
    def remove_from(cls, outer_obj, inner_obj):
        Contains.delete().where(
            Contains.outer_obj==outer_obj,
            Contains.inner_obj==inner_obj).execute()

