%post
# We need to handle SELinux relabeling for a few reasons:
# - %post scripts that write files into places in /etc, but don't do
#   labeling correctly
# - Anaconda code that does the same (e.g. moving our log files into
#   /var/log/anaconda)
# - ostree payloads, where all of the labeling of /var is the installer's
#   responsibility (see https://github.com/ostreedev/ostree/pull/872 )
# - OSTree variants of the traditional mounts if present

RESCUE_MODE=/run/install/RESCUE_MODE

# Do not automatically modify files on the system being rescued.
if [ -e ${RESCUE_MODE} ]; then
    exit 0
fi

echo "Restoring SElinux contexts..."

restorecon -ir \
  /boot \
  /dev \
  /etc/ \
  /lib64 \
  /root \
  /usr/lib64 \
  /var/cache/yum \
  /var/home \
  /var/lib \
  /var/lock \
  /var/log \
  /var/media \
  /var/mnt \
  /var/opt \
  /var/roothome \
  /var/run \
  /var/spool \
  /var/srv \

echo "Finished."

%end
