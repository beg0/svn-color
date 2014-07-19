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
