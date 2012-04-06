#!/usr/bin/env python
'''
Given a file or directory, expands "macros" using a given language.

Macro definition ("hello" is the name, and "python" is the language):
??defm:hello:python(arg1, arg2){{
print "puts 'Hello, %s!!!' \n%s" % (arg1, arg2)
}}

Macro call (eg, in ruby code):
??hello??'Joe'??'puts "Why, dude?"'??

Result:
puts 'Hello, Joe!!!'
puts "Why, dude?"
'''
import sys
import os
import re
import tempfile
import subprocess
from glob import iglob
from pprint import pprint

# CONSTANTS
# define the special char that is used in the syntax.
# probably use something that's no where else in the code.

special_char_escaped = '\?\?'
special_char = '??'
end_char = ';'
start_def = '{{'
end_def = '}}'

# REGEXES
# the regexes to match varius parts of the code
re_func_def = re.compile(
    r'%(sc)sdefm:(\w+):(\w+)\(\s*([^\)]*)\s*\)\s*%(st)s(.*?)%(en)s'\
    % {
        'sc': special_char_escaped,
        'st': start_def,
        'en': end_def,
    },
    re.I | re.S)
re_func_call = re.compile(
    r'%(sc)s(.*?)%(sc)s((?:.*?%(sc)s)*?)%(end)s'\
    % {
        'sc': special_char_escaped,
        'end': end_char,
    },
    re.I | re.S)

def indent(code, indent_str=None, ignore_first_line=False):
    if indent_str is None:
        indent_str = '    '
    out = []
    first = True
    for line in code.split('\n'):
        if first and ignore_first_line:
            out.append(line)
        else:
            out.append(indent_str + line)
        first = False
    return '\n'.join(out)

# LANGUAGES
class Lang(object):
    functions = ''
    functions_declared = set()

class Python(Lang):
    def add_function(self, name, args, code):
        self.functions += '\ndef %s(%s):\n%s' %\
                     (name,
                      ', '.join(args),
                      indent(code))
        self.functions_declared.add(name)

    def run_function(self, func, args):
        if func in self.functions_declared:
            code = "%s\n%s(%s)\n" % (self.functions, func, ','.join(args))

            # write out the file and return the result
            _, t_name = tempfile.mkstemp('.py')
            f = open(t_name, 'wb')
            if f:
                f.write(code)
                f.close()
            else:
                raise Exception("Can't write to temp file %s." % t_name)

            # run the script
            result = subprocess.check_output(['python', t_name])

            # delete the file
            os.unlink(t_name)

            # return the result
            return result.rstrip('\n')
        else:
            raise Exception("Unknown function %s" % func)

# defines the languages we can use for function calls
langs = {
    'python': Python(),
}

# DATA STRUCTURES
# stores all the files
files = {}

# stores how to call the functions
function_calls = {}

# FUNCTIONS
def define_functions(f):
    """
    Takes a file and finds all function definitions.
    """
    def define_func(m):
        """
        Takes a function match and saves it off.
        """
        name, lang, args, f_code = m.groups()
        args = map(str.strip, args.split(','))

        if name in function_calls:
            raise Exception("Trying to redeclare function %s." % name)
        l = langs.get(lang)
        if l is not None:
            l.add_function(name, args, f_code)
            function_calls[name] = l

        return ''

    code = files.get(f)
    if code is not None:
        files[f] = re_func_def.sub(define_func, code)

def str_reverse(s):
    """
    Reverses a string.
    """
    s = list(s)
    s.reverse()
    return ''.join(s)

def expand_functions():
    """
    Loop through all the files and expand the functions.
    """
    current_code = ''
    def expand(m):
        """
        Takes a match object and expands the function calls.
        """
        # get the peices
        name, args = m.groups()
        args = args.split(special_char)[:-1]

        # get the left indent.
        left_indent = ''
        i = m.start() - 1
        while i >= 0 and (current_code[i] == ' ' or current_code[i] == '\t'):
            left_indent += current_code[i]
            i -= 1
        left_indent = str_reverse(left_indent)

        # get the function result
        l = function_calls.get(name)
        if l is None:
            raise Exception("Undeclared function %s" % name)
        result = l.run_function(name, args)

        # return the result
        if result is None:
            raise Exception("Error running function")
        else:
            return indent(result, left_indent, True)

    for f, code in files.items():
        current_code = code

        files[f] = re_func_call.sub(expand, current_code)

def expand_dir(path):
    # loop through the files in the path and add them to the files structure
    for f in iglob(os.path.join(path, '*.exp.*')):
        expand_file(f)

def expand_file(fname):
    # open the file and save it's contents
    with open(fname) as f:
        files[fname] = '\n'.join([x.rstrip('\n').rstrip('\r') for x in f])

        define_functions(fname)

def write_out_files():
    for name, code in files.iteritems():
        out_name = name.replace('.exp.', '.')
        f = open(out_name, 'wb')
        if not f:
            raise IOError("Can't output the processed file %s" % name)
        f.write(code)
        f.close()

def main():
    # get the arguments
    if len(sys.argv) == 1:
        # use the current directory
        path = os.getcwd()
    elif len(sys.argv) == 2:
        path = sys.argv[1]
    else:
        sys.stderr.write("USAGE: expander [PATH]\n")
        sys.exit(1)

    # do the right thing based on the type of argument.
    if os.path.isfile(path):
        expand_file(path)
        expand_functions()
        sys.stdout.write(files[path])
    elif os.path.isdir(path):
        expand_dir(path)
        expand_functions()
        write_out_files()
    else:
        sys.stderr.write("Couldn't find the given path '%s'." % path)
        sys.exit(1)

if __name__ == "__main__":
    main()
