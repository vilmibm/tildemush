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
