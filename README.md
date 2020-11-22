# tildemush

is being actively rewritten with the goal of producing a stable beta. for design docs and historical
information, see the `alpha` directory.

# project plan

## beta plan

The alpha version of tildemush proved that it was idea with merit. however, the code is unreadable
and unmaintainable. I figured a lot of stuff out all at once and while it's impressive, actually
getting the code into a state that is maintainable and reliable would be a ton of work. I'm
especially frustrated around the pile of hacks for implementing WITCH and would like to slow down
and try and produce something from scratch instead of relying on an existing lisp-like language.

Further, I've been writing Go full time for the past year. I think it's a far better language for
writing this kind of project and would rather rewrite in that.

I'm thus considering all the work in Python to have been _alpha_ and am now embarking on a _beta_
version of tildemush.

It's unclear to what extent I'll use Projects at this point.


### phase 1

I want to start from WITCH instead of having it come much later in development. I previously started
with networking, then database structure, then game logic, then finally WITCH. This time, I want
WITCH to be the grounding aspect of work.

- [ ] proof of concept lexer/parser
- [ ] event schema
- [ ] basic event bus
- [ ] emit events from WITCH objects

### phase 2

Once I feel like there is a decent foundation for WITCH, I can re-implement the "world" of
tildemush: room support (based on WITCH) and a controller for knowing how events should be routed
based on what is in what room

- [ ] rooms
- [ ] presence

### phase 3

Now, humans must be able to see the world. This phase adds support for special player objects. This
phase must hard-stop at a testing harness that eliminates the problems I had with the prior test
suite; it was very brittle and flaky.

- [ ] players
- [ ] deterministic testing harness

### phase 4

Now that objects can exist, events can be routed, and players can move I want persistence.

- [ ] persistence

### phase 5

The world should be essentially functional at this point, so clients should be allowed to interact
with it.

- [ ] protocol design
- [ ] basic client
- [ ] authentication concerns

### phase 6

If I even get this far, I'll plan more :)
