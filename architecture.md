# tildemush architecture

## Overview

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

## Data model

An unfortunate tension that exists in the Python world is the coupling of the
Django ORM to the rest of Django. If we want to model users and in-game objects
in such a way that is accessible to Django (ie for user authentication and use
of the admin app), we'll be stuck accessing the same data through the Django ORM
from within the game engine.

It remains to be seen how the Django ORM fares being used in the websocket based
game transactions as opposed to classic HTTP transactions, but I don't think
this is an unreasonable place to start.

## API

### HTTP

- `/world-stats` receive structured data about number of rooms, population, command use
- `/register` create a new character
- `/auth` exchange login information for a token that can initiate a websocket session; this is also passed (instead of a cookie) with HTTP calls
- `/logout` destroy the auth token
- `/reset-password`
- `/delete-character`
- `/initiate` create the two way socket to the game server
- `/disconnect` cleanly close the game server socket

### In-game

In game commands constitute an API of their own, albeit one that is more fluid
and expansive than the HTTP API. They have more to do with game design, and as such reside in [client design documentation](client.md)



