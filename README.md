SVN-Color
========

SVN-Color add missing features to the standard - command line - subversion 
client on Linux.

The standard subversion client on linux - svn - does a wonderful job at 
managing changes on files and communicating with the subversion server. However
it lacks a lots of feature to make it user friendly and easy to use on a 
terminal. The goal of SVN-Color is to add these missing features, so that users
can enjoy the use of this great Version Control System which is subversion.

In particular, SVN-Color adds the following features:
 - Automatically colorize output of most svn command (diff, status, log, add, 
    delete, update, ...)
 - automatically pipe to pager if needed
 - Allow user to define its own aliases
 - Add Spell Correction on svn command
 - Improve some existing commands like 'commit' or 'update'
 - Ability to define its own svn commands

This program is simply a wrapper around the standard command line svn client. 
However, as far as I knwon, it's the most complete wrapper for svn. Most of 
wrapper I'have seen out there are simply wrapper to colorize 'diff' or 'update'
output. Often they does not work if the standard output is not a terminal.
Finally, none of them add as many features as svn-color does.

Configuration
-------------

SVN-Color is fully functionnal with the following software:
 - Python 2.7,
 - svn 1.8.8 (r1568071)
 - Ubuntu 14.04 LTS

It probably works with different version of software, but it was not tested

Installation
------------
For now, SVN-Color is very simple, only one file. Put svn-color.py somewhere in
a directory knwon in your $PATH variable. For example in /usr/local/bin/ and 
give it executable rights.

For example:

 $ sudo cp svn-color.py /usr/local/bin && sudo chmod a+x /usr/local/bin/svn-color.py

You can define aliases to svn commandes. For that create a 'aliases' file
similar to the one provided and put it in your ~/.subversion directory.

For example:

 $ cp aliases ~/.subversion/aliases

Usage
-----
SVN-Color is a drop-in replacement of the standard svn client. Simply replace 
'svn' call to 'svn-color.py'.

e.g.
	$ svn-color.py status -q
or
	$ svn-color.py commit myfile.py myotherfile.py

Alternativelly, you can create an alias in your .bashrc file (given that the 
shell you are using is bash). At the end of your .bashrc file (located in your
home directory), add the following line:

 alias svn=svn-color.py


Enjoy enhance experience with SVN
