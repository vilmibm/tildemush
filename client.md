# tildemush client

## TUI

### Principles

The fundamental UX principles of _tildemush_'s TUI are:

- **discoverability** Users should know, without pressing a single button, how
  to get help or learn more about the interface. the `micro` editor does this
  very well: instead of listing out a bunch of commands like `nano`, it tells
  you how to toggle a command list as well as how to get more detailed help.
- **clear feedback** Errors should suggest paths to remediation.
- **frequent activity** A failing(?) of many TUIs is giving the appearance of
  still silence when activity is happening slightly out of sight. I posit that
  without stooping to the addiction/stimulation driven approach of contemporary
  graphical social media we can make decisions that hint at activity outside of
  a user's current room or just by displaying nice environmental information
  during quiet periods.

### Screens

- Initial splash screen with ascii art and information
- Character login screen
- Main game UI
- [witch](scripting.md) editing modal
- Character information modal (inventory listing, examine output, bio editing)
- Preferences / account modal
- Help area (reference + tutorials)

#### Main Game UI

The primary screen users will be staring at needs to be multi-paned, responsive to input, and nice to look at.

    _______________________________
    | top bar[1]                  | 
    |-----------------|-----------|
    | main area[2]    | status[5] |
    |                 |           |
    |                 |           |
    |-----------------|-----------|
    | command area[3]             |
    |-----------------------------|
    | help area[4]                |
    -------------------------------

- **[1] top bar** Shows a kind of "topic" set by admins, as well as connection
  information (ie total connected users, current character's name)
- **[2] main area** Where chats, emotes, and any other "live" information
  scrolls through
- **[3] command area** Where commands are input.
- **[4] help area** Where hints about what to do / how to find more help are
  displayed
- **[5] status area** Information about the current room, its occupants, and the
  user's inventory
  
  
### Open UI questions

- Should whispering get its own modal? I think whispers should take place in the
  main area with an obvious prefix / color change.
- Should various actions get key chords? Or all be based on `/` commands? 

## In game commands

- `/dig` create a new room, assigning its ownership to the user
- `/destroy` destroy a created object
- `/create` fabricate a new object
- `/bless` open up an object for scripting
- `/say` audibly chat to your current room. default action for entered text.
- `/yell` be loud; chats to your current room, but other rooms hear indistinct yelling from your room. shortcut is `**`
- `/emote` use a predefined non-verbal action (potentially at another user) shortcut is `!`
- `/whisper` send a private message to a nearby user. shortcut is `. `
- `/do` free-form "character does x"
- `/get` pick up an item in your current room
- `/examine` get item info for something in your current room or inventory; get info on a user
- `/look` get room info
- `/drop` drop an item
- `/wear` add something to your "is wearing" description
- `/unwear` remove something from your "is wearing" description
- `/wield` carry an item in your hands
- `/unwield` put away an item
- `/quit` end game socket session and quit client

As long as the command isn't reserved, items can provide new actions to users.
For example, an `amulet of hugs` can bestow the `/hug` command specifically when
worn.
