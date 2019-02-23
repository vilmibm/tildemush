; TODO support additional args, here. right now, they have to be one big string.
; TODO #195 rewrite tell-sender to be whispering
(defmacro tell-sender [action args] `(witch-tell-sender sender ~action ~args))
(defmacro move-sender [direction] `(witch-move-sender sender ~direction))
(defmacro teleport-sender [target-room-name] `(witch-teleport-sender sender ~target-room-name))

(defmacro about [docstring]
  `(add-docstring ~docstring))

(defmacro has [data]
  `(ensure-obj-data ~data))

(defmacro allows [perm-dict]
  `(set-permissions ~perm-dict))

(defmacro provides [command-string &rest actions]
  `(add-provides-handler
     ~command-string ; Potentially with $this or $object
     (fn [this sender command-string arg-string]
       ; TODO figure out how to handle the dynamic object naming from command string
       ; binding from kwargs at runtime is a no go unless i want to fall back
       ; on eval; but that would be prevented by asteval at runtime. my earlier
       ; approach might work? it's breaking my brain some, but if i can produce
       ; the simple case of a metaprogrammed setv i might get it to work?
       (setv arg arg-string)
       (setv args (split-args arg-string))
       (setv from-me? (= this sender))
       ~@actions)))

; You'll note the weird (setv noop) in the next two macros. This is a hideous
; hack. If given only a single form, Hy's (fn) uses a Lambda AST node. Given
; multiple forms, it creates a named function. asteval doesn't support Lambda at
; all, so we do a noop setv to trick Hy into making a named function. If you
; think this is brittle and likely to fail as Hy changes you'd be right!

(defmacro hears [hear-string &rest actions]
  ; Astute readers might notice that you could implement this as a provides
  ; handler for "say" and then do the wildcarding in the witch code. I chose to
  ; go this route purely because it's conceptually easier to think about things
  ; this way. An advanced programmer who wants regex-based matching can always
  ; add a provides handler for say and totally do that.
  (setv noop (gensym))
  `(add-hears-handler
     ~hear-string
     (fn [this sender heard]
       (setv noop 0)
       ~@actions)))

(defmacro sees [see-string &rest actions]
   ; Astute readers might notice that you could implement this as a provides
   ; handler for "emote" and then do the wildcarding in the witch code. I chose to
   ; go this route purely because it's conceptually easier to think about things
   ; this way. An advanced programmer who wants regex-based matching can always
   ; add a provides handler for emote and totally do that.
   (setv noop (gensym))
   `(add-sees-handler
     ~see-string
     (fn [this sender saw]
       (setv noop 0)
       ~@actions)))

(defmacro incantation
  [_ author-username &rest directives]
  directives)

; what follows is a maximalist example of all the features i'd like witch to have
; N.B. tell-sender in this draft sends a whisper to the sender. the current version of tell-sender
; in the code is being deleted.
; (incantation by vilmibm
;   (about "This script defines a silly, kind of evil book. It is intended to
;   illustrate every feature that WITCH offers.")
;   (has {"name" "the necronomicon"
;         "description" "a book bound in flesh seething with undead energy."
;         "pronouns" ["it" "it" "its"]
;         "souls" []
;         "log" []})
;
;   (allows {"read" "world"
;            "write" "world"
;            "carry" "world"
;            "execute" "world"})
;
;   (every 24 hours
;       (unless (empty? (get-data "souls"))
;         (does "exhales souls into the air around it")
;         (set-data "souls" [])))
;
;   (every 12 hours
;       (unless (empty? (get-data "log"))
;         (room-says "you hear a ghostly echo from the dead past..." (pick-random (get-data "log")))
;         (set-data "log" [])))
;
;   (idling
;     (if (< 5 (random-number 10))
;         (does "glows odiously")))
;
;   (hears "*" (append-data "log" heard))
;
;   (hears "fire" (does "seems to clench its pages more tightly"))
;
;   (provides "fear" (room-says "the aura about the necronomicon seems more vibrant"))
;
;   (provides "read $this"
;             (room-says (sender-data "name") "opens the" (get-data "name") "and begins to read!")
;             (says "i now have" (+ (sender-data "name") "'s") "soul.")
;             (does "laughs wickedly")
;             (append-data "souls" sender-name)
;             (says "i shall now predict the present~")
;             (says (calls "/home/vilmibm/bin/get_random_headline")))
;
;   (provides "touch $this"
;             (tell-sender "you stroke the" (+ (get-data "name") "'s") "covers.")
;             (tell-sender "the souls of" (join-and (get-data "souls")) "all call out to you from the void."))
;
;   (provides "lick $this"
;             (tell-sender "you lick the cover of the necronomicon. it is bittersweet.")
;             (teleport-sender "vilmibm/void"))
;
;   (provides "punch $this"
;             (room-says (sender-data "name") "punches" (get-data "name"))
;             (room-says "the necronomicon punches back, sending" (sender-data "name") "flying!")
;             (move-sender (random-direction)))
;
;   (provides "kiss $this"
;             (room-says (sender-data "name") "kisses" (get-data "name"))
;             (does "blushes violently")
;             (if (carried?)
;                 (tell-sender "the book squirms and tries to throw itself at the floor")))
;
;   (provides "throw $this at $object"
;             (room-says "the necronomicon flaps like a bird, dives at"
;                         (get-data object "name")
;                         "and flaps noisily around"
;                         (get (get-data object "pronouns") 2)
;                         "head"))
;
;   (provides "rip page from $this"
;             (creates {"name" "yellowed page"
;                       "description" "a page, seemingly quite ancient, ripped from" (get-data "name")})))
