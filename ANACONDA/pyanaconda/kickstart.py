#
# kickstart.py: kickstart install support
#
# Copyright (C) 1999-2016
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import glob
import os
import os.path
import shlex
import sys
import tempfile
import time
import warnings

from contextlib import contextmanager

from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.kickstart import VERSION, commands as COMMANDS
from pyanaconda.core.kickstart.specification import KickstartSpecification
from pyanaconda.core.constants import IPMI_ABORTED
from pyanaconda.errors import ScriptError, errorHandler
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.structures.kickstart import KickstartReport
from pyanaconda.pwpolicy import F34_PwPolicy, F34_PwPolicyData

from pykickstart.base import BaseHandler, KickstartCommand, RemovedCommand
from pykickstart.constants import KS_SCRIPT_POST, KS_SCRIPT_PRE, KS_SCRIPT_TRACEBACK, KS_SCRIPT_PREINSTALL
from pykickstart.errors import KickstartError, KickstartParseWarning, KickstartDeprecationWarning
from pykickstart.ko import KickstartObject
from pykickstart.parser import KickstartParser
from pykickstart.parser import Script as KSScript
from pykickstart.sections import NullSection, PostScriptSection, PreScriptSection, \
    PreInstallScriptSection, OnErrorScriptSection, TracebackScriptSection, Section
from pykickstart.version import returnClassForVersion

log = get_module_logger(__name__)
stdoutLog = get_stdout_logger()

# kickstart parsing and kickstart script
script_log = log.getChild("script")
parsing_log = log.getChild("parsing")


@contextmanager
def check_kickstart_error():
    try:
        yield
    except KickstartError as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        print(e)
        util.ipmi_report(IPMI_ABORTED)
        sys.exit(1)


class AnacondaKSScript(KSScript):
    """ Execute a kickstart script

        This will write the script to a file named /tmp/ks-script- before
        execution.
        Output is logged by the program logger, the path specified by --log
        or to /tmp/ks-script-\\*.log
    """
    def run(self, chroot):
        """ Run the kickstart script
            @param chroot directory path to chroot into before execution
        """
        if self.inChroot:
            scriptRoot = chroot
        else:
            scriptRoot = "/"

        (fd, path) = tempfile.mkstemp("", "ks-script-", scriptRoot + "/tmp")

        os.write(fd, self.script.encode("utf-8"))
        os.close(fd)
        os.chmod(path, 0o700)

        # Always log stdout/stderr from scripts.  Using --log just lets you
        # pick where it goes.  The script will also be logged to program.log
        # because of execWithRedirect.
        if self.logfile:
            if self.inChroot:
                messages = "%s/%s" % (scriptRoot, self.logfile)
            else:
                messages = self.logfile

            d = os.path.dirname(messages)
            if not os.path.exists(d):
                os.makedirs(d)
        else:
            # Always log outside the chroot, we copy those logs into the
            # chroot later.
            messages = "/tmp/%s.log" % os.path.basename(path)

        with util.open_with_perm(messages, "w", 0o600) as fp:
            rc = util.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                       stdout=fp,
                                       root=scriptRoot)

        if rc != 0:
            script_log.error("Error code %s running the kickstart script at line %s", rc, self.lineno)
            if self.errorOnFail:
                err = ""
                with open(messages, "r") as fp:
                    err = "".join(fp.readlines())

                # Show error dialog even for non-interactive
                flags.ksprompt = True

                errorHandler.cb(ScriptError(self.lineno, err))
                util.ipmi_report(IPMI_ABORTED)
                sys.exit(0)


class AnacondaInternalScript(AnacondaKSScript):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hidden = True

    def __str__(self):
        # Scripts that implement portions of anaconda (copying screenshots and
        # log files, setfilecons, etc.) should not be written to the output
        # kickstart file.
        return ""


###
### SUBCLASSES OF PYKICKSTART COMMAND HANDLERS
###

class UselessSection(Section):
    """Kickstart section that was moved on DBus and doesn't do anything."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sectionOpen = kwargs.get("sectionOpen")


class UselessCommand(KickstartCommand):
    """Kickstart command that was moved on DBus and doesn't do anything.

    Use this class to override the pykickstart command in our command map,
    when we don't want the command to do anything.
    """

    def __str__(self):
        """Generate this part of a kickstart file from the DBus module."""
        return ""

    def parse(self, args):
        """Do not parse anything.

        We can keep this method for the checks if it is possible, but
        it shouldn't parse anything.
        """
        log.warning("Command %s will be parsed in DBus module.", self.currentCmd)


class UselessObject(KickstartObject):
    """Kickstart object that was moved on DBus and doesn't do anything."""

    def __str__(self):
        """Generate this part of a kickstart file from the DBus module."""
        return ""


