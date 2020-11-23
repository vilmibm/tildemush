package witch

import (
	"fmt"
	"strings"
	"unicode/utf8"
)

/*
	To start, a proof of concept lexer + parser for a simple stack based language called sunmoon.
	"sun" pushes onto a stack; "moon" pops. it's an error to pop too many times. comments are
	written with a leading #.
*/

const comment = "#"
const push = "sun"
const pop = "moon"
const newline = "\n" // TODO unsure about this
const space = " "
const tab = "	"
const eof = -1

type itemType int

const (
	itemError = iota
	itemComment
	itemPush
	itemPop
	itemEOF
)

type item struct {
	typ itemType // something like itemNumber
	val string   // content of the item, like "23"
}

func (i item) String() string {
	switch i.typ {
	case itemEOF:
		return "EOF"
	case itemError:
		return i.val
	}

	return fmt.Sprintf("%q", i.val)
}

type stateFn func(*Lexer) stateFn

type Lexer struct {
	name  string    // for error reporting
	input string    // string being scanned
	start int       // start of current item
	pos   int       // current position in input
	width int       // width of last thing read
	items chan item // channel of scanned items
}

func Lex(name, input string) (*Lexer, chan item) {
	l := &Lexer{
		name:  name,
		input: input,
		items: make(chan item),
	}
	go l.run()
	return l, l.items
}

func (l *Lexer) run() {
	for state := lexText; state != nil; {
		state = state(l)
	}
	close(l.items)
}

func (l *Lexer) emit(t itemType) {
	l.items <- item{t, l.input[l.start:l.pos]}
	l.start = l.pos
}

func (l *Lexer) next() rune {
	if l.pos >= len(l.input) {
		l.width = 0
		return eof
	}
	r, w := utf8.DecodeRuneInString(l.input[l.pos:])
	l.width = w
	l.pos += l.width
	return r
}

func (l *Lexer) peek() rune {
	r := l.next()
	l.backup()
	return r
}

func (l *Lexer) ignore() {
	l.start = l.pos
}

func (l *Lexer) backup() {
	l.pos -= l.width
}

func (l *Lexer) errorf(format string, args ...interface{}) stateFn {
	l.items <- item{
		itemError,
		fmt.Sprintf(format, args...),
	}
	return nil
}

func (l *Lexer) accept(valid string) bool {
	if strings.ContainsRune(valid, l.next()) {
		return true
	}
	l.backup()
	return false
}

func (l *Lexer) acceptUntil(s string) {
	for {
		if l.pos == len(l.input)-1 {
			return
		}
		if strings.HasPrefix(l.input[l.pos:], s) {
			return
		}
		_ = l.next()
	}
}

// lexText is a "start state" that never emits anything
func lexText(l *Lexer) stateFn {
	fmt.Printf("DBG %#v\n", string(l.input[l.pos:]))
	if strings.HasPrefix(l.input[l.pos:], comment) {
		return lexComment(l)
	}

	if strings.HasPrefix(l.input[l.pos:], push) {
		return lexPush(l)
	}

	if strings.HasPrefix(l.input[l.pos:], pop) {
		return lexPop(l)
	}

	if strings.HasPrefix(l.input[l.pos:], newline) {
		return lexWhitespace(l)
	}

	if strings.HasPrefix(l.input[l.pos:], space) {
		return lexWhitespace(l)
	}

	if strings.HasPrefix(l.input[l.pos:], tab) {
		return lexWhitespace(l)
	}

	if l.pos == len(l.input)-1 {
		l.emit(itemEOF)
	} else {
		// TODO emit error
	}

	return nil
}

func lexWhitespace(l *Lexer) stateFn {
	for {
		if !l.accept(tab + newline + space) {
			break
		}
	}

	fmt.Printf("DBG %#v\n", "ignoring whitespace")
	l.ignore()

	return lexText
}

func lexComment(l *Lexer) stateFn {
	l.pos += len(comment)
	l.acceptUntil(newline)
	l.emit(itemComment)
	return lexText
}

func lexPush(l *Lexer) stateFn {
	l.pos += len(push)
	l.emit(itemPush)
	return lexText
}

func lexPop(l *Lexer) stateFn {
	l.pos += len(pop)
	l.emit(itemPop)
	return lexText
}
