#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argument_count, char *arguments[]) {
  if (argument_count < 2) {
    fputs("Usage: runtest <command> [arguments ...]\n", stderr);
    return 64;
  }

  execvp(arguments[1], &arguments[1]);

  int execution_error = errno;
  fprintf(stderr, "runtest: %s: %s\n", arguments[1],
          strerror(execution_error));
  return execution_error == ENOENT ? 127 : 126;
}
