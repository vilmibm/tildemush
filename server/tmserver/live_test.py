"""This script is used to create a test world. Once run, log in as
vilmibm:foobarbazquux, then you should be in a room with a horse."""

from .migrations import reset_db
from .models import UserAccount, GameObject, Script, ScriptRevision
from .world import GameWorld

def setup_vil():
    return UserAccount.create(
        username='vilmibm',
        password='foobarbazquux')


def setup_horse():
    reset_db()
    vil = setup_vil()
    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    horse_script = Script.create(
        name='horse',
        author=vil
    )
    script_rev = ScriptRevision.create(
        script=horse_script,
        code='''
            (witch "horse"
              (has {"num-pets" 0
                    "name" "snoozy"
                    "description" "a horse"})
              (hears "pet"
                (set-data "num-pets" (+ 1 (get-data "num-pets")))
                  (if (= 0 (% (get-data "num-pets") 5))
                    (says "neigh neigh neigh i am horse"))))''')
    snoozy = GameObject.create(
        author=vil,
        shortname='snoozy',
        script_revision=script_rev)

    GameWorld.put_into(foyer, snoozy)

