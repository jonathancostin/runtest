#include <errno.h>
#include <fcntl.h>
#include <pwd.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

typedef enum {
  MODE_LOCAL,
  MODE_AUTO,
} Mode;

typedef struct {
  Mode mode;
  bool saved;
} ModeState;

static const char *mode_name(Mode mode) {
  return mode == MODE_AUTO ? "auto" : "local";
}

static const char *display_mode_name(Mode mode) {
  return mode == MODE_AUTO ? "Auto" : "Local";
}

static const char *account_home_directory(void) {
#ifdef RUNTEST_TESTING
  const char *account_home = getenv("RUNTEST_TEST_ACCOUNT_HOME");
  if (account_home == NULL || account_home[0] == '\0') {
    errno = ENOENT;
    return NULL;
  }
  return account_home;
#else
  errno = 0;
  struct passwd *account = getpwuid(getuid());
  if (account == NULL || account->pw_dir == NULL || account->pw_dir[0] == '\0') {
    if (errno == 0) {
      errno = ENOENT;
    }
    return NULL;
  }
  return account->pw_dir;
#endif
}

static char *path_below_account_home(const char *suffix) {
  const char *account_home = account_home_directory();
  if (account_home == NULL) {
    return NULL;
  }

  size_t path_length = strlen(account_home) + strlen(suffix) + 1;
  char *path = malloc(path_length);
  if (path == NULL) {
    return NULL;
  }

  snprintf(path, path_length, "%s%s", account_home, suffix);
  return path;
}

static char *mode_state_path(void) {
  return path_below_account_home("/Library/Application Support/RunTest/mode");
}

static int read_mode_state(ModeState *state) {
  state->mode = MODE_LOCAL;
  state->saved = false;

  char *path = mode_state_path();
  if (path == NULL) {
    if (errno == ENOENT) {
      return 0;
    }
    fputs("runtest: cannot allocate mode state path\n", stderr);
    return -1;
  }

  FILE *file = fopen(path, "r");
  int open_error = errno;
  free(path);
  if (file == NULL) {
    if (open_error == ENOENT) {
      return 0;
    }
    fprintf(stderr, "runtest: cannot read mode state: %s\n",
            strerror(open_error));
    return -1;
  }

  char saved_mode[16];
  if (fgets(saved_mode, sizeof(saved_mode), file) == NULL) {
    int read_error = ferror(file) ? errno : EINVAL;
    fclose(file);
    fprintf(stderr, "runtest: cannot read mode state: %s\n",
            strerror(read_error));
    return -1;
  }

  if (fclose(file) != 0) {
    fprintf(stderr, "runtest: cannot read mode state: %s\n", strerror(errno));
    return -1;
  }

  saved_mode[strcspn(saved_mode, "\r\n")] = '\0';
  if (strcmp(saved_mode, "local") == 0) {
    state->mode = MODE_LOCAL;
  } else if (strcmp(saved_mode, "auto") == 0) {
    state->mode = MODE_AUTO;
  } else {
    fprintf(stderr, "runtest: mode state contains an unknown value: %s\n",
            saved_mode);
    return -1;
  }

  state->saved = true;
  return 0;
}

static int make_directory(const char *path) {
  if (mkdir(path, 0700) == 0 || errno == EEXIST) {
    return 0;
  }

  fprintf(stderr, "runtest: cannot create state directory %s: %s\n", path,
          strerror(errno));
  return -1;
}

static int ensure_state_directory(void) {
  const char *suffixes[] = {
      "/Library",
      "/Library/Application Support",
      "/Library/Application Support/RunTest",
  };

  for (size_t index = 0; index < sizeof(suffixes) / sizeof(suffixes[0]);
       index++) {
    char *path = path_below_account_home(suffixes[index]);
    if (path == NULL) {
      fputs("runtest: account home is unavailable; cannot save mode state\n",
            stderr);
      return -1;
    }

    int result = make_directory(path);
    free(path);
    if (result != 0) {
      return -1;
    }
  }

  return 0;
}

static int write_mode_state(Mode mode) {
  if (ensure_state_directory() != 0) {
    return -1;
  }

  char *state_path = mode_state_path();
  char *temporary_path =
      path_below_account_home(
          "/Library/Application Support/RunTest/mode.XXXXXX");
  if (state_path == NULL || temporary_path == NULL) {
    free(state_path);
    free(temporary_path);
    fputs("runtest: cannot allocate mode state path\n", stderr);
    return -1;
  }

  int file_descriptor = mkstemp(temporary_path);
  if (file_descriptor == -1) {
    fprintf(stderr, "runtest: cannot create temporary mode state: %s\n",
            strerror(errno));
    free(state_path);
    free(temporary_path);
    return -1;
  }

  const char *value = mode_name(mode);
  size_t value_length = strlen(value);
  bool write_failed =
      write(file_descriptor, value, value_length) != (ssize_t)value_length ||
      write(file_descriptor, "\n", 1) != 1 || fsync(file_descriptor) != 0;
  int write_error = errno;

  if (close(file_descriptor) != 0 && !write_failed) {
    write_failed = true;
    write_error = errno;
  }

  if (!write_failed && rename(temporary_path, state_path) != 0) {
    write_failed = true;
    write_error = errno;
  }

  if (write_failed) {
    fprintf(stderr, "runtest: cannot save mode state: %s\n",
            strerror(write_error));
    unlink(temporary_path);
  }

  free(state_path);
  free(temporary_path);
  return write_failed ? -1 : 0;
}

