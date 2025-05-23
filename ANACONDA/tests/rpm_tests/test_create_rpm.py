#
# Copyright (C) 2018  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#

import os

from tests.rpm_tests import RPMTestCase

# blivet-gui is supported on Fedora, but not ELN/CentOS/RHEL
HAVE_BLIVET_GUI = os.path.exists("/usr/bin/blivet-gui")

# list of source files which should be ignored in tests
IGNORED_SOURCE_FILES = []

if not HAVE_BLIVET_GUI:
    IGNORED_SOURCE_FILES.append("pyanaconda/ui/gui/spokes/blivet_gui.py")


class InstalledFilesTestCase(RPMTestCase):
    """Test if files in anaconda directory are correctly placed in the rpm files."""

    ANACONDA_BUS_CONF = "anaconda-bus.conf"
    ANACONDA_GENERATOR = "anaconda-generator"

    def test_pyanaconda_installed_files(self):
        rpms = self._apply_filters([RPMFilters.debug_exclude,
                                    RPMFilters.anaconda_widgets_exclude],
                                   self.rpm_paths)
        rpm_files = self._get_rpms_content(rpms)

        rpm_files = filter(FileFilters.site_packages_only, rpm_files)
        rpm_files = map(ModifyingFilters.remove_site_packages_prefix, rpm_files)

        rpm_files = filter(FileFilters.pycache_exclude, rpm_files)
        rpm_files = filter(FileFilters.pyc_exclude, rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.pyanaconda_only,
                FileFilters.pycache_exclude,
                FileFilters.pyc_exclude,
                FileFilters.no_extension_exlude,
                FileFilters.makefiles_exclude,
                FileFilters.isys_exclude,
                FileFilters.glade_files_exclude,
                FileFilters.text_files_exclude,
                FileFilters.src_ignore_exclude
            ], self._get_source_files()
        )

        src_files = map(ModifyingFilters.rename_dot_in_files, src_files)

        self._check_files_in_rpm(src_files, rpm_files)

    def test_dbus_conf_installed_files(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_dbus_confs_only, rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_dbus_only,
                FileFilters.confs_only,
                lambda f: FileFilters.specific_file_exclude(self.ANACONDA_BUS_CONF, f)
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_dbus_prefix,
                ModifyingFilters.apply_confs_prefix,
                ModifyingFilters.apply_dbus_prefix,
                ModifyingFilters.apply_share_anaconda_prefix
            ], src_files
        )

        self._check_files_in_rpm(src_files, rpm_files)

    def test_dbus_main_conf_file(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(lambda f: FileFilters.specific_file_only(self.ANACONDA_BUS_CONF, f),
                           rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_dbus_only,
                FileFilters.confs_only,
                lambda f: FileFilters.specific_file_only(self.ANACONDA_BUS_CONF, f)
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_dbus_prefix,
                ModifyingFilters.apply_dbus_prefix,
                ModifyingFilters.apply_share_anaconda_prefix
            ], src_files
        )

        self._check_files_in_rpm(src_files, rpm_files)

    def test_dbus_service_files(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_dbus_services_only, rpm_files)

        src_files = self._get_source_files()
        src_files = filter(FileFilters.src_dbus_only, src_files)
        src_files = filter(FileFilters.services_only, src_files)

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_dbus_prefix,
                ModifyingFilters.apply_services_prefix,
                ModifyingFilters.apply_dbus_prefix,
                ModifyingFilters.apply_share_anaconda_prefix
            ], src_files
        )

        self._check_files_in_rpm(src_files, rpm_files)

    def test_anaconda_conf_file(self):
        assert "data/anaconda.conf" in self._get_source_files()
        assert "/etc/anaconda/anaconda.conf" in self._get_core_rpm_content()

    def test_anaconda_conf_dir(self):
        rpm_files = self._get_core_rpm_content()
        rpm_files = filter(FileFilters.confd_only, rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_data_only,
                FileFilters.confd_only,
                FileFilters.confs_only,
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_prefix,
                lambda x: ModifyingFilters.apply_rpm_prefix("/etc/anaconda", x)
            ], src_files
        )

        self._check_files_in_rpm(src_files, rpm_files)

    def test_product_conf_dir(self):
        rpm_files = self._get_core_rpm_content()
        rpm_files = filter(FileFilters.productd_only, rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_data_only,
                FileFilters.productd_only,
                FileFilters.confs_only,
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_prefix,
                lambda x: ModifyingFilters.apply_rpm_prefix("/etc/anaconda", x)
            ], src_files
        )

        self._check_files_in_rpm(src_files, rpm_files)

    def test_anaconda_service_files(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_systemd_only, rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_systemd_only,
                FileFilters.makefiles_exclude,
                lambda f: FileFilters.specific_file_exclude(self.ANACONDA_GENERATOR, f)
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_systemd_prefix,
                lambda x: ModifyingFilters.apply_rpm_prefix("/usr/lib/systemd/system", x)
            ], src_files
        )

        self._check_files_in_rpm(src_files, rpm_files)

    def test_anaconda_service_generator_file(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_systemd_only, rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_systemd_only,
                FileFilters.makefiles_exclude,
                lambda f: FileFilters.specific_file_only(self.ANACONDA_GENERATOR, f)
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_systemd_prefix,
                lambda x: ModifyingFilters.apply_rpm_prefix("/usr/lib/systemd/system-generators",
                                                            x)
            ], src_files
        )

        self._check_files_in_rpm(src_files, rpm_files)

    def _check_files_in_rpm(self, src_files, rpm_files):
        src_files = self._check_and_return_as_list(src_files)
        rpm_files = self._check_and_return_as_list(rpm_files)

        for f in src_files:
            assert f in rpm_files, "File '{}' is not packaged in rpm".format(f)

    def _check_and_return_as_list(self, files_list):
        li = list(files_list)
        assert len(li) != 0, "No files to compare found!"

        return li

    def _get_source_files(self):
        ret = set()
        for root, _, files in os.walk(self.anaconda_root_path):
            files_with_path = self._join_relative_path_for_files(root, files)
            ret.update(files_with_path)

        return ret

    def _join_relative_path_for_files(self, root, files):
        out_files = set()
        new_root = os.path.relpath(root, self.anaconda_root_path)

        for f in files:
            new_path = os.path.join(new_root, f)
            out_files.add(new_path)

        return out_files

    def _get_core_rpm_content(self):
        rpms = filter(RPMFilters.debug_exclude, self.rpm_paths)
        rpms = filter(RPMFilters.anaconda_core_only, rpms)
        return self._get_rpms_content(rpms)

    def _get_rpms_content(self, rpms):
        content = set()

        for rpm in rpms:
            content.update(self._get_rpm_content(rpm))

        return content

    def _get_rpm_content(self, rpm):
        command = ["rpm", "-q", "-p", "-l", rpm]
        rpm_content = self.check_subprocess(command)

        return rpm_content.stdout.decode("utf-8").split('\n')

    @staticmethod
    def _apply_filters(filters, in_iter):
        for f in filters:
            in_iter = filter(f, in_iter)

        return in_iter

    @staticmethod
    def _apply_maps(maps, in_iter):
        for m in maps:
            in_iter = map(m, in_iter)

        return in_iter


