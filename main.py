from contextlib import ExitStack
import sys
import os
import subprocess
import readline
import atexit
class Parser:
    def __init__(self):
        pass
    def quotes_handler(self,quote : str,quote_state : str | None): # Handles quotes returning correct state and supporting overlap of quotes
        if not quote_state:
            return quote
        if quote_state == quote:
            return
        return quote_state
    def redirect_builder(self,raw_input: list[str],parsed_command,i): # Returns a well formed redirect
            stream = ""
            redirect = ""
            while i <  len(raw_input):
                char = raw_input[i]
                stream = char
                if  not char.isdigit():
                    if char and char != " ":
                        parsed_command[-1] += char
                    stream = "1"
                if len(raw_input) > i+2 and raw_input[i+2] == ">":
                    redirect = raw_input[i+1] + raw_input[i+2]
                    i += 3
                    return i,raw_input,stream + redirect
                else:
                    if i+1 < len(raw_input):
                        redirect = raw_input[i+1]
                        i += 2
                    return i,raw_input,stream + redirect
            return i,raw_input,stream + redirect
    def appender(self,command_list: list[str], redirects_list: list[str], current: str,redirect_state: bool): # Appends args to the correct list if contains something
        if current:
            if redirect_state:
                redirects_list.append(current)
                redirect_state = False
            else:
                command_list.append(current)
            current = ""
        return command_list,redirects_list,current,redirect_state
class Redirect:
    def __init__(self):
        pass     
    def std_handler(self,redirects,redirect_targets):
        stdout,stderr = ["stdout"],["stderr"]
        if not redirects:
            return stdout,stderr
        for i in range(len(redirects)):
            if redirects[i] in ("1>","1>>"):
                stdout = [redirects[i],redirect_targets[i]]
            if redirects[i] in ("2>","2>>"):
                stderr = [redirects[i],redirect_targets[i]]
        return stdout,stderr

