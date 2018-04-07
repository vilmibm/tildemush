# project plan

## purpose of this document

this is a very rough document i use to track progress and direction for tildemush. the source of truth for what's actually going on in this project is [the project board](https://github.com/vilmibm/tildemush/projects/1) and its linked issues.

the phases are very arbitrary.

project management flow is:

- notes in this file
  - ➡️ notes added to TODO in project board
    - ➡️ notes converted to issues and filled in with checkbox TODO list
    - ⬅️ issue is completed
  - ⬅️ issue is moved to done
- ⬅️ this file updated as needed to reflect new information

## phase 1

- [x] stub websocket handlers
- ~stub http handler~
- [x] basic client with urwid

## phase 2

- [x] connect client to server
  - [x] login
  - [x] register
- [ ] schema design
  - [ ] users
  - [ ] rooms
  - [ ] objects
  - [ ] scripts
  - [ ] game world
- [x] implement auth model
  - ~ident style~
  - [x] username/password style

## phase 3

- [ ] expose game world to client
  - [ ] room presence
  - [ ] announcements
  - [ ] whispers
- [ ] WITCH macro stubs
  - [ ] object scripting
  - [ ] room scripting
- [ ] define game commands

## phase 4

- [ ] UI flesh out
  - [ ] settings
  - [ ] error messaging
  - [ ] WITCH editor
  - [ ] tab completion first pass
- [ ] test harness for testing async interactions
