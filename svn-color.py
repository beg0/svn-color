#!/usr/bin/python

# This file is part of SVN-Color.  SVN-Color is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 3
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright beg0 <beg0@free.fr>
#

import sys, os
import getopt
import subprocess, errno, select
import re
import traceback
import StringIO, pipes
import ConfigParser
import collections

SVN_BIN='/usr/bin/svn'
SVN_CONFIG_DIR=os.path.expanduser('~/.subversion')

ESCAPE_END = "\033[m"
STATUS_NONVERSIONCONTROL_CLR = "\033[1;34m"
STATUS_MISSING_CLR = "\033[1;31m"
STATUS_ADDED_CLR = "\033[1;32m"
STATUS_MODIFIED_CLR = "\033[1;33m"
STATUS_DELETED_CLR = "\033[0;31m"
STATUS_IGNORED_CLR = "\033[0;37m"
STATUS_CONFLICTED_CLR = "\033[0;31m"
LOG_SEPARATOR_CLR = "\033[1;32m"
LOG_SUMMARY_CLR = "\033[1;31m"

BUILTIN_ALIASES = {
	'praise': 	'blame',
	'annotate': 	'blame',
	'ann':		'blame',
	'cl':		'changelist',
	'co':		'checkout',
	'ci':		'commit',
	'cp':		'copy',
	'del':		'delete',
	'remove':	'delete',
	'rm':		'delete',
	'di':		'diff',
	'?':		'help',
	'h':		'help',
	'ls':		'list',
	'mv':		'move',
	'rename':	'move',
	'ren':		'move',
	'pdel':		'propdel',
	'pd':		'propdel',
	'pedit':	'propedit',
	'pe':		'propedit',
	'pget':		'propget',
	'pg':		'propget',
	'plist':	'proplist',
	'pl':		'proplist',
	'pset':		'propset',
	'ps':		'propset',
	'stat':		'status',
	'st':		'status',
	'sw':		'switch',
	'up':		'update',
}

AVAILABLE_OPERATIONS = [ 'add', 'blame', 'cat', 'changelist', 'checkout', 'cleanup', 'commit', 'copy',
			 'delete', 'diff', 'export', 'help', 'import', 'info', 'list', 'lock',
			 'log', 'merge', 'mergeinfo', 'mkdir', 'move', 'patch', 'propdel', 'propedit',
			 'propget', 'proplist', 'propset', 'relocate', 'resolve', 'resolved', 'revert', 'status',
			 'switch', 'unlock', 'update', 'upgrade' ]
 
INTERACTIVE_ONLY = ['commit', 'propedit', 'cat', 'copy' ]


# The spell corrector code is largely inspired from  Peter Norvig's article
# "How to Write a Spelling Corrector" - http://norvig.com/spell-correct.html
class SpellCorrecter:
	alphabet = 'abcdefghijklmnopqrstuvwxyz'
	def __init__(self, features):
		    self.NWORDS = collections.defaultdict(lambda: 1)
		    for f in features:
		        self.NWORDS[f] += 1
	
	def correct(self, word):
		def edits1 (word):
			splits     = [(word[:i], word[i:]) for i in range(len(word) + 1)]
			deletes    = [a + b[1:] for a, b in splits if b]
			transposes = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b)>1]
			replaces   = [a + c + b[1:] for a, b in splits for c in SpellCorrecter.alphabet if b]
			inserts    = [a + c + b     for a, b in splits for c in SpellCorrecter.alphabet]
			return set(deletes + transposes + replaces + inserts)

		def known_edits2(word):
			return set(e2 for e1 in edits1(word) for e2 in edits1(e1) if e2 in self.NWORDS)

		def known(words):
			return set(w for w in words if w in self.NWORDS)

		candidates = known([word]) or known(edits1(word)) or known_edits2(word) #or [word]
		return candidates
		#return max(candidates, key=self.NWORDS.get)


