# Copyright (c) 2015-2016, NVIDIA CORPORATION. All rights reserved.
#
# SPDX-License-Identifier: GPL-2.0

# Logic to spawn a sub-process and interact with its stdio.

import os
import re
import pty
import signal
import select
import time

class Timeout(Exception):
    """An exception sub-class that indicates that a timeout occurred."""
    pass

class Spawn(object):
    """Represents the stdio of a freshly created sub-process. Commands may be
    sent to the process, and responses waited for.
    """

    def __init__(self, args):
        """Spawn (fork/exec) the sub-process.

        Args:
            args: array of processs arguments. argv[0] is the command to execute.

        Returns:
            Nothing.
        """

        self.waited = False
        self.buf = ''
        self.logfile_read = None
        self.before = ''
        self.after = ''
        self.timeout = None

        (self.pid, self.fd) = pty.fork()
        if self.pid == 0:
            try:
                # For some reason, SIGHUP is set to SIG_IGN at this point when
                # run under "go" (www.go.cd). Perhaps this happens under any
                # background (non-interactive) system?
                signal.signal(signal.SIGHUP, signal.SIG_DFL)
                os.execvp(args[0], args)
            except:
                print 'CHILD EXECEPTION:'
                import traceback
                traceback.print_exc()
            finally:
                os._exit(255)

        self.poll = select.poll()
        self.poll.register(self.fd, select.POLLIN | select.POLLPRI | select.POLLERR | select.POLLHUP | select.POLLNVAL)

    def kill(self, sig):
        """Send unix signal "sig" to the child process.

        Args:
            sig: The signal number to send.

        Returns:
            Nothing.
        """

        os.kill(self.pid, sig)

    def isalive(self):
        """Determine whether the child process is still running.

        Args:
            None.

        Returns:
            Boolean indicating whether process is alive.
        """

        if self.waited:
            return False

        w = os.waitpid(self.pid, os.WNOHANG)
        if w[0] == 0:
            return True

        self.waited = True
        return False

    def send(self, data):
        """Send data to the sub-process's stdin.

        Args:
            data: The data to send to the process.

        Returns:
            Nothing.
        """

        os.write(self.fd, data)

    def expect(self, patterns):
        """Wait for the sub-process to emit specific data.

        This function waits for the process to emit one pattern from the
        supplied list of patterns, or for a timeout to occur.

        Args:
            patterns: A list of strings or regex objects that we expect to
                see in the sub-process' stdout.

        Returns:
            The index within the patterns array of the pattern the process
            emitted.

        Notable exceptions:
            Timeout, if the process did not emit any of the patterns within
            the expected time.
        """

        for pi in xrange(len(patterns)):
            if type(patterns[pi]) == type(''):
                patterns[pi] = re.compile(patterns[pi])

        tstart_s = time.time()
        try:
            while True:
                earliest_m = None
                earliest_pi = None
                for pi in xrange(len(patterns)):
                    pattern = patterns[pi]
                    m = pattern.search(self.buf)
                    if not m:
                        continue
                    if earliest_m and m.start() >= earliest_m.start():
                        continue
                    earliest_m = m
                    earliest_pi = pi
                if earliest_m:
                    pos = earliest_m.start()
                    posafter = earliest_m.end() + 1
                    self.before = self.buf[:pos]
                    self.after = self.buf[pos:posafter]
                    self.buf = self.buf[posafter:]
                    return earliest_pi
                tnow_s = time.time()
                tdelta_ms = (tnow_s - tstart_s) * 1000
                if tdelta_ms > self.timeout:
                    raise Timeout()
                events = self.poll.poll(self.timeout - tdelta_ms)
                if not events:
                    raise Timeout()
                c = os.read(self.fd, 1024)
                if not c:
                    raise EOFError()
                if self.logfile_read:
                    self.logfile_read.write(c)
                self.buf += c
        finally:
            if self.logfile_read:
                self.logfile_read.flush()

    def close(self):
        """Close the stdio connection to the sub-process.

        This also waits a reasonable time for the sub-process to stop running.

        Args:
            None.

        Returns:
            Nothing.
        """

        os.close(self.fd)
        for i in xrange(100):
            if not self.isalive():
                break
            time.sleep(0.1)