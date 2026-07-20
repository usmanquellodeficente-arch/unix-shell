# Python Shell Implementation

A POSIX-like shell built from scratch in Python, developed as part of the CodeCrafters "Build Your Own Shell" challenge. It implements command parsing, execution, pipelines, redirection, variable expansion, job control, and programmable tab completion, closely mirroring core Bash behavior.

## Features

- **Command Parsing**: Custom lexer supporting single and double quotes, escape sequences, and quote overlap handling.
- **I/O Redirection**: Support for `>`, `>>`, `1>`, `1>>`, `2>`, `2>>` with correct stream targeting.
- **Pipelines**: Multi-stage pipelines (`cmd1 | cmd2 | cmd3`) mixing builtins and external executables using `os.pipe()` and `subprocess.Popen`.
- **Variable Expansion**: Supports both `$VAR` and `${VAR}` syntax with declared shell variables.
- **Background Jobs**: Run commands with `&`, track job numbers, and report status via `jobs`.
- **Command History**: Persistent history via `readline`, with `history -r/-w/-a` for reading, writing, and appending history files, plus `HISTFILE` environment variable support on startup and exit.
- **Tab Completion**:
  - Builtin command completion
  - Executable completion (scanned from `PATH`)
  - File and directory completion, including multi-argument paths
  - Programmable completion via `complete -C` / `complete -F`, following the `COMP_LINE` / `COMP_POINT` convention
- **Builtin Commands**: `echo`, `exit`, `type`, `pwd`, `cd`, `complete`, `jobs`, `history`, `declare`.

## Architecture

The project follows a modular, single-responsibility design:

| Component      | Responsibility                                                                 |
|-----------------|---------------------------------------------------------------------------------|
| `Parser`        | Tokenizes raw input, handles quoting, escaping, and redirect token detection.   |
| `Redirect`      | Resolves redirect tokens into concrete `(target, mode)` tuples for stdout/stderr. |
| `Resolver`      | Orchestrates parsing, variable expansion, and redirect resolution per command.  |
| `Executor`      | Executes parsed commands, manages builtins, pipelines, and background jobs.    |
| `Completions`   | Implements all tab completion logic (files, builtins, executables, programmable). |
| `History`       | Wraps `readline` history operations and persistence to disk.                   |

Data flows as follows:
## Builtin Commands Reference

| Command     | Description                                                                 |
|-------------|-------------------------------------------------------------------------------|
| `echo`      | Prints arguments to stdout.                                                  |
| `exit`      | Terminates the shell.                                                        |
| `type`      | Reports whether a command is a builtin, an executable (with path), or unknown. |
| `pwd`       | Prints the current working directory.                                        |
| `cd`        | Changes directory, supports `~` for home expansion.                          |
| `complete`  | Registers or inspects programmable completion specs (`-C`, `-F`, `-p`, `-r`). |
| `jobs`      | Lists background jobs with running/done status.                              |
| `history`   | Displays, reads, writes, or appends command history.                         |
| `declare`   | Declares shell variables (`name=value`) or inspects them with `-p`.          |

## Installation

Requires Python 3.10+ (uses `str | None` union syntax).

```bash
git clone <repository-url>
cd <repository-folder>
python3 shell.py
```

No external dependencies beyond the Python standard library (`readline`, `subprocess`, `os`, `atexit`, `contextlib`).

## Usage Examples

```bash
$ echo "Hello, World!"
Hello, World!

$ ls | grep .py | wc -l
3

$ echo "output" > out.txt
$ cat out.txt 1>> out.txt

$ declare NAME=John
$ echo "Hi $NAME"
Hi John

$ sleep 100 &
[1] 12345
$ jobs
[1]+  Running                 sleep 100 &

$ history -w /tmp/my_history
$ history -r /tmp/my_history
```

## Environment Variables

- `HISTFILE`: path to a file used to persist command history across sessions. Loaded on startup and updated on exit or via `history -a`.

## Known Limitations

- No support for subshells `()` or command substitution `$(...)`.
- No support for logical operators (`&&`, `||`).
- Signal handling (e.g. `SIGINT`, `SIGTSTP`) for job control is not implemented.

## Project Structure
## Contributing

This project is primarily a learning exercise. Issues and pull requests focused on bug fixes or architectural improvements are welcome.

## License

MIT