class FileFilters(object):

    @staticmethod
    def makefiles_exclude(path):
        return "Makefile" not in path

    @staticmethod
    def isys_exclude(path):
        return "/isys/" not in path

    @staticmethod
    def pycache_exclude(path):
        return "__pycache__" not in path

    @staticmethod
    def pyc_exclude(path):
        return not path.endswith('.pyc')

    @staticmethod
    def pyanaconda_only(path):
        return "pyanaconda/" in path

    @staticmethod
    def site_packages_only(path):
        return "site-packages" in path

    @staticmethod
    def glade_files_exclude(path):
        return not path.endswith(".glade")

    @staticmethod
    def no_extension_exlude(path):
        return "." in path

    @staticmethod
    def text_files_exclude(path):
        return not path.endswith(".rst")

    @staticmethod
    def rpm_dbus_confs_only(path):
        return "/dbus" in path and path.endswith(".conf")

    @staticmethod
    def rpm_dbus_services_only(path):
        return "/dbus" in path and path.endswith(".service")

    @staticmethod
    def src_dbus_only(path):
        return "data/dbus" in path

    @staticmethod
    def confd_only(path):
        return "/conf.d/" in path

    @staticmethod
    def productd_only(path):
        return "/product.d/" in path

    @staticmethod
    def confs_only(path):
        return path.endswith(".conf")

    @staticmethod
    def services_only(path):
        return path.endswith(".service")

    @staticmethod
    def rpm_systemd_only(path):
        return "/systemd/system" in path

    @staticmethod
    def src_systemd_only(path):
        return "systemd/" in path

    @staticmethod
    def src_data_only(path):
        return "data/" in path

    @staticmethod
    def specific_file_only(name, path):
        return path.endswith(name)

    @staticmethod
    def specific_file_exclude(name, path):
        return not FileFilters.specific_file_only(name, path)

    @staticmethod
    def src_ignore_exclude(path):
        return path not in IGNORED_SOURCE_FILES


class RPMFilters(object):

    @staticmethod
    def debug_exclude(rpm):
        return "debug" not in rpm

    @staticmethod
    def anaconda_widgets_exclude(rpm):
        return "anaconda-widgets" not in rpm

    @staticmethod
    def anaconda_core_only(rpm):
        # includes debug package
        return "anaconda-core" in rpm


class ModifyingFilters(object):

    @staticmethod
    def rename_dot_in_files(path):
        if path.endswith(".in"):
            return path[:-3]

        return path

    @staticmethod
    def remove_site_packages_prefix(path):
        if FileFilters.site_packages_only(path):
            _, suffix = path.split("site-packages/")
            return suffix

        return path

    @staticmethod
    def remove_prefix(prefix, path):
        if path.startswith(prefix):
            return path[len(prefix):]

        return path

    @staticmethod
    def remove_data_prefix(path):
        return ModifyingFilters.remove_prefix("data/", path)

    @staticmethod
    def remove_data_dbus_prefix(path):
        return ModifyingFilters.remove_prefix("data/dbus/", path)

    @staticmethod
    def remove_data_systemd_prefix(path):
        return ModifyingFilters.remove_prefix("data/systemd/", path)

    @staticmethod
    def apply_rpm_prefix(prefix, path):
        return os.path.join(prefix, path)

    @staticmethod
    def apply_share_anaconda_prefix(path):
        return ModifyingFilters.apply_rpm_prefix("/usr/share/anaconda/", path)

    @staticmethod
    def apply_confs_prefix(path):
        return ModifyingFilters.apply_rpm_prefix("confs/", path)

    @staticmethod
    def apply_services_prefix(path):
        return ModifyingFilters.apply_rpm_prefix("services/", path)

    @staticmethod
    def apply_dbus_prefix(path):
        return ModifyingFilters.apply_rpm_prefix("dbus/", path)
