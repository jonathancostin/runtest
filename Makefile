CC ?= cc
CFLAGS ?= -O2
RUNTEST_CFLAGS = -std=c17 -Wall -Wextra -Wpedantic -Werror
RUNTEST = bin/runtest
TEST_RUNTEST = bin/runtest-test
SOURCE = src/runtest.c

.PHONY: build check test

build: $(RUNTEST)

$(RUNTEST): $(SOURCE)
	mkdir -p bin
	$(CC) $(CPPFLAGS) $(CFLAGS) $(RUNTEST_CFLAGS) -o $@ $<

$(TEST_RUNTEST): $(SOURCE)
	mkdir -p bin
	$(CC) $(CPPFLAGS) $(CFLAGS) $(RUNTEST_CFLAGS) -DRUNTEST_TESTING -o $@ $<

check:
	$(CC) $(CPPFLAGS) $(CFLAGS) $(RUNTEST_CFLAGS) -fsyntax-only $(SOURCE)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(RUNTEST_CFLAGS) -DRUNTEST_TESTING -fsyntax-only $(SOURCE)
	python3 -m compileall -q tests

test: $(TEST_RUNTEST)
	RUNTEST_UNDER_TEST="$(CURDIR)/$(TEST_RUNTEST)" python3 -m unittest discover -s tests -v
