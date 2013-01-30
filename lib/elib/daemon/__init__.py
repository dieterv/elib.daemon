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
and the comments following his post and information gained from the books "Advanced
UNIX Programming (2nd Edition)" and "Advanced Programming in the UNIX Environment".
'''


__all__ = ['Daemon']
__version__ = '0.0.6'
__docformat__ = 'restructuredtext'


import errno
import grp
import os
import pwd
import resource
import signal
import sys


UMASK = 0        # Default file mode creation mask of the daemon.
MAXFD = 2048     # Default maximum for the number of available file descriptors.


class Daemon(object):
    '''
    The `elib.deamon.Daemon` class encapsulates all behavior expected of a
    well mannered forked daemon process.
    '''
    def __init__(self, pidfile, workdir='/', sigmap=None,
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
        :param sigmap: dictionary mapping signals to callables. If `sigmap` is None
                       signal.SIGTERM is mapped to a default function that exits the
                       daemon process.
        :param user: can be the name or uid of a user. `Daemon.start` will switch
                     to this user to run the service. If `user` is None no user
                     switching will be done.
        :param group: can be the name or gid of a group. `Daemon.start` will
                      switch to this group to run the service. If `group` is None
                      no group switching will be done.
        :param stdin: file name that will be opened and used to replace the
                      standard sys.stdin file descriptor.
                      This argument is optional and defaults to `/dev/null`.
        :param stdout: file name that will be opened and used to replace the
                       standard sys.stdout file descriptor.
                       This argument is optional and defaults to `/dev/null`.
                       Note that stdout is opened unbuffered.
        :param stderr: file name that will be opened and used to replace the
                       standard sys.stderr file descriptor.
                       This argument is optional and defaults to `/dev/null`.
                       Note that stderr is opened unbuffered.
        '''
        if pidfile is None:
            sys.exit('Error: no pid file specified')
        else:
            self.pidfile = pidfile

        if workdir is None or not os.path.isdir(workdir):
            sys.exit('Error: workdir \'%s\' does not exist' % workdir)
        else:
            self.workdir = workdir

        if sigmap is None:
            self.sigmap = {signal.SIGTERM: self._terminate}
        else:
            self.sigmap = sigmap

        if user is None:
            self.uid = None
        elif isinstance(user, basestring):
            self.uid = pwd.getpwnam(user).pw_uid
        elif isinstance(user, int):
            self.uid = user
        else:
            raise TypeError('user must be a string or int, but received a %s' % type(user))

        if group is None:
            self.gid = None
        elif isinstance(group, basestring):
            self.gid = grp.getgrnam(group).gr_gid
        elif isinstance(group, int):
            self.gid = group
        else:
            raise TypeError('group must be a string or int, but received a %s' % type(group))

        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

    def start(self):
        '''
        Daemonize the running script. When this method returns, the process is
        completely decoupled from the parent environment.
        '''
        # Note: what's with sys.exit() and os._exit()?
        # os._exit is like sys.exit(), but it doesn't call any functions registered
        # with atexit (and on_exit) or any registered signal handlers.  It also
        # closes any open file descriptors. Using sys.exit() may cause all stdio
        # streams to be flushed twice and any temporary files may be unexpectedly
        # removed.  It's therefore recommended that child branches of a fork()
        # and the parent branch of a daemon use os._exit().

        # Prevent multiple instances. Note this is racy but good enough for now...
        try:
            with open(self.pidfile, 'rb') as f:
                pid = int(f.read().strip())
        except (IOError, ValueError):
            pass
        else:
            try:
                os.kill(pid, 0)
            except OSError:
                # good, pid is not running
                pass
            else:
                # bail out, pid lives
                sys.stderr.write('Already running as %s\n' % pid)
                sys.stderr.flush()
                os._exit(os.EX_OSERR)

        # Ensure directories for pidfile and self.std(in|out|err) exist
        for f in [self.pidfile, self.stdin, self.stdout, self.stderr]:
            if not os.path.isdir(os.path.abspath(os.path.dirname(f))):
                os.makedirs(os.path.dirname(f), 0o755)

        # Fork the first child and exit its parent immediately.
        try:
            if os.fork() != 0:
                os._exit(os.EX_OK)
        except OSError as e:
            sys.stderr.write('First fork failed: (%d) %s\n' % (e.errno, e.strerror))
            sys.stderr.flush()
            os._exit(os.EX_OSERR)

        # To become the session leader of this new session and the process group
        # leader of the new process group, we call os.setsid().  The process is
        # also guaranteed not to have a controlling terminal.
        os.setsid()

        # Fork the second child and exit its parent immediately.
        # This causes the second child process to be orphaned, making the init
        # process responsible for its cleanup.  And, since the first child is
        # a session leader without a controlling terminal, it's possible for
        # it to acquire one by opening a terminal in the future (System V-
        # based systems).  This second fork guarantees that the child is no
        # longer a session leader, preventing the daemon from ever acquiring
        # a controlling terminal.
        try:
            if os.fork() != 0:
                os._exit(os.EX_OK)
        except OSError as e:
            sys.stderr.write('Second fork failed: (%d) %s\n' % (e.errno, e.strerror))
            sys.stderr.flush()
            os._exit(os.EX_OSERR)

        # Write pid file
        with open(self.pidfile, 'wb') as f:
            f.write(str(os.getpid()))

        # Reset the file mode creation mask.
        os.umask(UMASK)

        # Since the current working directory may be on a mounted filesystem,
        # we avoid the issue of not being able to unmount that filesystem at
        # shutdown time by changing the current directory to self.workdir.
        # This is usually the root directory.
        os.chdir(self.workdir)

        # Switch effective group
        if self.gid is not None:
            os.setegid(self.gid)

        # Switch effective user
        if self.uid is not None:
            os.seteuid(self.uid)
            os.environ['HOME'] = pwd.getpwuid(self.uid).pw_dir

        # Attach signal handles
        for signum, callback in self.sigmap.items():
            signal.signal(signum, callback)

        # Close all open file descriptors. This prevents the child from keeping
        # open any file descriptors inherited from the parent.
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]

        if (maxfd == resource.RLIM_INFINITY):
            maxfd = MAXFD

        # Close all file descriptors except std(in|out|err).
        exclude = [x.fileno() for x in [self.stdin, self.stdout, self.stderr, sys.stdin, sys.stdout, sys.stderr] if hasattr(x, 'fileno')]
        for fd in reversed(range(maxfd)):
            if fd not in exclude:
                try:
                    os.close(fd)
                except OSError as e:
                    if e.errno == errno.EBADF:
                        # File descriptor was not open
                        pass
                    else:
                        sys.stderr.write('Failed to close file descriptor %d: (%d) %s\n' % (fd, e.errno, e.strerror))
                        sys.stderr.flush()
                        os._exit(os.EX_OSERR)

        # Redirect std(in|out|err) to self.std(in|out|err)
        si = open(self.stdin, "r")
        os.close(sys.stdin.fileno())
        os.dup2(si.fileno(), sys.stdin.fileno())
        sys.__stdin__ = sys.stdin

        sys.stdout.flush()
        so = open(self.stdout, "a+", 0)
        os.close(sys.stdout.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        sys.__stdout__ = sys.stdout

        sys.stderr.flush()
        se = open(self.stderr, "a+", 0)
        os.close(sys.stderr.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        sys.__stderr__ = sys.stderr

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
            with open(self.pidfile, 'rb') as f:
                pid = int(f.read().strip())
        except IOError as e:
            sys.exit('Error: can\'t open pidfile %s: %s' % (self.pidfile, str(e)))
        except ValueError:
            sys.exit('Error: mangled pidfile %s: %r' % self.pidfile)

        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            # process already disappeared -> ignore
            pass

    def _terminate(self, signum, frame):
        sys.exit('Terminating on signal %s' % signum)