static bool executable_is_on_path(const char *name) {
  const char *path = getenv("PATH");
  if (path == NULL) {
    return false;
  }

  size_t name_length = strlen(name);
  const char *directory = path;

  while (true) {
    const char *separator = strchr(directory, ':');
    size_t directory_length =
        separator == NULL ? strlen(directory) : (size_t)(separator - directory);
    size_t candidate_length = directory_length + 1 + name_length + 1;
    char *candidate = malloc(candidate_length);
    if (candidate == NULL) {
      return false;
    }

    if (directory_length == 0) {
      snprintf(candidate, candidate_length, "./%s", name);
    } else {
      snprintf(candidate, candidate_length, "%.*s/%s", (int)directory_length,
               directory, name);
    }

    bool is_executable = access(candidate, X_OK) == 0;
    free(candidate);
    if (is_executable) {
      return true;
    }

    if (separator == NULL) {
      return false;
    }
    directory = separator + 1;
  }
}

int main(int argument_count, char *arguments[]) {
  if (argument_count < 2) {
    fputs("Usage: runtest <command> [arguments ...]\n", stderr);
    return 64;
  }

  if (strcmp(arguments[1], "status") == 0) {
    ModeState state;
    if (read_mode_state(&state) != 0) {
      return 1;
    }

    if (argument_count == 3 && strcmp(arguments[2], "--json") == 0) {
      printf("{\"auto\":{\"available\":%s,\"fallback\":\"direct local "
             "execution\",\"policy\":\"taskpolicy -b\"},\"mode\":\"%s\","
             "\"source\":\"%s\"}\n",
             executable_is_on_path("taskpolicy") ? "true" : "false",
             mode_name(state.mode), state.saved ? "saved" : "default");
      return 0;
    }

    if (argument_count != 2) {
      fputs("Usage: runtest status [--json]\n", stderr);
      return 64;
    }

    printf("Mode: %s%s\n", display_mode_name(state.mode),
           state.saved ? "" : " (default; no saved mode)");
    printf("Auto policy: taskpolicy -b (%s)\n",
           executable_is_on_path("taskpolicy") ? "available" : "unavailable");
    printf("Auto fallback: direct local execution\n");
    return 0;
  }

  if (strcmp(arguments[1], "mode") == 0) {
    if (argument_count != 3 ||
        (strcmp(arguments[2], "local") != 0 &&
         strcmp(arguments[2], "auto") != 0)) {
      fputs("Usage: runtest mode <local|auto>\n", stderr);
      return 64;
    }

    Mode mode = strcmp(arguments[2], "auto") == 0 ? MODE_AUTO : MODE_LOCAL;
    if (write_mode_state(mode) != 0) {
      return 1;
    }

    printf("Mode set to %s.\n", display_mode_name(mode));
    return 0;
  }

  ModeState state;
  if (read_mode_state(&state) != 0) {
    return 1;
  }

  if (state.mode == MODE_AUTO && executable_is_on_path("taskpolicy")) {
    char **taskpolicy_arguments =
        calloc((size_t)argument_count + 2, sizeof(*taskpolicy_arguments));
    if (taskpolicy_arguments == NULL) {
      fputs("runtest: cannot allocate Auto command arguments\n", stderr);
      return 1;
    }

    taskpolicy_arguments[0] = "taskpolicy";
    taskpolicy_arguments[1] = "-b";
    for (int index = 1; index < argument_count; index++) {
      taskpolicy_arguments[index + 1] = arguments[index];
    }

    execvp(taskpolicy_arguments[0], taskpolicy_arguments);
    int taskpolicy_error = errno;
    free(taskpolicy_arguments);
    fprintf(stderr,
            "runtest: Auto policy is unavailable (%s); falling back to "
            "direct local execution\n",
            strerror(taskpolicy_error));
  } else if (state.mode == MODE_AUTO) {
    fputs("runtest: Auto policy is unavailable; falling back to direct local "
          "execution\n",
          stderr);
  }

  execvp(arguments[1], &arguments[1]);

  int execution_error = errno;
  fprintf(stderr, "runtest: %s: %s\n", arguments[1],
          strerror(execution_error));
  return execution_error == ENOENT ? 127 : 126;
}