class RepoData(COMMANDS.RepoData):

    __mount_counter = 0

    def __init__(self, *args, **kwargs):
        """ Add enabled kwarg

            :param enabled: The repo has been enabled
            :type enabled: bool
        """
        self.enabled = kwargs.pop("enabled", True)
        self.repo_id = kwargs.pop("repo_id", None)
        self.treeinfo_origin = kwargs.pop("treeinfo_origin", False)
        self.partition = kwargs.pop("partition", None)
        self.iso_path = kwargs.pop("iso_path", None)

        self.mount_dir_suffix = kwargs.pop("mount_dir_suffix", None)

        super().__init__(*args, **kwargs)

    @classmethod
    def create_copy(cls, other):
        return cls(name=other.name,
                   baseurl=other.baseurl,
                   mirrorlist=other.mirrorlist,
                   metalink=other.metalink,
                   proxy=other.proxy,
                   enabled=other.enabled,
                   treeinfo_origin=other.treeinfo_origin,
                   partition=other.partition,
                   iso_path=other.iso_path,
                   mount_dir_suffix=other.mount_dir_suffix)

    def generate_mount_dir(self):
        """Generate persistent mount directory suffix

        This is valid only for HD repositories
        """
        if self.is_harddrive_based() and self.mount_dir_suffix is None:
            self.mount_dir_suffix = "addition_" + self._generate_mount_dir_suffix()

    @classmethod
    def _generate_mount_dir_suffix(cls):
        suffix = str(cls.__mount_counter)
        cls.__mount_counter += 1
        return suffix

    def __str__(self):
        """Don't output disabled repos"""
        if self.enabled:
            return super().__str__()
        else:
            return ''

    def is_harddrive_based(self):
        return self.partition is not None


###
### %anaconda Section
###
class AnacondaSectionHandler(BaseHandler):
    """A handler for only the anaconda section's commands."""
    commandMap = {
        "pwpolicy": F34_PwPolicy
    }

    dataMap = {
        "PwPolicyData": F34_PwPolicyData
    }

    def __init__(self):
        super().__init__(mapping=self.commandMap, dataMapping=self.dataMap)

    def __str__(self):
        """Return the %anaconda section"""
        retval = ""
        # This dictionary should only be modified during __init__, so if it
        # changes during iteration something has gone horribly wrong.
        lst = sorted(self._writeOrder.keys())
        for prio in lst:
            for obj in self._writeOrder[prio]:
                retval += str(obj)

        if retval:
            retval = "\n%anaconda\n" + retval + "%end\n"
        return retval


class AnacondaSection(Section):
    """A section for anaconda specific commands."""
    sectionOpen = "%anaconda"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmdno = 0

    def handleLine(self, line):
        if not self.handler:
            return

        self.cmdno += 1
        args = shlex.split(line, comments=True)
        self.handler.currentCmd = args[0]
        self.handler.currentLine = self.cmdno
        return self.handler.dispatcher(args, self.cmdno)

    def handleHeader(self, lineno, args):
        """Process the arguments to the %anaconda header."""
        Section.handleHeader(self, lineno, args)

        warnings.warn(_(
            "The %%anaconda section has been deprecated. It "
            "may be removed from future releases, which will "
            "result in a fatal error when it is encountered. "
            "Please modify your kickstart file to remove this "
            "section."
        ), KickstartDeprecationWarning)

    def finalize(self):
        """Let %anaconda know no additional data will come."""
        Section.finalize(self)


###
### HANDLERS
###

