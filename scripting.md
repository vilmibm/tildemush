# Scripting in tildemush: WITCH

This document captures the design of the _tildemush_ scripting language, WITCH,
hereafter stylized as _witch_ to save on shift key presses.

_witch_ stands for Weaving Incantations That Control Homonculi or Writing
Incantations To Control Homonculi.

## Goals

- Easily comprehensible by newcomers to programming
- Tight feedback loop (i.e., editing and execution are both tied into _tildemush_'s GUI)
- Rich set of code templates for seeding new scripts
- One way to do things
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
documentation sections of a _witch_ program are pulled out and stored as well
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

### Sketch 1

The following is my first pass at notes for what a _witch_ program might look
like.

```
object "squirmghetti" by "vilmibm" {
  doc { 
    this object listens for the word 'hungry' and keeps track of how many times 
    it has heard it. it also emotes when it hears the word. if it hears the question  
    'squirmghetti how hungry?' it will report on its hungry counter.
  }
  
  describe {
    A plate of spaghetti.
  }

  data {
    "counter": 0
  }

  hears "hungry" {
    this.run("/do squirms uneasily...")
    set("counter", get("counter") + 1)
  }
  
  hears "squirmghetti how hungry?" {
    this.run("/say $(get("counter"))")
  }
}
```

The above example is fairly simplistic; it doesn't feature any interaction with
any player nor does it show taking information from the world around it.
However, it lays out a way of structuring the code: directives followed by
bracketed blocks that contain various things.

I went back and forth on how to issue game commands; on the one hand, i like the
brevity of something like:

       `/do squirms uneasily`
   
I chose the more verbose `this.run` so we have room later to say `player.run`,
since an aspect of `tildemush` objects is that they should be able to augment
their possessor's abilities.

#### Observations / questions

0. **are the various directives too inconsistent?** In this design, each
   directive has different semantics. On the one hand, the semantics make sense
   for each directive; on the other, knowing how one works doesn't really clue
   you into the others. I think I'm okay with this inconsistency; it keeps the
   number of syntactical elements down (ie if `doc` remains a directive like
   this we don't need some kind of syntactical indicator for documentation)
1. **should the data accessors/mutators be namespaced? ie `data.get` and
   `data.set`?** Dot syntax may be pretty confusing to a beginner, but if we're
   already going to have `player.run` and `this.run` then it seems like it's
   good to be consistent here.
2. **how should wildcarding and capturing be handled?** In this example, it's
   assumed that the `hears` string occurs anywhere in a message to the object's
   room. Seems like things should either be: regex support, basic non-greedy \*
   wildcarding with parenthetical captures. I think regexes are going to be too
   much to learn; the latter choice seems good enough for most cases.
3. **The data directive is kind of ugly.** The `0` is an initial value, but I'm
   not sure if that is clear.
4. **While not a whitespace delimited language like Python, we use \n instead of ;**
5. **This is starting to look like a Ruby DSL**. That's probably due to my time
   at Puppet. I think starting with a Ruby DSL is a bad foundation; while more
   work up front, compiling to Python AST is going to lead to more reliable
   compiling and error reporting. I think it's okay to _look_ like a Ruby DSL in
   some ways but I don't want to implement that way.
6. **The initial, outer `object` directive is pre-seeded on the first /bless.** A
   program's name matches the object's name and the author is the player who
   created the object. I'm imagining a flow like this:
   
       /create squirmghetti
       **The air crackles around you and in your outstretched hand a squirmghetti appears. Whatever that is.**
       **squirmghetti added to your inventory.**
       /bless squirmghetti
7. **The object directive suggests a very tight coupling between WITCH scripting
   and game objects.** This is intentional. A _witch_ script shouldn't have
   meaning outside of an object context.
   
### Sketch 2

SEE: [Discussion about more interactive objects with ~selfsame](https://gist.github.com/selfsame/c895dc90429c035ea611932c80f30dc2)

```
object "horse" by "vilmibm" {
    description {
        A friendly horse you can ride. If angered, it can attack, so be careful. It loves to eat oats.
    }
    data {
        "rider": ""
        "pestered": 0
    }
    every 10 minutes {
        this.say("Neigh.")
    }
    action "get" {
        # override an attempt to put this object into an inventory
        stop
    }
    action "pester" {
        # `data` refers to the data store for this object
        # `this` refers to the object.
        # `subject` refers to the player or thing that performed the action
        # `room` refers to the room the object currently exists in
        if data.get("pestered") > 5:
            this.do("attack {subject.name}")  # for this to have any effect, 
                                              # the subject must have an attack action defined.
            room.say("The horse angrily rears up at {subject}. After a moment of huffing, it calms down.")
            data.set("pestered", 0)
        else:
            room.say("The horse glares at you.")
    }
    action "examine" {
      if data.get("rider") != "":
        room.say("A friendly horse ridden by {data.get('rider')}")
      else:
            room.say("A friendly horse.")
    }
    action "ride" {
        if data.get("rider") != "":
            room.say("{data.get('rider')} is already on the horse.")
            stop
        if data.get("pestered") > 0:
            this.do("snort")
            room.say("The horse seems annoyed. Perhaps try again later.")
            data.set("pestered", 0)
            stop
        room.say("{subject.name} climbs up on the horse.")
        data.set("rider", subject.name)
    }
    action "dismount" {
        if data.get("rider") == "":
            stop
        data.set("rider", "")
        room.say("{subject.name} hops down from the horse.")
    }
    action "feed" (thing) {
        room.say("The horse happily gobbles up {thing}.")
    }
}
```

a session with the horse and a player named _vilmibm_:

```
*** horse says "Neigh."

/do pester horse
*** The horse glares at you.

/do pester horse
*** The horse glares at you.

/do pester horse
*** The horse glares at you.

/do pester horse
*** The horse angrily rears up at vilmibm. After a moment of huffing, it calms down.

/do feed horse grains
*** The horse happily gobbes up grains.

/do ride horse
*** vilmibm climbs up on the horse.

/do ride horse
*** vilmibm is already on the horse.

/do examine horse
*** You see a friendly horse ridden by vilmibm

/do dismount horse
*** vilmibm hops down from horse.

/do pester horse
*** The horse glares at you.

/do ride horse
*** horse says "Snort."
*** The horse seems annoyed. Perhaps try again later.
```

## Sketch 3

What if we just used Hy macros? Something like:

```hy
(item "horse" by "vilmibm"

  (description 
    "A friendly horse you can ride. If angered, it can attack,
    so be careful. It loves to eat oats.")

  (data 
    {"rider" ""
    "pestered" 0})
 
  (every (random-number 90) minutes
    (script 
      (self.say "Neigh.")))
      
  (action "get"
    (description "Override the get action so horse can't be put in inventory.")
    (script
      (stop)))
    
  (action "pester"
    (description "Play with the horse's tail or tug on its ears.")
    ; `data` refers to the data store for this object
    ; `self` refers to the object.
    ; `subject` refers to the player or thing that performed the action
    ; `room` refers to the room the object currently exists in
    (script
      (if (greater-than (data.get "pestered") 5)
        (do
          (self.action "attack {subject.name}")
          (data.set "pestered" 0))
        (room.say "The horse glares at you.")
      )))
      
  (action "examine"
    (script
      (room.say "{self.description}")
      (if (not-equal (data.get "rider") "")
        (room.say "{(data.get "rider")} is riding the horse."))))
        
  (action "ride"
    (description 
      "Attempt to mount the horse. It might not work if the horse is annoyed 
      or if there is already a rider.")
      
    (script
      (if (not-equal (data.get "rider") "")
        (do
          (room.say("{(data.get "rider")} is already on the horse."))
          (stop)))
          
      (if (greater-than (data.get "pestered") 0)
        (do
          (self.action "snorts angrily")
          (room.say "The horse seems angry...")
          (stop)))
          
      (room.say "{subject.name} climbs up on the horse.")
      (data.get "rider" subject.name))

  (action "dismount"
    (description
      "Get off the horse.")
      
    (script
      (if (equal (data.get "rider") "")
        (stop))
      
      (data.set "rider" ""))
      (room.say "{subject.name} hops down from the horse."))

  (action "feed" [thing]
    (description
      "Feed the horse something.")

    (script
      (if (equal thing "oats")
        (do
          (room.say "The horse seems very happy!")
          (data.set "pestered" 0))
        (room.say "The horse happily gobbles up {thing}"))))
```

I think I'm going with this route.

It's far easier to implement and more consistent than the brand new language I
was constructing.

I'm worried the s-expressions might be a bit daunting to beginners; but I know scheme is frequently a pedagogical language and also the general lack of confusing syntax is awesome.

Notes:

- `(equal x y)`, `(not-equal x y)`, and `(greater-than x y)` are not in native Hy; I'd be implementing them.
-  I opted for the less lispy `(self.action)` form (instead of `(.action self)` since it seems much more clear for a learner)
- I'm torn about the `(script)` macro's name. It could just be a `(do)` but it will make writing the overall macro easier.

## Sketch 4 -- room definition

```hylang
(room "garden" by "vilmibm"

  (description
    "A quiet, lush garden. Flowers and vegetables of every color sprout up
    along a simple, brick path. Thick green grass carpets the rest of the area.
    There is a small table with a steaming teapot and a rustic chaise lounge 
    chair next to it.")
    
  (has "teapot" by "vilmibm")
  (has "chaise lounge" by "vilmibm")
    
  (look "up"
    (script
      (if world.evening
        (subject.tell 
          "You can make out strange constellations above you. 
          The stars are bright and clear.")
        (subject.tell 
          "The sky is a pleasant blue color here. 
          A few clouds dot the expanse above you."))))
      
  (every (random-number 60) minutes
    (script
      (self.say "Birdsong breaks the silence."))))
```

I'm thinking room creation can start like this:

```
/add-room "garden"
*** You imagine vilmibm's garden. You get the sense that it's floating out there.
/link-room "west" "garden"
*** vilmibm's garden can now be accessed to the west.
/unlink-room "west" "garden"
*** vilmibm's garden can no longer be accessed to the west.
/remove-room "garden"
*** You hear a far off rumbling. The "garden" room is no more.
/remove-room "basement"
*** Error! you are vilmibm, and you don't own the room "basement".
```