# formatter for "status" operation but also "add", "delete", ...
def format_status_line(line):
	if line.startswith("?"):			# non version control (?)
		return "\033[1;34m" + line + "\033[m"
	elif line.startswith("A") and not line.startswith("At revision"):			# Added
		return "\033[1;32m" + line + "\033[m"
	elif line.startswith("C"):			# Conficted
		return "\033[0;31m" + line + "\033[m"
	elif line.startswith("D"):			# Deleted
		return "\033[1;31m" + line + "\033[m"
	elif line.startswith("I"):			# Ignored
		return "\033[0;37m" + line + "\033[m"
	elif line.startswith("M"):			# Modified
		return "\033[1;33m" + line + "\033[m"
	elif line.startswith("U") and not line.startswith("Updat"):			# Updated 
		return "\033[1;33m" + line + "\033[m"
	elif line.startswith("G"):			# merGed 
		return "\033[1;34m" + line + "\033[m"
	elif line.startswith("!"):			# missing (!)
		return "\033[1;31m" + line + "\033[m"
	elif line.startswith("E"):			# Existed 
		return "\033[0;31m" + line + "\033[m"
	elif line.startswith("R"):			# Replaced 
		return "\033[0;35m" + line + "\033[m"
	else:
		return line

def format_diff_line(line):
	if line.startswith("+") or line.startswith(">") or line.startswith("--- "): #new
		return  "\033[1;34m" + line + "\033[m"
	elif line.startswith("-") or line.startswith("<") or line.startswith("*** "): #old
		return  "\033[1;31m" + line + "\033[m"
	elif line.startswith("Only in") or line.startswith("@") or line.startswith("****"): #diff specific
		return "\033[1;35m" + line + "\033[m"
	elif line.startswith("Index: ") or line.startswith("====") or line.startswith("retrieving ") or line.startswith("diff ") or line.startswith("RCS file: "): #SVN specific
		return "\033[1;32m" + line + "\033[m"
	else:
		return line

def format_log_line(line):
	if re.match("^-{3,}$",line):			# separator line
                return "\033[1;32m" + line + "\033[m"
	elif re.match("^r\d+\s+\|\s+", line):		# summary line, TODO: improve this
		return "\033[1;31m" + line + "\033[m"
	elif line.startswith("   "):			# "Changed path" line (in verbose mode)
		return "   " + format_status_line(line.lstrip())
	else:
		return line

def format_blame_line(line):
	return re.sub("(\\s*\\d+\\s*)([\\w\\d_-]+)","\033[0;33m\\1\033[0;32m\\2\033[m",line,1)

def stderr_formater(line):
	return "\033[0;31m" + line + "\033[m"


def format_info_line(line):
	return re.sub(r'^(.*?:)',r'\033[00;34m\1\033[00m',line)

def noop_formater(line):
	return line

def run_svn_op(formater, err_formater, fd_out, fd_err, svn_args):
	svn_cmd_line = [SVN_BIN] + svn_args
	
	stdout_dest = fd_out
	if formater:
		stdout_dest = subprocess.PIPE
	
	stderr_dest = fd_err
	if err_formater:
		stderr_dest = subprocess.PIPE

	if formater:
		svn_process=subprocess.Popen(svn_cmd_line, stdout=stdout_dest, stderr=stderr_dest)
		try:
			fd_to_watch = []
			if stdout_dest == subprocess.PIPE:
				fd_to_watch.append(svn_process.stdout)	
				
			if stderr_dest == subprocess.PIPE:
				fd_to_watch.append(svn_process.stderr)	
				
			while fd_to_watch:
				
				(readable, _, _) = select.select(fd_to_watch, [], [])

				out_line = ''
				err_line = ''
				if svn_process.stdout in readable:
					out_line = svn_process.stdout.readline()
					if out_line and fd_out != None:
						fd_out.write(formater(out_line))
					else:	#EOF
						fd_to_watch.remove(svn_process.stdout)
				if svn_process.stderr in readable:
					err_line = svn_process.stderr.readline()
					if err_line and fd_err != None:
						fd_err.write(err_formater(err_line))
					else: #EOF
						fd_to_watch.remove(svn_process.stderr)

		except KeyboardInterrupt, e: # Ctrl-C
			svn_process.terminate()	
			raise e
		except IOError, e:
			if e.errno == errno.EPIPE:
				 svn_process.terminate()
			else:
				raise e	
		return svn_process.wait()
	else:
		return subprocess.call(svn_cmd_line)
	