# This is just the latest entry from pykickstart.handlers.control with all the
# classes we're overriding in place of the defaults.
class AnacondaKickstartSpecification(KickstartSpecification):
    """The kickstart specification of the main process."""

    commands = {
        "autostep": COMMANDS.AutoStep,
        "cmdline": COMMANDS.DisplayMode,
        "driverdisk": COMMANDS.DriverDisk,
        "module": COMMANDS.Module,
        "eula": COMMANDS.Eula,
        "graphical": COMMANDS.DisplayMode,
        "halt": COMMANDS.Reboot,
        "liveimg": COMMANDS.Liveimg,
        "logging": COMMANDS.Logging,
        "mediacheck": COMMANDS.MediaCheck,
        "method": COMMANDS.Method,
        "poweroff": COMMANDS.Reboot,
        "reboot": COMMANDS.Reboot,
        "repo": COMMANDS.Repo,
        "rescue": COMMANDS.Rescue,
        "shutdown": COMMANDS.Reboot,
        "sshpw": COMMANDS.SshPw,
        "text": COMMANDS.DisplayMode,
        "updates": COMMANDS.Updates,
        "vnc": COMMANDS.Vnc,
    }

    commands_data = {
        "DriverDiskData": COMMANDS.DriverDiskData,
        "ModuleData": COMMANDS.ModuleData,
        "RepoData": RepoData,
        "SshPwData": COMMANDS.SshPwData,
    }

    @classmethod
    def generate_command_map(cls, handler):
        """Generate a command map.

        :param handler: a kickstart handler
        :return: a map of command overrides
        """
        command_map = dict(cls.commands)

        for name, command in handler.commandMap.items():
            # Ignore removed commands.
            if issubclass(command, RemovedCommand):
                continue

            # Mark unspecified commands as useless.
            if name not in command_map:
                command_map[name] = UselessCommand

        return command_map

    @classmethod
    def generate_data_map(cls, handler):
        """Generate a data map.

        :param handler: a kickstart handler
        :return: a map of data overrides
        """
        return dict(cls.commands_data)


# Get the kickstart handler for the specified version.
superclass = returnClassForVersion(VERSION)

# Generate the command and data overrides.
specification = AnacondaKickstartSpecification
commandMap = specification.generate_command_map(superclass)
dataMap = specification.generate_data_map(superclass)


class AnacondaKSHandler(superclass):

    def __init__(self, commandUpdates=None, dataUpdates=None):
        if commandUpdates is None:
            commandUpdates = commandMap

        if dataUpdates is None:
            dataUpdates = dataMap

        super().__init__(commandUpdates=commandUpdates, dataUpdates=dataUpdates)
        self.onPart = {}

        # The %anaconda section uses its own handler for a limited set of commands
        self.anaconda = AnacondaSectionHandler()

        # The %packages section is handled by the DBus module.
        self.packages = UselessObject()

    def __str__(self):
        proxy = BOSS.get_proxy()
        modules = proxy.GenerateKickstart().strip()
        return super().__str__() + "\n" + modules + "\n\n" + str(self.anaconda)


class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
    def __init__(self, handler, followIncludes=True, errorsAreFatal=True,
                 missingIncludeIsFatal=True):
        super().__init__(handler, missingIncludeIsFatal=False)

    def handleCommand(self, lineno, args):
        pass

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=AnacondaKSScript))
        self.registerSection(NullSection(self.handler, sectionOpen="%pre-install"))
        self.registerSection(NullSection(self.handler, sectionOpen="%post"))
        self.registerSection(NullSection(self.handler, sectionOpen="%onerror"))
        self.registerSection(NullSection(self.handler, sectionOpen="%traceback"))
        self.registerSection(NullSection(self.handler, sectionOpen="%packages"))
        self.registerSection(NullSection(self.handler, sectionOpen="%addon"))
        self.registerSection(NullSection(self.handler, sectionOpen="%certificate"))
        self.registerSection(NullSection(self.handler.anaconda, sectionOpen="%anaconda"))