class Completions: # Contains all method to handle completitions
    def __init__(self,executor: Executor):
        self.executor = executor
        self.executables = {}
        paths = os.environ.get("PATH", "").split(os.pathsep)
        for i in range(len(paths)):
            if os.path.exists(paths[i]):
                for element in os.listdir(paths[i]):
                    full_path = os.path.join(paths[i], element)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        self.executables[element] = full_path
    def my_display_hook(sef, substitution, matches, longest_match_length):
        sys.stdout.write("\n")
        sys.stdout.write("  ".join(matches))
        sys.stdout.write("\n$ " + readline.get_line_buffer())
        sys.stdout.flush() 
    def file_completion_handler(self, full_command, state):
        matches = []
        divider = full_command.rfind(" ")

        if os.sep in full_command[divider + 1:]:
            last_slash = full_command.rfind(os.sep)
            path = os.path.abspath(full_command[divider + 1: last_slash + 1])
            prefix = full_command[last_slash + 1:]
            matches = [f for f in os.listdir(path) if f.startswith(prefix) or not prefix]
            matches = sorted(matches)
            if state < len(matches):
                result = matches[state]
                completed_line = path + os.sep + result
                if len(matches) == 1:
                    if os.path.isdir(completed_line):
                        return full_command[divider + 1: last_slash + 1] + result  + os.sep
                    return full_command[divider + 1: last_slash + 1] + result + " "
                else:
                    return full_command[divider + 1: last_slash + 1] + result
        else:
            path = os.getcwd()
            prefix = full_command[divider + 1:]
            matches = [f for f in os.listdir(path) if f.startswith(prefix) or not prefix]
            matches = sorted(matches)
            if state < len(matches):
                is_dir = os.path.isdir(path + os.sep + matches[state])
                if is_dir:
                    return matches[state] + os.sep
                if len(matches) == 1:
                    return matches[state] + " "
                return matches[state]
    def handle_completion(self, raw_command, state):
        full_command = readline.get_line_buffer()
        input_list = full_command.split(" ")
        if input_list[0] in self.executor.registered_completions:
            if state == 0:
                env = os.environ.copy()
                env["COMP_LINE"] = full_command
                env["COMP_POINT"] = str(len(full_command))
                args = input_list
                length = len(args)
                command = args[0]
                current = command if length < 2 else args[-1]
                previus = "" if length < 2 else args[-2]
                result = subprocess.run(
                    [
                        self.executor.registered_completions[input_list[0]][1],
                        command,
                        current,
                        previus,
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                stripped = result.stdout.strip()
                if stripped:
                    self.last_candidates = sorted(stripped.split("\n"))
                else:
                    self.last_candidates = []
            candidates = self.last_candidates
            if state >= len(candidates):
                return None
            if len(candidates) == 1:
                return candidates[state] + " "
            return candidates[state]
        if " " in full_command:
            return self.file_completion_handler(full_command,state)
        else:
            result = self.builtin_completion(raw_command,state)
        if result:
            return result
        return self.executables_completion(raw_command,state)
    def executables_completion(self,raw_command,state): # Executable commands completition 
        matches = [executable for executable in self.executables if executable.startswith(raw_command)]
        if not matches:
            print("\x07", end="", flush = True)
            return None
        if state < len(matches):
            return matches[state] + " "
        else:
            return None
    
    def builtin_completion(self,raw_command,state) -> None | str :# Builtin commands completition 
        matches = [cmd for cmd in self.executor.builtin_commands if cmd.startswith(raw_command)]
        if not matches and state == 0:
            print("\x07", end="", flush = True)
            return None
        if state < len(matches):
            return matches[state] + " "
        return None

class Resolver(): # Organizes the raw input trough parsers, handles redirect and passes complete command to execute 
    def __init__(self,parser_obj: Parser,redirect_obj: Redirect):
        self.parser_obj = parser_obj
        self.redirect_obj = redirect_obj
    def parse(self,raw_input,declared_variables: dict): # Uses Parser class method to parse user input
        quote_type = None
        escaped = False
        current_parsed_command = []
        command_list = []
        current_command_redirect = []
        redirected = False
        variable = False
        current_command_redirect_target = []
        current = ""
        redirect_list = []
        redirect_target_list = []
        i = 0
        while i < len((raw_input)):
            char = raw_input[i]
            if char == "\\" and not escaped:
                if  not quote_type:
                    escaped = True
                    i += 1
                    continue
                if quote_type == '"' and (raw_input[i+1] in ('"',"\\") and len(raw_input) > i+1):
                    escaped = True
                    i += 1
                    continue
            if len(raw_input) > i+1 and raw_input[i+1] == ">":
                current_parsed_command,current_command_redirect_target,current,redirected= self.parser_obj.appender(current_parsed_command,current_command_redirect_target,current,redirected)
                i,raw_input,complete_redirect = self.parser_obj.redirect_builder(raw_input,current_parsed_command,i)
                if not redirected:
                    current_command_redirect.append(complete_redirect)
                    redirected = True
                continue

            if char in ("'",'"') and not escaped:
                current_quote = self.parser_obj.quotes_handler(char,quote_type)
                if char != current_quote and current_quote:
                    current += char
                else:
                    quote_type  = current_quote
                i += 1
                continue
            if char == " " and not quote_type and not escaped:
                if variable:
                    current = self.check_variable(current, declared_variables)
                    variable = False
                current_parsed_command,current_command_redirect_target,current,redirected= self.parser_obj.appender(current_parsed_command,current_command_redirect_target,current,redirected)
                i += 1
                continue
            if char == "|" and not quote_type and not escaped:
                command_list.append(current_parsed_command)
                redirect_list.append(current_command_redirect)
                redirect_target_list.append(current_command_redirect_target)
                current_parsed_command,current_command_redirect,current_command_redirect_target = [],[],[]
                current = ""
                redirected = False
                i += 1
                continue
            if char == "$" and not quote_type and not escaped:
                variable = True
                current += char
                i += 1
                continue
            else:
                if char == "&" and i == len(raw_input) - 1:
                    current_parsed_command,current_command_redirect_target,current,redirected= self.parser_obj.appender(current_parsed_command,current_command_redirect_target,current,redirected)
                current += char
                if escaped:
                    escaped = False
            i += 1
        if variable:
            current = self.check_variable(current, declared_variables)
            variable = False
        current_parsed_command,current_command_redirect_target,current,redirected= self.parser_obj.appender(current_parsed_command,current_command_redirect_target,current,redirected)
        if not current_command_redirect_target:
            current_command_redirect_target = ["stdout","stderr"]
        command_list.append(current_parsed_command)
        redirect_list.append(current_command_redirect)
        redirect_target_list.append(current_command_redirect_target)
        return command_list,redirect_list,redirect_target_list
    # ${FOO}bar
    def check_variable(self, string, variables):
        current, rest = string.split("$", 1)
        if rest.startswith("{") and "}" in rest:
            variable = rest[1:rest.index("}")]
            suffix = rest[rest.index("}") + 1:]
        else:
            index = 0
            while index < len(rest) and (rest[index].isalnum() or rest[index] == "_"):
                index += 1
                variable = rest[:index]
                suffix = rest[index:]
        if variable in variables:
            return current + variables[variable] + suffix
        else:
            return current + "" + suffix

    def redirect_handler(self,redirects,redirect_targets) -> tuple: # Organizes Redirect in correct forms of tuple (file_name,mode)
        stdout,stderr = self.redirect_obj.std_handler(redirects,redirect_targets)
        stdout_info, stderr_info = "",""
        if stdout[0] == "stdout":
            stdout_info = (sys.stdout,None)
        else:
            mode = "a" if stdout[0].startswith(("1>>",">>")) else "w"
            file_name = stdout[1]
            stdout_info = (file_name,mode)
        if stderr[0] == "stderr":
            stderr_info = (sys.stderr,None)
        else:
            mode = "a" if stderr[0].startswith(("2>>",">>")) else "w"
            file_name = stderr[1]
            stderr_info = (file_name,mode)
        return stdout_info, stderr_info
class Executor: # Executes the organized command recived from Resolver class with redirects
    def __init__(self,resolver_obj: Resolver,history_obj: History): 
        self.builtin_commands = {
        "echo" : lambda  args,fstdout,fstderr : print(" ".join(args),file = fstdout),
        "exit" : lambda  args,fstdout,fstderr : sys.exit(),
        "type" : lambda args,fstdout,fstderr : self.handle_type(args,fstdout,fstderr),
        "pwd" : lambda args,fstdout,fstderr : print(os.getcwd(),file = fstdout),
        "cd" : lambda args,fstdout,fstderr : self.handle_cd(args,fstdout,fstderr),
        "complete" : lambda args,fstdout,fstderr : self.handle_complete(args,fstdout,fstderr),
        "jobs" : lambda args,fstdout,fstderr : self.handle_jobs(args,fstdout,fstderr),
        "history" : lambda args,fstdout,fstderr : self.handle_history(args,fstdout,fstderr),
        "declare" : lambda args,fstdout,fstderr : self.handle_declare(args,fstdout,fstderr),
        }
        self.registered_completions = {}
        self.background_jobs = {}
        self.declared_variables = {}
        self.resolver_obj = resolver_obj
        self.history_obj = history_obj
    def handle_pipelines(self, parsed_command_list, redirects_list, redirect_targets_list):
        next_stdin = None
        processes = []
        n = len(parsed_command_list)
        for index, (parsed_command, redirects, redirect_targets) in enumerate(zip(parsed_command_list, redirects_list, redirect_targets_list)):
            cmd = parsed_command[0]
            args = parsed_command[1:]
            is_last = (index == n - 1)
            stdin_for_this = next_stdin

            if cmd in self.builtin_commands:
                if is_last:
                    fstdout = sys.stdout
                else:
                    read_fd, write_fd = os.pipe()
                    fstdout = os.fdopen(write_fd, "w")
                self.builtin_commands[cmd](args, fstdout, sys.stderr)
                if not is_last:
                    fstdout.close()
                    next_stdin = read_fd
            else:
                stdout_target = None if is_last else subprocess.PIPE
                process = subprocess.Popen([cmd] + args, stdin=stdin_for_this, stdout=stdout_target)
                processes.append(process)
                if not is_last:
                    next_stdin = process.stdout

            if stdin_for_this is not None:
                if isinstance(stdin_for_this, int):
                    os.close(stdin_for_this)
                else:
                    stdin_for_this.close()

        for process in processes:
            process.wait()
    def execute(self,parsed_command_list,redirects_list,redirect_targets_list) -> None:
        if len(parsed_command_list) > 1:
            return self.handle_pipelines(parsed_command_list,redirects_list,redirect_targets_list)
        parsed_command = parsed_command_list[0]
        redirects = redirects_list[0]
        redirect_targets = redirect_targets_list[0]
        bjob = True if parsed_command[-1] == "&" else False
        stdout_info, stderr_info = (),()
        stdout_info, stderr_info = self.resolver_obj.redirect_handler(redirects,redirect_targets)
        with ExitStack() as stack:
            fstdout = stdout_info[0] if stdout_info[1] is None else stack.enter_context(open(stdout_info[0], stdout_info[1]))
            fstderr = stderr_info[0] if stderr_info[1] is None else stack.enter_context(open(stderr_info[0],stderr_info[1]))
            cmd = parsed_command[0]
            args = parsed_command[1:] if not bjob else parsed_command[1:-1]
            if bjob:
                complete_command = " ".join(parsed_command)
                process = subprocess.Popen([cmd] + args)
                jobs =  list(self.background_jobs.values())
                if jobs:
                    current_num_id = max([num_id[0] for num_id in jobs])
                else:
                    current_num_id = 0
                self.background_jobs[process.pid] = (current_num_id + 1, complete_command, process)
                print(f"[{self.background_jobs[process.pid][0]}] {process.pid}")
                return
            if parsed_command[0] in self.builtin_commands:
                self.builtin_commands[cmd](args,fstdout,fstderr)
                return
            if  self.find_executable(cmd):
                subprocess.run([cmd, *args], stdout=fstdout, stderr=fstderr)
                return
            print(f"{cmd}: command not found")
    def handle_type(self,args,fstdout,fstderr) -> None:
        if  args[0] in self.builtin_commands:
            print(f"{args[0]} is a shell builtin",file = fstdout)
            return
        if full_path := self.find_executable(args[0]):
            print(f"{args[0]} is {full_path}", file = fstdout)
            return
        print(f"{args[0]}: not found", file = fstderr)

    def find_executable(self,args: str, For_completion = False) -> str:
        paths = os.environ.get("PATH", "").split(os.pathsep)
        # Find executable for other purposes
        for path in paths:
            path += os.sep + args if not path.endswith(os.sep) else args
            if os.path.exists(path) and os.access(path, os.X_OK):
                return (path)
    def handle_cd(self,args, fstdout,fstderr) -> None:
        if args[0] == "~":
            os.chdir(os.path.expanduser("~"))
            return
        path = os.path.abspath(args[0])
        if os.path.exists(path):
            os.chdir(path)
            return
        print(f"{args[0]}: No such file or directory",file = fstderr)
    def handle_complete(self, args, fstdout, fstderr):
        flag = args[0]
        if flag == "-p":
            if len(args) < 2:
                print("Invalid syntax", file=fstderr)
                return
            command = args[1]
            if command in self.registered_completions:
                mode, path = self.registered_completions[command]
                print(f"complete {mode} '{path}' {command}", file=fstdout)
            else:
                self._no_completion_spec(command, fstderr)
            return
        if flag =="-r":
            if len(args) < 2:
                print("Invalid syntax", file=fstderr)
                return
            command = args[1]
            if command in self.registered_completions:
                self.registered_completions.pop(command)
            else:
                self._no_completion_spec(command, fstderr)
            return
        if flag in ("-C", "-F"):
            if len(args) < 3:
                print("Invalid syntax", file=fstderr)
                return
            mode = flag
            path = f"{args[1]}"
            command = args[2]
            self.registered_completions[command] = (mode, path)
            return
        print(f"complete: {flag}: invalid option", file=fstderr)
    def _no_completion_spec(self, command, fstderr):
        print(f"complete: {command}: no completion specification", file=fstderr)
    def handle_jobs(self, args, fstdout, fstderr, job_list=None, print_ony_done=False):
        job_list = self.background_jobs.copy()
        jobs = list(job_list.items())
        signs = {}
        if len(jobs) >= 1:
            signs[jobs[-1][0]] = "+"
        if len(jobs) >= 2:
            signs[jobs[-2][0]] = "-"
        for pid, job in jobs:
            process = job[2]
            if process.poll() is None:
                status = "Running"
            else:
                status = "Done"
            command = job[1].rstrip(" &")
            sign = signs.get(pid, "")
            if status == "Done":
                print(f"[{job[0]}]{sign}  Done                 {command}")
                self.background_jobs.pop(pid)
                continue
            if not print_ony_done:
                if sign:
                    print(f"[{job[0]}]{sign}  Running                 {command}")
                else:
                    print(f"[{job[0]}]   Running                 {command}")
    def handle_history(self, args, fstdout, fstderr):
        length = len(args)
        if length > 0:
            if args[0] == "-r":
                path = args[1]
                if os.path.exists(path) and os.path.isfile(path):
                    self.history_obj.handle_history_files(path,"r")
                    return
                else:
                    print(f"{path}: No such file or directory", file = fstderr)
            if args[0] == "-w":
                path = args[1]
                self.history_obj.handle_history_files(path,"w")
                return
            if args[0] == "-a":
                path = args[1]
                if os.path.exists(path) and os.path.isfile(path):
                    self.history_obj.handle_history_files(path,"a")
                    return
                else:
                    print(f"{path}: No such file or directory", file = fstderr)
        num_display = int(args[0]) if length == 1 else length
        self.history_obj.show_history(fstdout, num_display)
        
    def handle_declare(self, args, fstdout, fstderr):
        length = len(args) 
        if length < 1:
            print("Invalid syntax",file = fstderr)
            return
        
        if "=" in args[0]:
            name, value = args[0].split("=", 1)
            if name.isidentifier():
                self.declared_variables[name] = value
                return
            print(f"declare: `{name}={value}': not a valid identifier")
            return
        if args[0] == "-p" and length > 1:
            if args[1] in self.declared_variables:
                print(f'declare -- {args[1]}="{self.declared_variables[args[1]]}"')
            else:
                print(f"declare: {args[1]}: not found",file = fstderr)
class History:
    def __init__(self):
        self.last_appended_index = 0
    def show_history(self,fstdout, display):
            total = readline.get_current_history_length()
            start_number = 1
            if not display == 0 :
                start_number = ((readline.get_current_history_length()) - display) + 1
            for i in range(start_number, total + 1):
                cmd = readline.get_history_item(i)
                print(f"    {i}  {cmd}", file=fstdout)
    def handle_history_files(self,path,mode = None):
            if mode == "r":
                with open(path,"r") as f:
                    for line in f:
                        stripped_line = line.strip()
                        if stripped_line:
                            readline.add_history(stripped_line)
            elif mode == "w":
                with open(path,"w") as f:
                    for i in range(1, readline.get_current_history_length() + 1):
                        f.write(readline.get_history_item(i) + "\n")
            else:
                total = readline.get_current_history_length()
                with open(path,"a") as f:
                    for i in range(self.last_appended_index + 1, readline.get_current_history_length() + 1):
                        f.write(readline.get_history_item(i) + "\n")
                    self.last_appended_index = total
def main():
    parser = Parser() #Constructing Parser,Redirect,Executor and Completer
    redirect_handler = Redirect()
    resolver = Resolver(parser,redirect_handler)
    history = History()
    executor = Executor(resolver, history)
    completer = Completions(executor)
    readline.set_completer(completer.handle_completion) #Readline configurations
    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind("set completion-query-items 0")
    readline.set_completion_display_matches_hook(completer.my_display_hook)
    readline.set_completer_delims(" \t\n")
    readline.parse_and_bind('"\\e[B": next-history')
    histfile = os.getenv("HISTFILE")
    if histfile and os.path.exists(histfile):
        history.handle_history_files(histfile, "r")
        history.last_appended_index = readline.get_current_history_length()
    atexit.register(clean_exit, history, histfile)
    while True:
        executor.handle_jobs("",sys.stdout,sys.stderr,print_ony_done = True)
        user_input: str = input("$ ")
        if not user_input:
            continue
        command,redirects,redirect_targets = resolver.parse(user_input,executor.declared_variables)
        executor.execute(command,redirects,redirect_targets)
def clean_exit(history_obj: History,path):
    if path:
        history_obj.handle_history_files(path, "a")
if __name__ == "__main__":
    main()