def run_single_svn_operation(svn_operation, svn_options, svn_output, svn_error, colorize):
	svn_args = [svn_operation] + svn_options
	if colorize:
		err_formater = stderr_formater
		if svn_operation == "status" or svn_operation == "update" or svn_operation == "add" or svn_operation == "delete" or svn_operation == "mkdir" or	svn_operation == "move" or svn_operation == "checkout" or svn_operation == "merge":
			formater = format_status_line
		elif svn_operation == "diff":
			if '--summarize' in svn_options:
				formater = format_status_line
			else:
				formater = format_diff_line
		elif svn_operation == "log":
			formater = format_log_line
		elif svn_operation == "blame":
			formater = format_blame_line
		elif svn_operation == "info":
			formater = format_info_line
		elif svn_operation in INTERACTIVE_ONLY: # commit, propedit and so on...
			formater = err_formater = None
		else:
			formater = noop_formater # pass throw
	else:
		formater = err_formater = noop_formater # no color
		
	
	run_svn_op(formater, err_formater, svn_output, svn_error, svn_args)


def get_current_rev(svn_args):
	svn_info = StringIO.StringIO()

	#remove "-r 1234" option in command line if any
	if "-r" in svn_args:
		option_index = svn_args.index("-r")
		svn_args.pop(option_index + 1)
		svn_args.pop(option_index)

	run_svn_op(noop_formater, noop_formater, svn_info, None, ["info"] + svn_args)

	old_rev_info = re.search("Revision:\\s*(\\d+)",svn_info.getvalue())
	if old_rev_info:
		return int(old_rev_info.group(1))

	else:
		return None

def get_last_changed_rev(svn_args):
	svn_info = StringIO.StringIO()
	run_svn_op(noop_formater, noop_formater, svn_info, None, ["info"] + svn_args)

	old_rev_info = re.search("Last Changed Rev:\\s*(\\d+)",svn_info.getvalue())
	if old_rev_info:
		return int(old_rev_info.group(1))

	else:
		return None

# Wrapper around 'update' that also display log since the last update
def alias_updateverbose(svn_args, svn_output, svn_error, colorize):

	formater = err_formater = noop_formater
	
	old_rev = get_current_rev(svn_args)

	if colorize:
		err_formater = stderr_formater
		formater = format_status_line
		
	run_svn_op(formater, err_formater, svn_output, svn_error, ["update"] + svn_args)

	new_rev = get_current_rev(svn_args)
	

	rev_request = None
	if old_rev != None and new_rev != None:
		if old_rev < new_rev:
			rev_request = str(old_rev + 1) + ":" + str(new_rev)
		elif old_rev > new_rev:
			rev_request = str(new_rev) + ":" + str(old_rev - 1)
		elif svn_output != None:
			svn_output.write("No changes.\n")

	if rev_request != None:
		if colorize:
			formater = format_log_line

		run_svn_op(formater, err_formater, svn_output, svn_error, ["log", "-v", "-r",rev_request] + svn_args)

BUILTIN_ALIASES["updateverbose"] = alias_updateverbose
BUILTIN_ALIASES["upv"] = alias_updateverbose

# Wrapper around 'commit' subcommand that remove commitfile given in argument (if any)
def alias_commitextended(svn_args, svn_output, svn_error, colorize):

	commitfile = None
	for opt in [ '-F', '--file']:
		try:
			optidx = svn_args.index(opt)
			commitfile = svn_args[optidx+1]
		except ValueError, IndexError:
			pass
		if commitfile != None:
			break

	if len(svn_args) > 0 and svn_args[0] ==  '--non-interactive':
		svn_args.remove('--non-interactive')

	exit_code = run_svn_op(None, None, svn_output, svn_error,["commit"] + svn_args)

	#remove commitfile
	if exit_code == 0 and commitfile != None:
		os.remove(commitfile)

BUILTIN_ALIASES["commitextended"] = alias_commitextended
BUILTIN_ALIASES["cix"] = alias_commitextended


#def alias_dummy_st(svn_args, svn_output, svn_error, colorize):
#
#	print "svn_args=",svn_args
#	formater = err_formater = lambda(l): l # no color
#	if colorize:
#		err_formater = stderr_formater
#		formater = format_status_line
#		
#	run_svn_op(formater, err_formater, svn_output, svn_error, ["status"] + svn_args[1:])
#
#
#BUILTIN_ALIASES["dummy_st"] = alias_dummy_st

#FIXME: this does not handle the case of option with arguments
#for example: svn --old 1234 --new 12345 diff
def svn_extract_operation(argv=None):
	if argv is None:
		argv = sys.argv

	if len(argv) < 2:
		return None,[] 

	svn_operation = None
	svn_options = argv[1:]
	for arg in argv[1:]:
		if not arg.startswith('-'): # not an option argument? says it's the svn operation
			svn_operation = arg
			svn_options.remove(svn_operation)
			break

	return svn_operation, svn_options

