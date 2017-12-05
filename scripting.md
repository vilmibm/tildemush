# Scripting in tildemush: WITCH

This document captures the design of the _tildemush_ scripting language, WITCH,
hereafter stylized as _witch_ to save on shift key presses.

_witch_ stands for Weaving Incantations That Control Homonculi or Writing
Incantations To Control Homonculi.

## Goals

- Easily comprehensible by newcomers to programming
- Tight feedback loop (i.e., editing and execution are both tied into _tildemush_'s GUI)
- Rich set of code templates for seeding new scripts
- Fun

## Guidelines

### Single File Approach

A thing I've noticed again and again with newer programmers is a struggle with
where things go. The idea of a text file (!) that can be executed (!) is already
a big learning step; suddenly by having to consider multiple files, databases,
documentation files, and "the place to go to run code", a neophyte can be
overwhelmed. I've seen this again and again coaching Django Girls and working
with people on the town.

Let's say a user wants to implement a copy of Amy Bruckman's "squirmy
spaghetti", a semi-animate plate of spaghetti that shivers whenever the word
"hungry" is said. Let's further add some state to the spaghetti: it keeps track
of how many times it's seen the word "hungry." Every aspect of Squirmghetti
should fit inside a single file:

- A structured section for saving untyped state. This section, while expressed
  as in-memory and ephemeral storage, provides access to simple persisted
  storage via the _witch_ runtime. For Squirmghetti, this means a single counter
  `hungry_count` that is incremented in the code section of the file.
- Documentation strings, inspired by
  [Python](https://en.wikipedia.org/wiki/Docstring) as well as
  [POD](http://perldoc.perl.org/perlpod.html), provide usage information, author
  information, and other documentation. For Squirmghetti, this will highlight
  the code's author, its fear of the word "hungry,", and how to ask it to
  display its word counter.
- Code. This section of a _witch_ script defines the behavior of the object
  being scripted. It can reference and mutate things defined in its state
  section. For Squirmghetti, this code listens to audible chats for utterances
  containing the string "hungry," emotes at the room it's in, and responds to
  the string "how hungry?" with the number of times the word "hungry" has been
  said.

### No Feature Monopoly

_witch_ is the first class scripting environment for _tildemush_. However,
scripting objects is permitted via external programs as well. While features get
implemented in _witch_ first, the API that _witch_ represents should also be
supported in the other extension languages. Things possible in _witch_ should be
possible anywhere.

### No reliance on editor support

An editor that syntax highlights your code, provides intelligent autocompletion,
or lets you run snippets of code is _awesome_. However, for a newcomer to
programming, this is just more overwhelming noise. The syntax of _witch_ needs
to be clear and readable from a program like `nano`.

## Compilation and Runtime

### Compilation

_witch_ compiles to Python AST.

This decision is to get _witch_ off the ground. Python AST seems like the
fastest and easiest way to get a new programming language off the ground (given
that I have mostly no experience writing a new language).

### Runtime

_witch_'s runtime is just Python with some important caveats. For one, the
special state section of a _witch_ program causes the runtime to initiate,
access, or update the program's state as stored in an RDBMS. Further, the
documentation sections of a _witch** program are pulled out and stored as well
for retrieving help about a program.

## Serialization

_witch_ code is edited from within tildemush. While tildemush will be calling
out to some editor from within its UI (like
[TTBP](https://github.com/modgethanc/ttbp) and
[BBJ](https://github.com/tildetown/bbj)), code is saved to a database.

_witch_ code can be saved as textual data tied to a user's account; care needs
to be taken such that when a user re-opens some _witch_ code they see the file
in the same state as they left it (whitespace warts and all).

## Language and Grammer Spec

**_TODO_**