class AnacondaKSParser(KickstartParser):
    def __init__(self, handler, followIncludes=True, errorsAreFatal=True,
                 missingIncludeIsFatal=True, scriptClass=AnacondaKSScript):
        self.scriptClass = scriptClass
        super().__init__(handler)

    def handleCommand(self, lineno, args):
        if not self.handler:
            return

        return KickstartParser.handleCommand(self, lineno, args)

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PreInstallScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PostScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(TracebackScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(OnErrorScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(UselessSection(self.handler, sectionOpen="%packages"))
        self.registerSection(UselessSection(self.handler, sectionOpen="%addon"))
        self.registerSection(UselessSection(self.handler, sectionOpen="%certificate"))
        self.registerSection(AnacondaSection(self.handler.anaconda))


def preScriptPass(f):
    # The first pass through kickstart file processing - look for %pre scripts
    # and run them.  This must come in a separate pass in case a script
    # generates an included file that has commands for later.
    ksparser = AnacondaPreParser(AnacondaKSHandler())

    with check_kickstart_error():
        ksparser.readKickstart(f)

    # run %pre scripts
    runPreScripts(ksparser.handler.scripts)


def parseKickstart(handler, f, strict_mode=False, pass_to_boss=False):
    # preprocessing the kickstart file has already been handled in initramfs.

    ksparser = AnacondaKSParser(handler)
    kswarnings = []
    showwarning = warnings.showwarning

    def ksshowwarning(message, category, filename, lineno, file=None, line=None):
        # Print the warning with default function.
        showwarning(message, category, filename, lineno, file, line)
        # Collect pykickstart warnings.
        if issubclass(category, KickstartParseWarning):
            kswarnings.append(message)

    try:
        # Process warnings differently in this part.
        with warnings.catch_warnings():

            # Set up the warnings module.
            warnings.showwarning = ksshowwarning
            warnings.simplefilter("always", category=KickstartParseWarning)

            # Parse the kickstart file in DBus modules.
            if pass_to_boss:
                boss = BOSS.get_proxy()
                report = KickstartReport.from_structure(
                    boss.ReadKickstartFile(f)
                )
                for warn in report.warning_messages:
                    warnings.warn(warn.message, KickstartParseWarning)
                if not report.is_valid():
                    message = "\n\n".join(map(str, report.error_messages))
                    raise KickstartError(message)

            # Parse the kickstart file in anaconda.
            ksparser.readKickstart(f)

            # Print kickstart warnings and error out if in strict mode
            if kswarnings:
                print(_("\nSome warnings occurred during reading the kickstart file:"))
                for w in kswarnings:
                    print(str(w).strip())
                if strict_mode:
                    raise KickstartError("Please modify your kickstart file to fix the warnings "
                                         "or remove the `ksstrict` option.")

    except KickstartError as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        parsing_log.error(e)

        # Print an error and terminate.
        print(_("\nAn error occurred during reading the kickstart file:"
                "\n%s\n\nThe installer will now terminate.") % str(e).strip())

        util.ipmi_report(IPMI_ABORTED)
        time.sleep(10)
        sys.exit(1)


def appendPostScripts(ksdata):
    scripts = ""

    # Read in all the post script snippets to a single big string.
    for fn in sorted(glob.glob("/usr/share/anaconda/post-scripts/*ks")):
        f = open(fn, "r")
        scripts += f.read()
        f.close()

    # Then parse the snippets against the existing ksdata.  We can do this
    # because pykickstart allows multiple parses to save their data into a
    # single data object.  Errors parsing the scripts are a bug in anaconda,
    # so just raise an exception.
    ksparser = AnacondaKSParser(ksdata, scriptClass=AnacondaInternalScript)
    ksparser.readKickstartFromString(scripts, reset=False)


def runPostScripts(scripts):
    postScripts = [s for s in scripts if s.type == KS_SCRIPT_POST]

    if len(postScripts) == 0:
        return

    script_log.info("Running kickstart %%post script(s)")
    for script in postScripts:
        script.run(conf.target.system_root)
    script_log.info("All kickstart %%post script(s) have been run")


def runPreScripts(scripts):
    preScripts = [s for s in scripts if s.type == KS_SCRIPT_PRE]

    if len(preScripts) == 0:
        return

    script_log.info("Running kickstart %%pre script(s)")
    stdoutLog.info(_("Running pre-installation scripts"))

    for script in preScripts:
        script.run("/")

    script_log.info("All kickstart %%pre script(s) have been run")


def runPreInstallScripts(scripts):
    preInstallScripts = [s for s in scripts if s.type == KS_SCRIPT_PREINSTALL]

    if len(preInstallScripts) == 0:
        return

    script_log.info("Running kickstart %%pre-install script(s)")

    for script in preInstallScripts:
        script.run("/")

    script_log.info("All kickstart %%pre-install script(s) have been run")


def runTracebackScripts(scripts):
    script_log.info("Running kickstart %%traceback script(s)")
    for script in filter(lambda s: s.type == KS_SCRIPT_TRACEBACK, scripts):
        script.run("/")
    script_log.info("All kickstart %%traceback script(s) have been run")
