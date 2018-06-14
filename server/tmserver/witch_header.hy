(defmacro set-data [key value] `(.set-data receiver ~key ~value))
(defmacro get-data [key] `(.get-data receiver ~key))
(defmacro says [message] `(.say receiver ~message))
#_("TODO support additional args, here. right now, they have to be one big string.")
(defmacro tell-sender [action args] `(.tell-sender receiver sender ~action ~args))

#_("TODO what to do with script_name and author_name?")
#_("TODO eventually decide on cmd-args handling")

(defmacro witch
  [script_name _ author_name data &rest actions]
  (setv se (gensym))
  (setv hp (gensym))
  `(do
     (setv ~se (ScriptEngine))
     ~@(map
         (fn [hp] `(.add-handler
                     ~se
                     ~(get hp 1)
                     (fn [receiver sender action-args]
                       ~@(cut hp 2))) )
         actions)
     (ensure-obj-data ~(get data 1))
     ~se))



#_(setv hmm (witch "horse" by "vilmibm"
                (has {"num-pets" 0})
                (hears "pet"
                       (set-data "num-pets"
                                 (+ 1 (get-data "num-pets")))
                       (if (= 0 (% (get-data "num-pets") 5))
                           (says "neigh neigh neigh :)")))))
