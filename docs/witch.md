# WITCH

Weaving Incatations To Create Homonculi

## Gen 4 sketch

```
object "horse" by "vilmibm" {
    is {
        A horse. It is friendly enough and will let you ride it if it likes you. It does have a
        temper but loves oats.
    }

    has {
        rider Player: none
        pesterCount Number: 0
    }

    provides pester :me {
       if pesterCount > 5 {
           do("attack {subject.name}")
           room.say("The horse angrily rears up at {subject.name}. After a moment of huffing, it calms down.")
           pesterCount <- 0
       }
    }

    provides examine :me {
        if rider {
            room.whisper(subject, "You see a friendly horse ridden by {rider.name}") 
            stop
        }
        room.whisper(subject, "You see a friendly horse")
    }

    // TODO fill in ride stuff
}
``
