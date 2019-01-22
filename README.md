# tildemush

## disclaimer

**THIS PROJECT IS STILL IN ALPHA! any docs you find here (with the exception for the `setup` section) are purely hypothetical are not guaranteed to describe any actual state of the system. the only source of truth right now is the code, but you're welcome to peruse the docs to get a sense of the spirit and direction of the project.**

## TOC

- This document: background, purpose, and high level information
- [Architecture](docs/architecture.md)
- [Client design](docs/client.md)
- [The WITCH in-game scripting language](docs/scripting.md)

## dev instance

the town is running a development version of tildemush. you can connect from tilde.town:

    mkdir ~/.config/tildemush
    echo '{"server_port": 10014, "server_host": "mush.tilde.town"}' > ~/.config/tildemush/config.json
    tmclient

This instance is volatile (ie it's liable to go down or have its database wiped ⚠️ **at any time** ⚠️ so use at your own risk. it's also completely undocumented; if you want to know how things work, you'll have to look at tildemush's code.

## requirements

* `python 3.6+`
* `pip`
* `postgresql`

## setup

* `python -m virtualenv venv` - create a virtualenv in the project directory
* `source venv/bin/activate`
* `cd server && pip install -e ".[testing]" && cd ..`
* `cd client && pip install --process-dependency-links -e ".[testing]" && cd ..`
* setup `postgres` (see below)

### postgres setup (Arch linux)

[https://wiki.archlinux.org/index.php/PostgreSQL](https://wiki.archlinux.org/index.php/PostgreSQL)

* `sudo su postgres`
* `initdb --locale $LANG -E UTF8 -D '/var/lib/postgres/data'`
* `sudo systemctl enable postgresql` - configure postgres service to start on boot
* `sudo systemctl start postgresql.service` - start postgres service
* `createuser tildemush -W` (will prompt for password, use `tildemush`)
* `createdb tildemush -O tildemush`
* `createdb tildemush_test -O tildemush`

### postgres setup (without sudo)

See [running a little postgres database without sudo](a_little_postgres.md).

## running

**NB: if you are running the server on any OS except linux64, mapping will not work!**

* `tmserver --debug` to start the server
* `tmclient` in another terminal to start a client

## testing

**NB: if you are running the server on any OS except linux64, mapping will not work!**

* `TILDEMUSH_ENV=test pytest`

## Purpose and Goals

An original guiding principle of tilde.town is to re-examine "old" ideas using
newer technology and new perspectives on society.

The town itself is a combination of several "old" things (BBSs, time shared
Unix, Geocities) and several "new" things (Amazon Web Services, high level
programming languages, HTTP APIs). I put old and new in quotes since things
aren't so sequential nor cut and dry; ideas flow into each other over time and
take on new forms.

This project, _tildemush_, is another combination of the "old"
([MUSH](https://en.wikipedia.org/wiki/MUSH), command
line interfaces), and the "new" (modern scripting languages, advances in UX,
HTTP APIs, relational databases).

_tildemush_ is purposefully a greenfield project. A lesson I've learned running
tilde.town is that people who have grown up on the web and with graphical
interfaces take a different and freer approach to command line interfaces. They
are not constrained by the arcane pain of low level terminal programming. They
are not constrained by low bandwidth (ie, a few bytes per second) or hourly
internet costs. They're building interfaces that are more intuitive and natural
to contemporary users.

The urgency of this project struck me while I was reading Howard Rheingold's _The
Virtual Community_ after dealing with some frustrating IRC administration. IRC
serves a purpose and has utility, but as a small social community with a fairly
high level of trust we use approximately 10% of IRC's features. Meanwhile, I see users
working to enhance their mode of expression beyond merely `/say` and `/me`. We
have bots that remind you how loved you are, bots that dispense hugs, commands
for generating streams of rainbows and hearts. I see a _tension_ between the technical
complexity of IRC (which we have never demonstrated need for in three years) and
our desire, as a community, to express ourselves.

Meanwhile, reading _The Virtual Community_, I realized how naturally a MUD/MUSH allowed
for this expression; and how the ability to script life into objects let users
build on a rich foundation of expression.

Thus, the goals of _tildemush_:

- A MUSH built with contemporary tooling (Python)
- Extensible by users, even those unused to programming
- A beautiful, intuitive, and text-based UI
- A rich TUI administrative interface

## Guiding Quotes

> Designing human-computer experience isn't about building a better desktop.
> It's about creating imaginary worlds that have a special relationship to
> reality--worlds in which we can extend, amplify, and enrich our own capacities
> to think, feel, and act.

-> -- <cite>Brenda Laurel, _Computers as Theatre_</cite

> Let's have a little thought experiment here. All right, you're playing in a virtual world. And it's got these pictures, they're looking pretty good. And you think, "Oh, that's pretty good." And you think, "I like these pictures and that's pretty good." And it's a--and it's a 3D world, but I'm only seeing it in 2D on a screen so maybe if I got like a little headset on and put it on, now I can see it in 3D. But if I move my head a bit too much--oh well, maybe if we put little sensors on, so I can move my head. Yes, now, I can see it properly, yes. It's all here. But I'm still only seeing things and maybe I could have maybe some feeling as well. So I put a little data glove on and, "Oh, yes. Oh, it feels warm. Oh, that's good." But I'm still--I'm not hearing things. I'll put some goggles on. And I haven't got this sense of being in a place. I maybe--I want to be able to move. So I say, "Well, let's get these big like-coffin things and fill them full of these gels. And I'll take off all my clothes and put on all of these different devices and I'll lie down on it and it pull it--these electric currents through and make it feel hard or soft. So, it gives me the impression that I'm actually walking through grass because it's generating. And now, I'm beginning to feel I'm really in one of these places. But of course, really what's all that's happening here is that my senses are being fooled into this. What would happen if I was maybe cut out the whole business with the fingers and they stick a little jack in the back of your head and it goes right into the spinal cord and then you're talking straight to the brain there? All the senses that come into your brain, they're all filtered and they're used to create a world model inside your head and your imagination. But if you could talk straight to that imagination and cut out all the senses, then you would--it would be impossible to ignore it. You couldn't say, "Oh, that's just an image of a dragon." That would be a dragon. And if there was some kind of technology which could enable you to talk straight to the imagination, well, there is. 
>
> **It's called text.**
>
> -- <cite>Richard Bartle, as interviewed in Get Lamp (emphasis added)

> The future is already here--it's just not very evenly distributed.
>
> -- <cite>William Gibson, 1993</cite>

> ...artifacts have politics. The change in the software encouraged different styles of interaction, and attracted a different type of person. The ethics of community _emerged_. The design of the software was a strong factor in shaping what emerged.
>
> -- <cite>Amy Bruckman, as quoted in The Virtual Community by Howard Rheingold

> This perpetual toggling between nothing being new, under the sun, and everything having very recently changed, absolutely, is perhaps the central driving tension of my work.
>
> -- <cite>William Gibson, 2012</cite>


## Never Asked Questions

### Why are you calling it a MUSH and not a MUD?

It's true that MUSH most accurately refers to a codebase and not a style of
application. However, despite this (and despite the fact that the first "mush"
was called "tinymud"), I am using MUSH to refer to a program that focuses more
on socializing than gameplay elements like combat.

While it's entirely possible that _tildemush_ will have the features of a MUD
(ie hitpoints and combat), the priority of the program is to encourage
socialization and expression.

### What is the official expansion of MUSH for this project?

Multi User Shared Hallucination

### Why not script tildemush with $language?

_tildemush_'s [scripting engine](scripting.md) is geared towards beginner programmers. The
ultimate goal is for someone to script the behavior of some object without even
realizing they are doing proper programming.

However, a secondary goal is exposing hooks that allow _tildemush_ to be
scripted from other languages. More advanced programmers can take advantage of
this to create more sophisticated things.


### Text is too old fashioned. Why not a GUI?

Text is liberating. Text is accessible. Text leaves room for your imagination to
fill in the blanks. There is no virtual reality more real than your own imagination.

### tildemush is a long word, is there a shorter one?

In my head I affectionately refer to it as _tush_ so you're welcome to say that
if it amuses you.

### Why can't I use telnet?! Why do I have to use your client?!

[Telnet](https://en.wikipedia.org/wiki/Telnet) is awesome. However, it carries a
big pile of baggage, user interface wise. It's too brittle and too unsafe for
this project. Instead, a custom [urwid](http://urwid.org/) client will interact with a [websocket](https://websockets.readthedocs.io) API.

### Why websockets?

Websockets come from the HTTP world. HTTP is, at this point, a lingua franca we are stuck with. It has many, many
shortcomings, but it is understood by many and easy to reason about. Further,
while _tildemush_ itself will not have a GUI, a websocket-based API means we can easily
report on the state of the world via a website. Finally, getting to use HTTPS is an advantage; while like all crypto tools its UX is funamdentally confusing, it's better than many.


## Acknowledgements

- <3 to All the MU*ers who have come before
- <3 to the tilde.town community
- <3 to my computer science cohorts from my college days; your _autonomy_ project has always been a huge inspiration to me
- a lot of my enthusiasm for this project comes from [murepl](https://github.com/vilmibm/murepl), to date one of my proudest projects.

## Author

the _tildemush_ project is lead by [vilmibm](https://tilde.town/~vilmibm).

## Licensing

All code licensed under the terms of the GPLv3. All documentation and other
artifacts are licensed CC-BY-NC.
