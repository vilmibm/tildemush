package main

import (
	"fmt"
	"github.com/vilmibm/tildemush/witch"
)

func main() {
	l, items := witch.Lex("test", `# test program
sun sun sun moon moon moon`)

	fmt.Printf("DBG %#v\n", l)

	for {
		i, more := <-items
		if more {
			fmt.Printf("DBG %#v\n", i)
		} else {
			break
		}
	}
}
