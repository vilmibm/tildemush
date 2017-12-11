# tildemush Gameplay

This document describes the _gameplay_ of tildemush. While largely a social
environment, _tildemush_ is an interactive world with rules. These rules limit
the actions players can take and thus constitute gameplay even if there is no
victory condition or way to "lose" _tildemush_ (except by being a jerk).

## Object crafting

### Limits

To avoid flooding the world with tchotkes, users have a daily (real time) limit
on how many objects they can create per day. They can open an object for
blessing whenever they want, however.

### Ownership

There is an immutable relation between an object and its creator. While its
_owner_ may change, the creator is always the same. If someone would like to
take another person's object and edit its code, they can request a `/clone` of
that object. Cloning counts as creation and counts against the cloning user's
creation quota.

## The world

Rooms have an initial description with further describable components. Rooms,
unlike objects, are purely declarative; any dynamic actions desired in a room
should be handled by [anchored](client.md) objects.

A room interaction might look like:

    /look
    This courtyard is overgrown. It's not overgrown in a cute or intentional way. Bushes, flowers, and trees in various states of decay tumble out from behind crumbling stone walls. You get the sense that this place isn't for you: it's been reclaimed by generations of feral plants.
    /look up
    The sky is barely visible through the overgrown trees.
    /look down
    The ground was once neatly laid cobblestone. Now, it's a rippling sheet of roots and cracked rock. Watch your step.
    /exits
    You can head north, south, and east from here.


- TODO: room description format
- TODO: dig interaction
- TODO: room ownership
- TODO: exit description
- TODO: room identifiers

## Mortality and combat

Right now, there are no plans for mortality or combat. I'd like it to exist, but
I don't consider it needed for the initial release and want to make sure it's
done correctly.
