(defmacro set-data [key value] `(.set-data receiver ~key ~value))
(defmacro get-data [key] `(.get-data receiver ~key))
(defmacro says [message] `(.say receiver ~message))

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
                       (._ensure-data receiver ~(get data 1))
                       ~@(cut hp 2))) )
         actions)
     ~se))



#_(setv hmm (witch "horse" by "vilmibm"
                (has {"num-pets" 0})
                (hears "pet"
                       (set-data "num-pets"
                                 (+ 1 (get-data "num-pets")))
                       (if (= 0 (% (get-data "num-pets") 5))
                           (says "neigh neigh neigh :)")))))
