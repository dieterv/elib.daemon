# -*- coding: utf-8 -*-
#
# Copyright © 2007-2010 Dieter Verfaillie <dieterv@optionexplicit.be>
#
# This file is part of etk.docking.
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
The elib.daemon module can be used on Linux systems to fork a daemon process. It
is based on `Jürgen Hermann's recipe <http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66012>`_.

An example script might look like this::

    from util import daemon

    counter = daemon.Daemon(
        stdin="/dev/null",
        stdout="/tmp/daemon.log",
        stderr="/tmp/daemon.log",
        pidfile="/var/run/counter/counter.pid",
        user="nobody"
    )

    if __name__ == "__main__":
        if counter.service():
            import sys, os, time
            sys.stdout.write("Daemon started with pid %d\n" % os.getpid())
            sys.stdout.write("Daemon stdout output\n")
            sys.stderr.write("Daemon stderr output\n")
            sys.stdout.flush()
            c = 0
            while True:
                sys.stdout.write('%d: %s\n' % (c, time.ctime(time.time())))
                sys.stdout.flush()
                c += 1
                time.sleep(1)
'''


__all__ = ['install', 'install_module']
__version__ = '0.0.3'
__docformat__ = 'restructuredtext'


import sys
import os

import grp
import pwd
import signal


UMASK = 0        # File mode creation mask of the daemon.
WORKDIR = "/"    # Default working directory for the daemon.
MAXFD = 1024     # Default maximum for the number of available file descriptors.


class Daemon(object):
    """
    The <class>Daemon</class> class provides methods for <pyref method="start">starting</pyref>
    and <pyref method="stop">stopping</pyref> a daemon process as well as
    <pyref method="service">handling command line arguments</pyref>.
    """
    def __init__(self, stdin="/dev/null", stdout="/dev/null", stderr="/dev/null", pidfile=None, user=None, group=None, exitfunc=None):
        """
        <par>The <arg>stdin</arg>, <arg>stdout</arg>, and <arg>stderr</arg> arguments
        are file names that will be opened and be used to replace the standard file
        descriptors in <lit>sys.stdin</lit>, <lit>sys.stdout</lit>, and
        <lit>sys.stderr</lit>. These arguments are optional and default to
        <lit>"/dev/null"</lit>. Note that stderr is opened unbuffered, so if it
        shares a file with stdout then interleaved output may not appear in the
        order that you expect.</par>

        <par><arg>pidfile</arg> must be the name of a file. <method>start</method>
        will write the pid of the newly forked daemon to this file. <method>stop</method>
        uses this file to kill the daemon.</par>

        <par><arg>user</arg> can be the name or uid of a user. <method>start</method>
        will switch to this user for running the service. If <arg>user</arg> is
        <lit>None</lit> no user switching will be done.</par>

        <par>In the same way <arg>group</arg> can be the name or gid of a group.
        <method>start</method> will switch to this group.</par>
        """
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
        self.user = user
        self.group = group
        self.exitfunc = exitfunc

    def openstreams(self):
        """
        Open the standard file descriptors stdin, stdout and stderr as specified
        in the constructor.
        """
        sys.stdout.flush()
        sys.stderr.flush()

        # Todo: Why does this not work????
        # Close all open file descriptors.  This prevents the child from keeping
        # open any file descriptors inherited from the parent.  There is a variety
        # of methods to accomplish this task.  Three are listed below.
        #maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        #if (maxfd == resource.RLIM_INFINITY):
        #    maxfd = MAXFD

        # Iterate through and close all file descriptors.
        #for fd in range(0, maxfd):
        #    try:
        #        os.close(fd)
        #    except OSError:    # ERROR, fd wasn't open to begin with (ignored)
        #        pass

        si = open(self.stdin, "r")
        so = open(self.stdout, "a+")
        se = open(self.stderr, "a+", 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

    def handlesighup(self, signum, frame):
        """
        Handle a <lit>SIG_HUP</lit> signal: Reopen standard file descriptors.
        """
        self.openstreams()

    def handlesigterm(self, signum, frame):
        """
        Handle a <lit>SIG_TERM</lit> signal: Remove the pid file and exit.
        """
        if self.pidfile is not None:
            try:
                os.remove(self.pidfile)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                pass
        self.exitfunc(signum, frame)
        sys.exit(0)

    def switchuser(self, user, group):
        """
        Switch the effective user and group. If <arg>user</arg> is <lit>None</lit>
        and <arg>group</arg> is nothing will be done. <arg>user</arg> and <arg>group</arg>
        can be an <class>int</class> (i.e. a user/group id) or <class>str</class>
        (a user/group name).
        """
        if group is not None:
            if isinstance(group, basestring):
                group = grp.getgrnam(group).gr_gid
            os.setegid(group)
        if user is not None:
            if isinstance(user, basestring):
                user = pwd.getpwnam(user).pw_uid
            os.seteuid(user)
            if "HOME" in os.environ:
                os.environ["HOME"] = pwd.getpwuid(user).pw_dir

    def start(self):
        """
        Daemonize the running script. When this method returns the process is
        completely decoupled from the parent environment.
        """
        try:
            pid = os.fork()
        except OSError, e:
            raise Exception, "%s [%d]" % (e.strerror, e.errno)

        if (pid == 0):    # The first child.
            # To become the session leader of this new session and the process group
            # leader of the new process group, we call os.setsid().  The process is
            # also guaranteed not to have a controlling terminal.
            os.setsid()

            try:
                # Fork a second child and exit immediately to prevent zombies.  This
                # causes the second child process to be orphaned, making the init
                # process responsible for its cleanup.  And, since the first child is
                # a session leader without a controlling terminal, it's possible for
                # it to acquire one by opening a terminal in the future (System V-
                # based systems).  This second fork guarantees that the child is no
                # longer a session leader, preventing the daemon from ever acquiring
                # a controlling terminal.
                pid = os.fork()    # Fork a second child.
            except OSError, e:
                raise Exception, "%s [%d]" % (e.strerror, e.errno)

            if (pid == 0):    # The second child.
                # Since the current working directory may be a mounted filesystem, we
                # avoid the issue of not being able to unmount the filesystem at
                # shutdown time by changing it to the root directory.
                os.chdir(WORKDIR)
                # We probably don't want the file mode creation mask inherited from
                # the parent, so we give the child complete control over permissions.
                os.umask(UMASK)
            else:
                # exit() or _exit()?  See below.
                os._exit(0)    # Exit parent (the first child) of the second child.
        else:
            # exit() or _exit()?
            # _exit is like exit(), but it doesn't call any functions registered
            # with atexit (and on_exit) or any registered signal handlers.  It also
            # closes any open file descriptors.  Using exit() may cause all stdio
            # streams to be flushed twice and any temporary files may be unexpectedly
            # removed.  It's therefore recommended that child branches of a fork()
            # and the parent branch(es) of a daemon use _exit().
            os._exit(0)    # Exit parent of the first child.

        # Switch user
        if (not self.user is None) and (not self.group is None):
            self.switchuser(self.user, self.group)

        # Redirect standard file descriptors (will belong to the new user)
        self.openstreams()

        # Write pid file (will belong to the new user)
        if self.pidfile is not None:
            open(self.pidfile, "wb").write(str(os.getpid()))

        # Reopen file descriptors on SIGHUP
        signal.signal(signal.SIGHUP, self.handlesighup)

        # Remove pid file and exit on SIGTERM
        signal.signal(signal.SIGTERM, self.handlesigterm)

    def stop(self):
        """
        Send a <lit>SIGTERM</lit> signal to a running daemon. The pid of the
        daemon will be read from the pidfile specified in the constructor.
        """
        if self.pidfile is None:
            sys.exit("no pidfile specified")
        try:
            pidfile = open(self.pidfile, "rb")
        except IOError, exc:
            sys.exit("can't open pidfile %s: %s" % (self.pidfile, str(exc)))
        data = pidfile.read()
        try:
            pid = int(data)
        except ValueError:
            sys.exit("mangled pidfile %s: %r" % (self.pidfile, data))
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            # process already disappeared -> ignore
            pass

    def service(self, args=None):
        """
        <par>Handle command line arguments and start or stop the daemon accordingly.</par>

        <par><arg>args</arg> must be a list of command line arguments (including the
        program name in <lit>args[0]</lit>). If <arg>args</arg> is <lit>None</lit>
        or unspecified <lit>sys.argv</lit> is used.</par>

        <par>The return value is true, if <option>start</option> has been specified
        as the command line argument, i.e. if the daemon should be started.</par>
        """
        if args is None:
            args = sys.argv
        if len(args) < 2 or args[1] not in ("start", "stop"):
            sys.exit("Usage: %s (start|stop)" % args[0])
        if args[1] == "start":
            self.start()
            return True
        else:
            self.stop()
            return False
