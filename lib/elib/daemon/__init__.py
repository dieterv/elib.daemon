# -*- coding: utf-8 -*-
#
# Copyright © 2007-2010 Dieter Verfaillie <dieterv@optionexplicit.be>
#
# This file is part of elib.daemon.
#
# elib.daemon is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# elib.daemon is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with elib.daemon. If not, see <http://www.gnu.org/licenses/>.


'''
The elib.daemon module can be used on Unix systems to fork a daemon process.

It is based on `Jürgen Hermann's recipe <http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66012>`_
and the comments following his post, information gained from the books Advanced
UNIX Programming (2nd Edition) and Advanced Programming in the UNIX Environment.
'''


__all__ = ['Daemon']
__version__ = '0.0.3'
__docformat__ = 'restructuredtext'


import os
import sys
import grp
import pwd
import resource
import signal


UMASK = 0        # Default file mode creation mask of the daemon.
MAXFD = 1024     # Default maximum for the number of available file descriptors.


class Daemon(object):
    '''
    The `elib.deamon.Daemon` class encapsulates all behavior expected of a
    well mannered forked daemon process.
    '''
    def __init__(self, pidfile, workdir='/',
                 sighupfunc=None, sigtermfunc=None,
                 user=None, group=None,
                 stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        '''
        :param pidfile: must be the name of a file. The newly forked daemon
                        process will write it's pid to this file.
                        `Daemon.stop` uses this file to kill the daemon process
                        specified in the pidfile.
        :param workdir: when the daemon process starts, it will change the current
                        working directory to `workdir`.
                        This argument is optional and defaults to `/`.
        :param sighupfunc: a callable with the signature `sighupfunc(signum, frame)`
                           that will be called when the forked daemon process
                           receives a `SIG_HUP` signal. You can use this to reload
                           configuration files, etc.
                           This argument is optional and defaults to `None`.
                           Note that exceptions raised by `sighupfunc` are silently
                           ignored.
        :param sigtermfunc: a callable with the signature `sigtermfunc(signum, frame)`
                            that will be called when the forked daemon process
                            receives a `SIG_TERM` signal, before the pidfile is
                            removed and the process exits.
                            This argument is optional and defaults to `None`.
                            Note that exceptions raised by `sigtermfunc` are
                            silently ignored.
        :param user: can be the name or uid of a user. `Daemon.start` will switch
                     to this user to run the service. If user is None no user
                     switching will be done.
        :param group: can be the name or gid of a group. `Daemon.start` will
                      switch to this group to run the service. If group is None
                      no group switching will be done.
        :param stdin: file name that will be opened and used to replace the
                      standard sys.stdin file descriptor.
                      This argument is optional and defaults to `/dev/null`.
        :param stdout: file name that will be opened and used to replace the
                       standard sys.stdout file descriptor.
                       This argument is optional and defaults to `/dev/null`.
        :param stderr: file name that will be opened and used to replace the
                       standard sys.stderr file descriptor.
                       This argument is optional and defaults to `/dev/null`.
                       Note that stderr is opened unbuffered, so if it shares a
                       file with stdout then interleaved output may not appear
                       in the order that you expect.
        '''
        self.pidfile = pidfile
        self.workdir = workdir
        self.workdir = workdir
        self.sighupfunc = sighupfunc
        self.sigtermfunc = sigtermfunc

        if isinstance(user, basestring):
            self.user = pwd.getpwnam(user).pw_uid
        elif isinstance(user, int):
            self.user = user
        else:
            raise TypeError('user must be a string or int, but received a %s' % type(user))

        if isinstance(group, basestring):
            self.group = grp.getgrnam(group).gr_gid
        elif isinstance(group, int):
            self.group = group
        else:
            raise TypeError('group must be a string or int, but received a %s' % type(group))

        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

    def start(self):
        '''
        Daemonize the running script. When this method returns the process is
        completely decoupled from the parent environment.
        '''
        # Note: what's with sys.exit() and os._exit()?
        # os._exit is like sys.exit(), but it doesn't call any functions registered
        # with atexit (and on_exit) or any registered signal handlers.  It also
        # closes any open file descriptors.  Using sys.exit() may cause all stdio
        # streams to be flushed twice and any temporary files may be unexpectedly
        # removed.  It's therefore recommended that child branches of a fork()
        # and the parent branch of a daemon use os._exit().

        # Reset the file mode creation mask.
        os.umask(UMASK)

        # Fork the first child and exit the parent immediately.
        try:
            pid = os.fork()

            if pid != 0:
                os._exit(os.EX_OK)
        except OSError, e:
            sys.stderr.write('First fork failed: (%d) %s\n' % (e.errno, e.strerror))
            sys.stderr.flush()
            os._exit(os.EX_OSERR)

        # To become the session leader of this new session and the process group
        # leader of the new process group, we call os.setsid().  The process is
        # also guaranteed not to have a controlling terminal.
        os.setsid()

        # Fork the second child and exit the parent immediately.
        # This causes the second child process to be orphaned, making the init
        # process responsible for its cleanup.  And, since the first child is
        # a session leader without a controlling terminal, it's possible for
        # it to acquire one by opening a terminal in the future (System V-
        # based systems).  This second fork guarantees that the child is no
        # longer a session leader, preventing the daemon from ever acquiring
        # a controlling terminal.
        try:
            pid = os.fork()

            if pid != 0:
                os._exit(os.EX_OK)
        except OSError, e:
            sys.stderr.write('Second fork failed: (%d) %s\n' % (e.errno, e.strerror))
            sys.stderr.flush()
            os._exit(os.EX_OSERR)

        # Since the current working directory may be on a mounted filesystem,
        # we avoid the issue of not being able to unmount that filesystem at
        # shutdown time by changing the current directory to self.workir.
        # This is usually the root directory.
        os.chdir(self.workdir)

        # Write pid file
        if not os.path.isdir(os.path.abspath(os.path.dirname(self.pidfile))):
            os.makedirs(os.path.dirname(self.pidfile), 0o755)

        open(self.pidfile, 'w').write(str(os.getpid()))

        # Close all open file descriptors. This prevents the child from keeping
        # open any file descriptors inherited from the parent.
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]

        if (maxfd == resource.RLIM_INFINITY):
            maxfd = MAXFD

        # Iterate through and close all file descriptors.
        for fd in range(0, maxfd):
            try:
                os.close(fd)
            except OSError:
                pass

        # Reopen file descriptors 0, 1 and 2 (stdin, stdout and stderr).
        sys.stdin = sys.__stdin__ = open(self.stdin, 'r')
        sys.stdout = sys.__stdout__ = open(self.stdout, 'a+')
        sys.stderr = sys.__stderr__ = open(self.stderr, 'a+', 0)

        # Attach signal handles
        signal.signal(signal.SIGHUP, self._handlesighup)
        signal.signal(signal.SIGTERM, self._handlesigterm)

        # Switch effective group
        if self.group is not None:
            os.setegid(self.group)

        # Switch effective user
        if self.user is not None:
            os.seteuid(self.user)
            os.environ['HOME'] = pwd.getpwuid(self.user).pw_dir

    def stop(self):
        '''
        Sends a SIGTERM signal to the running daemon, if any. The pid of the
        running daemon will be read from the pidfile specified in the constructor.
        '''
        if self.pidfile is None:
            sys.exit('Error: no pid file specified')
        elif not os.path.isfile(self.pidfile):
            sys.exit('Error: pid file \'%s\' does not exist' % self.pidfile)

        try:
            pid = int(open(self.pidfile, 'rb').read().strip())
        except IOError, exc:
            sys.exit('Error: can\'t open pidfile %s: %s' % (self.pidfile, str(exc)))
        except ValueError:
            sys.exit('Error: mangled pidfile %s: %r' % self.pidfile)

        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            # process already disappeared -> ignore
            pass

    def _handlesighup(self, signum, frame):
        '''
        Passes a SIG_HUP signal to `Daemon.sighupfunc`.
        '''
        if self.sighupfunc is not None and callable(self.sighupfunc):
            try:
                self.sighupfunc(signum, frame)
            except:
                pass

    def _handlesigterm(self, signum, frame):
        '''
        Handle a SIG_TERM signal: Remove the pid file and exit.
        '''
        if self.sigtermfunc is not None and callable(self.sigtermfunc):
            try:
                self.sigtermfunc(signum, frame)
            except:
                pass

        if self.pidfile is not None:
            try:
                os.remove(self.pidfile)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                pass

        sys.exit(os.EX_OK)
