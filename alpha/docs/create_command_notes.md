# Some raw notes from prepping for the /create command

- should name and description be moved to a GameObject's k/v data? and out of the sql schema?
- should all objects have a script? should scripts exist outside of the objects they describe?
  - in an unorphaned script world, how are scripts shared?

##  TODO exits

## Aside: shortnames

As we talk more about this stuff, I'm thinking there are three useful strings for a given object:

- name
  This string is a "pretty" name for a thing. It likely has multiple words an
  capitalization, like "Medical Bay". Ideally it's mutable but not changed
  often. It is nonunique.
- shortname
  This string acts as an id for an object. It's unique and has no spaces and
  lacks certain special characters. It's like a slug. For example,
  "medical-bay" or "medical-bay-1". Ideally it's immutable.
- description
  This string is a long form description of an object. It can have line
  breaks. It's mutable and potentially frequently changing due to scripts.

For a user wandering the world, they're going to be dealing with the pretty
name. For users creating and editing rooms and exits, they'll want to use
shortnames. At any time, the pretty name can be used in quotes.


## What does /go look like behind the scenes?

- `/go north`
  0. we check the room for an object with a pretty or short name that starts with "north"
  1. we dispatch to it the "go" action
  2. it tells the game world to move the action sender

## how is this stuff set up?

- `/create exit door north`
  - creates a gameobject that responds to the "go" action if action_args is "north"

## How should this be implemented?

0. add support for a /create command with these initial semantics:
   - `/create <type> <pretty name> <addtnl args>`
     where type is one of <room, exit, item>
   - for room, addtnl args is just the description
   - for exit, addtnl args are `<direction> [<room shortname>]`, defaulting to the room the author is in
   - for item, addtnl args are just description
1. for all types, return the shortname of the created thing.
   - room shortnames are a slug of the pretty name, potentially with the author username for deduping
   - exit shortnames are a slug based on the exit direction, room shortname, and possibly room shortname for deduping
   - item shortnames are slug of pretty name, potentially with author username for deduping
2. each type is seeded with a templatized WITCH script that captures the
   names\* and basic behavior. this script can be modified (much) later with the
   `/edit` command.
   - room templatized scripts are no-ops
   - exit templatized scripts have a go handler
   - item templatized scripts are no-ops

\*: a big conceptual hurdle for tomorrow is figuring out how WITCH can be used
to modify persistent aspects of a game object like name and description. right
now scripts are generic and not attached to an specific object by default.
tomorrow, sketch out how script forking will work, since i want scripts to be
one-to-one with objects but also re-usable.


## Thoughts on create_room

This is going to end up nearly a clone of create_item, but where the
resulting GameObject is inserted is different: this doesn't go into
someone's inventory.
open questions:

* where *should* a new room go? Until someone with the authority
  links your initial node, your room is in the void. Options:
 * Have a shared hub room where all new rooms are automatically
   connected via a portkey.
 * Have each player get a private hub they can only access with a
   command, like /home. This hub acts like the hub above, but only
   for the player to which it belongs. When a structure is ready,
   an existing player can link to it. In case the room author doesn't
   clean up the automatic connection to their private hub, we can
   disallow anyone but them from entering the hub.

I like the private hub idea a lot. This also gives players an
automatic homebase like the one they get in Habitat.

* In case a user gets stranded on a node, how do they get back?
 * I propse a /foyer command that teleports someone back to the
   shared foyer.
* Should /create exit be supported first?
 * I'm going to start with /create room...I don't think it matters a
   ton. I recognize I'm procrastinating on move semantics until the
   last possible moment; that's not entirely unintentional. I'm
   hoping to shake out requirements by doing everything I possibly
   can around those semantics first.