def print_operation_not_found(svn_operation, corrections):
	sys.stderr.write("Unknown subcommand: %s\n" % pipes.quote(svn_operation))
	sys.stderr.write("Type 'svn help' for usage.\n")

	if len(corrections) > 0:
		sys.stderr.write("\n")
		if(len(corrections) == 1):
			sys.stderr.write("Did you mean this?\n")
		else:
			sys.stderr.write("Did you mean one of these?\n")
		for c in corrections:
			sys.stderr.write("\t" + c + "\n")

if __name__ == '__main__':
	pager_process = None

	svn_operation, svn_options = svn_extract_operation(sys.argv)

	# No args? let svn handle that
	if len(sys.argv) < 2 or svn_operation is None:
		os.execl(SVN_BIN, *sys.argv)

	#read config
	user_aliases = ConfigParser.ConfigParser()
	user_aliases.read(os.path.join(SVN_CONFIG_DIR,'aliases'))

	#resolve alias
	if user_aliases.has_option("aliases",svn_operation):
		svn_operation = user_aliases.get("aliases",svn_operation)

	if BUILTIN_ALIASES.has_key(svn_operation):
		svn_operation = BUILTIN_ALIASES[svn_operation]

	# unresolvable ? print error
	if svn_operation not in AVAILABLE_OPERATIONS + BUILTIN_ALIASES.values():
		available_ops = BUILTIN_ALIASES.keys() + AVAILABLE_OPERATIONS + user_aliases.options("aliases")
		sc = SpellCorrecter(available_ops)
		print_operation_not_found(svn_operation, sc.correct(svn_operation))
		sys.exit(1)

	#where to send the (formated) output of svn
	svn_output = sys.stdout
	svn_error = sys.stderr

	#TODO: check we are in interactive mode
	pager_path = None
	if sys.stdout.isatty():
		if os.environ.has_key("SVN_PAGER"):
			pager_path = os.environ["SVN_PAGER"]
		elif os.environ.has_key("PAGER"):
			pager_path = os.environ["PAGER"]
		else:
			pager_path = "pager" # TODO: check it exists

	if pager_path != None and len(pager_path) > 0 and not (svn_operation in INTERACTIVE_ONLY):
                #Make sur pager handle colors correctly (and exit if we don't need it)
                pager_env = os.environ;
                if not pager_env.has_key("LESS"):
                    pager_env["LESS"]="FRSX" # quit-if-one-screen, RAW-CONTROL-CHARS, chop-long-lines, no-init
                if not pager_env.has_key("LV"):
                    pager_env["LV"]="-c"

		pager_process = subprocess.Popen(pager_path, stdin=subprocess.PIPE, stdout=sys.stdout, shell=True, env=pager_env)
		svn_output = svn_error = pager_process.stdin
		svn_options.insert(0,"--non-interactive")

	colorize = 'auto'
	opts, args = (None, None)
	try:
		opts, args = getopt.getopt(svn_options, "", ["color="])
	except getopt.GetoptError as err:
#	        # print help information and exit:
#        	print(err) # will print something like "option -a not recognized"
#	        usage()
#	       	sys.exit(2)
		pass

#	for o, a in opts:
#		if o == "color":
#			if a in ("never","auto","always"):
#				colorize=a
#			else:
#				assert False, "invalid option 'color'"
#		else:
#		    assert False, "unhandled option"	
#
	colorize = True
	if not sys.stdout.isatty():
		colorize = False;

	if colorize:
		err_formater = stderr_formater
	else:
		err_formater = lambda(l): l

	try:
		if hasattr(svn_operation,'__call__'):
			svn_operation(svn_options, svn_output, svn_error, colorize)
		else:
			run_single_svn_operation(svn_operation,  svn_options, svn_output, svn_error, colorize)

	except KeyboardInterrupt, e: # Ctrl-C
		#if pager_process != None:
		#	pager_process.stdin.close()
		#	pager_process.send_signal(15)
		#	pager_process.wait()
		#raise e
		pass
	except SystemExit, e: # sys.exit()
		raise e
	except Exception, e:
		sys.stderr.write(err_formater('ERROR, UNEXPECTED EXCEPTION\n'))
		sys.stderr.write(err_formater(str(e)+"\n"))
		sys.stderr.write(err_formater(traceback.format_exc()))
		os._exit(1)

	if pager_process != None:
		pager_process.stdin.close()
		pager_process.wait()
