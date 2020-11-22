# some rambling while implementing GameObject

```
# every object needs to tie to a user account for authorizaton purposes

# so what is the lifecycle of a gameobject?

# it exists in perpetuity as a row in the DB. its code exists in a
# ScriptRevision row. Its code isn't necessarily in RAM; if an action
# occurs near it, we need to know if it responds to a certain action.

# If its code isn't in RAM, we need to pull and evaluate its WITCH from the
# DB. The result of that evaluation will exist in RAM. If we've gotten to
# this point, we know there is an instance of GameObject in RAM.

# Given a horse object called Snoozy and a player object called Vilmibm:

# 1. Vilmibm's user account runs "/pet" resulting in "COMMAND pet"
# 2. GameWorld queries for all of the objects that can "hear" that command, including Snoozy
# 3. Snoozy's script_engine is asked if it can handle "pet"
#  a. Snoozy's game object points to a scriptrevision, so we pull it from the DB
#  b. we run the scriptrevision's WITCH and now have a choice: does it
#     instantiate a ScriptEngine or does it call methods on the GameObject
#     instance? It might not matter; on the one hand i like the "code" part of
#     a GameObject being in its own instance, but it's weird to have it
#     divorced from the data stored in GameObject. Ultimately, I like that the
#     (witch) macro is instantiating a new thing: it doesn't need access to an
#     existing gameobject.
#     thus: we instantiate and call add_handler on a scriptrevision
#  c. we now return that, yes, a handler exists for 'pet'
# 4. Snoozy's 'pet' handler is called and is passed Snoozy (receiver) and the player object (sender)
#  a. data is fetched, checked, and set via Snoozy's instance
#  b. Snoozy emits "/say neigh"
# 5. GameWorld queries for all of the objects that can "hear" Snooy's say, including Vilmibm
# 6. Vilmibm's handler for "say" runs
#  a. we check if Vilmibm, the receiver, has a user_account property. If it
#     does, we call its "hears" method and pass say's arguments.
#
# The glaring hole in all this is that we're not dispatching based on
# argument; in other words, we merely heard that "/pet" happened. This is a
# big oversight, I think, but I want GameObjects to be able to respond to
# both transitive and intransitive verbs. For now /pet is intransitive
# (which is counter intuitive) but I'm kind of desperate to see an
# end-to-end PoC running with all these parts.

```
