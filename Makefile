CC ?= cc
CFLAGS ?= -O2
RUNTEST_CFLAGS = -std=c17 -Wall -Wextra -Wpedantic -Werror
RUNTEST = bin/runtest
SOURCE = src/runtest.c

.PHONY: build check test

build: $(RUNTEST)

$(RUNTEST): $(SOURCE)
	mkdir -p bin
	$(CC) $(CPPFLAGS) $(CFLAGS) $(RUNTEST_CFLAGS) -o $@ $<

check:
	$(CC) $(CPPFLAGS) $(CFLAGS) $(RUNTEST_CFLAGS) -fsyntax-only $(SOURCE)
	python3 -m compileall -q tests

test: build
	RUNTEST_UNDER_TEST="$(CURDIR)/$(RUNTEST)" python3 -m unittest discover -s tests -v
