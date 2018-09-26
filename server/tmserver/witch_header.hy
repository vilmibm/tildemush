#_("TODO support additional args, here. right now, they have to be one big string.")
(defmacro tell-sender [action args] `(witch-tell-sender sender ~action ~args))
(defmacro move-sender [direction] `(witch-move-sender sender ~direction))
(defmacro teleport-sender [target-room-name] `(witch-teleport-sender sender ~target-room-name))

#_("TODO eventually decide on cmd-args handling")

(defmacro witch
  [script_name data &rest actions]
  (setv hp (gensym))
  `(do
     ~@(map
         (fn [hp] `(add-handler
                     ~(get hp 1)
                     (fn [receiver sender arg]
                       (setv args (split-args arg))
                       (setv from-me? (= receiver sender))
                       ~@(cut hp 2))) )
         actions)
     (ensure-obj-data ~(get data 1))))


#_(setv hmm (witch "horse"
                (has {"num-pets" 0})
                (hears "pet"
                       (set-data "num-pets"
                                 (+ 1 (get-data "num-pets")))
                       (if (= 0 (% (get-data "num-pets") 5))
                           (says "neigh neigh neigh :)")))))

#_(what follows is a maximalist example of all the features i'd like witch to have)
#_(witch by vilmibm
       "This script defines a silly, kind of evil book. It is intended to
       illustrate every feature that WITCH offers."
       (has {"name" "necronomicon"
             "description" "a book bound in flesh seething with undead energy."
             "pronouns" ["it" "it" "its"]
             "souls" []
             "log" []})
       (allows
         {"read" "world"
          "write" "world"
          "carry" "world"
          "execute" "world"})
       (every 24 hours
              (unless (empty? (get-data "souls"))
                (does "exhales souls into the air around it")
                (set-data "souls" [])))
       (every 12 hours
              (unless (empty? (get-data "log"))
                (world-says "you hear a ghostly echo from the dead past..." (pick-random (get-data "log")))
                (set-data "log" [])))
       (idling
         (if (< 5 (random-number 10))
             (does "glows ominously")))
       (hears "*"
              (append-data "log" heard))
       (hears "fire"
              (does "grumbles quietly"))
       (provides "fear"
                 (world-says "the aura about the necronomicon seems more vibrant"))
       (provides transitive "read"
                 (says "welcome to undeath. i now have your soul.")
                 (does "laughs wickedly")
                 (append-data "souls" sender-name)
                 (says "i shall now predict the present~")
                 (says (calls "/home/vilmibm/bin/get_random_headline")))
       (provides transitive "touch"
                 (world-says "you stroke the fleshy book's covers and can feel the souls trapped within the book.")
                 (world-says "the souls of" (join-and (get-data "souls")) "all call out to you from the void."))
       (provides transitive "lick"
                 (world-says "you lick the cover of the necronomicon. it is bittersweet.")
                 (teleport-sender "vilmibm/void"))
       (provides transitive "punch"
                 (world-says "the necronomicon punches you back, sending you flying!")
                 (move-sender (random-direction)))
       (provides transitive "throw" (target (args 1))
                 (world-says "the necronomicon flaps like a bird, dives at"
                             (target-data "name")
                             "and flaps noisily around"
                             (get (target-data "pronouns") 2)
                             "head")))
