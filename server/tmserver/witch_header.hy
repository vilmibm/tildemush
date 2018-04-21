(defclass ScriptEngine []
  (defn set-data [self &rest args] (print "set-data" args))
  (defn get-data [self &rest args] (print "get-data" args))
  (defn say [self &rest args] (print "say" args))
  (defn add-handler [self &rest args] (print "add-hander" args)))
#_("TODO arguably i shold be deffing hears and data macros as well.")

(defmacro set-data [key value] `(.set-data gobj key value))
(defmacro get-data [key] `(.get-data gobj key))
(defmacro says [message] `(.say gobj message))

(defmacro witch
  [script_name _ author_name data actions]
  #_("TODO what to do with script_name and author_name?")
  (setv se (gensym))
  (setv hp (gensym))
  (quasiquote
    (do
      (setv ~se (ScriptEngine))
      #_("TODO something wrong with ~actions expansion...")
      (for [~hp ~actions]
        (.add-handler
          ~se
          ~(get hp 1)
          (fn [gobj pobj the-rest]
            #_("TODO eventually decide on the-rest handling")
            (._ensure-data gobj ~(get data 1))
            ~@(cut hp 2))))
      ~se)))

(setv se (witch "horse" by "vilmibm"
                (has {"num-pets" 0})
                (hears "pet"
                       (set-data "num-pets"
                                 (+ 1 (get-data "num-pets")))
                       (if (= 0 (% (get-data "num-pets") 5))
                           (says "neigh neigh neigh :)")))))
