# tildemush architecture

## Logging

- What should be ephemeral? What should be logged?

  Given a monolithic server, I'm comfortable with adding logging organically.
  The more the better, with attention to info/debug/error levels.

- Should user actions be replayable?

  This made sense in murepl where user constructs (rooms) were only changed
  through atomic commands. WITCH allows for dynamic change in game objects,
  which means that commands only make sense at a given time (corresponding to
  the state of objects in the system). We don't get visibility into how objects
  change in between invocations of the WITCH IDE.
  
  There is, theoretically, a way to capture this by having a sense of a global
  tick counter and treating all WITCH programs as immutable. A save of a WITCH
  program creates a brand new game object corresponding to that code. This is
  super intriguing but also getting us into research paper realm. I'm
  comfortable not having a replayable world.
  
- How should logs be stored?

  We have Postgresql. I'd rather use it than have to punt on file storage and
  rotation later. Given the distributed complexity of tildemush I'd like robust
  (stored in a schema'fied table) logging up front. It's not hard, but it is a
  bit boring.
  
## Game server

The monolithic server starts a websocket server listening on the game port. This
event loop handles client connections and requests for game world data. All
interactions with the server happen from within the tildemush client. Strong
versioning is required on both the client and server side.

## Repository structure

To the extent that it is possible, tildemush exists in a single repo. rough
sketch:

    - tildemush
     |- docs
     |- Makefile
     |- client
     | |- setup.py
     | |- tmclient
     |- configure
     |- CONTRIBUTING.md
     |- LICENSE
     |- README.md
     |- server
     | |- setup.py
     | |- tmserver

## Configuration

`~/.tildemush.json` to start. No need to overengineer. In-client editing should
be supported.

## Client

Client should take inspiration from older school textual apps but incorporate
newer ideas around responsiveness and layering. A user should never feel lost; a breadcrumb trail should always point them back where they came from.

Screens:

- Main window, where commands are input
- Configuration screen, for editing `~/.tildemush.json`.
- Admin screen, for checking logs and managing user accounts


## Sketch 2

Coming back to this, I'm really not thrilled about using Django at all. There are a few reasons:

- Coupling to ORM, as already mentioned
- Disconnect between Django's HTTP based auth model and our 80% non-HTTP traffic model
- Leaving almost all of Django's features unused

I'm fine abandoning it. Especially because for any administrative tasks, I want to do the work of accomplishing them from *within* tildemush; the more dogfooding the better.

I'm further feeling weird about websockets for this but I like the level of
abstraction they provide. Someone can roll by and call me a noob I guess but I'm
okay with it.

so not much has changed, and i think phase one is:

- a monolithic Python game server
 - accepts websocket connections
 - websocket responses handled by `asyncio`
- simple http handler
 - for dump of public world stats
 - for status info
- linux centric, town-native client in Python (see `asciimatics`)
 - responsive
 - $EDITOR interop for WITCH
 - pager integration for admin stuff
- admins auth like any other user, but get extra tooling in client
 - dump of world state, including non-public info
 - player account management

## Sketch 1

### Overview

_tildemush_ is not intended to support more than around a hundred concurrent
users (even that many users would be pushing up against my wildest notions of
popularity).

To this end, it is designed with few components: 

- a monolithic game server in Python using `asyncio`
  - exposes an HTTP/JSON API for authentication and latency-tolerate read operations
  - exposes a websocket API for receiving client input and sending world events
- an administrative Django application for reviewing user account and the state of the world
  - just the django admin
  - possibly a single page usage statistics report
- a linux-centric, town-native client written in Python (probably using `asciimatics`)

All state is persisted in PostgreSQL. A caching layer should not be initially necessary.

### Data model

An unfortunate tension that exists in the Python world is the coupling of the
Django ORM to the rest of Django. If we want to model users and in-game objects
in such a way that is accessible to Django (ie for user authentication and use
of the admin app), we'll be stuck accessing the same data through the Django ORM
from within the game engine.

It remains to be seen how the Django ORM fares being used in the websocket based
game transactions as opposed to classic HTTP transactions, but I don't think
this is an unreasonable place to start.

### API

#### HTTP

- `/world-stats` receive structured data about number of rooms, population, command use
- `/register` create a new character
- `/auth` exchange login information for a token that can initiate a websocket session; this is also passed (instead of a cookie) with HTTP calls
- `/logout` destroy the auth token
- `/reset-password`
- `/delete-character`
- `/initiate` create the two way socket to the game server
- `/disconnect` cleanly close the game server socket

#### In-game

In game commands constitute an API of their own, albeit one that is more fluid
and expansive than the HTTP API. They have more to do with game design, and as such reside in [client design documentation](client.md)



