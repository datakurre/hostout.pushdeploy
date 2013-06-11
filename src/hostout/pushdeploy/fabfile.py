# -*- coding: utf-8 -*
"""Fabfile for hostout.pushdeploy to describe all the magic
"""

import os

from zc.buildout.buildout import Buildout

from fabric.state import (
    env,
    output
)

from fabric.network import (
    normalize,
    key_filenames
)

from fabric.operations import (
    run,
    sudo,
    local
)

from fabric.context_managers import (
    lcd,
    settings
)


def rsync(from_path, to_path, reverse=False,
          exclude=(), delete=False, extra_opts="",
          ssh_opts="", capture=False):
    """Performs rsync from some remote location to some local location.
    Optionally does exactly the reverse (syncs from some local location
    to some remote location)."""

    # Adapted from:
    # https://github.com/fabric/fabric/blob/master/fabric/contrib/project.py

    # Create --exclude options from exclude list
    exclude_opts = ' --exclude "%s"' * len(exclude)

    # Double-backslash-escape
    exclusions = tuple([str(s).replace('"', '\\\\"') for s in exclude])

    # Honor SSH key(s)
    key_string = ""
    keys = key_filenames()
    if keys:
        key_string = "-i " + " -i ".join(keys)

    # Port
    user, host, port = normalize(env.host_string)
    if host.startswith('@'):
        host = host[1:]
    port_string = "-p %s" % port

    # RSH
    rsh_string = ""
    rsh_parts = [key_string, port_string, ssh_opts]
    if any(rsh_parts):
        rsh_string = "--rsh='ssh %s'" % " ".join(rsh_parts)

    # Set remote sudo
    if env.hostout.options.get('remote-sudo') == "true":
        remote_sudo = ' --rsync-path="sudo rsync"'
        extra_opts = (extra_opts + remote_sudo).strip()

    # Set up options part of string
    options_map = {
        'delete': "--delete" if delete else "",
        'exclude': exclude_opts % exclusions,
        'rsh': rsh_string,
        'extra': extra_opts
    }

    options = ("%(delete)s%(exclude)s -pthlrz "
               "%(extra)s %(rsh)s") % options_map

    # Interpret direction and define command
    if not reverse:
        cmd = "rsync %s %s@%s:%s %s" % (options, user, host,
                                        from_path, to_path)
    else:
        cmd = "rsync %s %s %s@%s:%s" % (options, to_path,
                                        user, host, from_path)

    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] rsync: %s" % cmd)
    return local(cmd, capture=capture)


def clone(repository, branch=None):
    """Clone a new local buildout from a mercurial repository.
    """

    hostout_path = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert hostout_path, u'No path found for the selected hostout'

    # Clone
    branch = branch and ' -r {0:s}'.format(branch) or ''
    cmd = 'hg clone {0:s}{1:s} {2:s}'.format(repository, branch, hostout_path)
    cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] clone: {0:s}'.format(cmd))
    local(cmd)


def update(branch=None):
    """Update the local buildout from its mercurial repository.
    """

    hostout_path = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert hostout_path, u'No path found for the selected hostout'

    # Pull
    with lcd(hostout_path):
        cmd = 'hg pull'
        cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
        if local_sudo:
            cmd = 'sudo {0:s}'.format(cmd)
        if output.running:
            print('[localhost] update: {0:s}'.format(cmd))
        local(cmd)

    # Update
    branch = bool(branch) and ' {0:s}'.format(branch) or ''
    with lcd(hostout_path):
        cmd = 'hg update -C{0:s}'.format(branch)
        cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
        if env.hostout.options.get('local-sudo') == 'true':
            cmd = 'sudo {0:s}'.format(cmd)
        if output.running:
            print('[localhost] update: {0:s}'.format(cmd))
        local(cmd)


def bootstrap():
    """Execute bootstrap for the local buildout.

    The default effective python could be overridden by setting
    ``bootstrap-python`` -hostout-option with a path to an another python
    executable.

    """
    hostout_path = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert hostout_path, u'No path found for the selected hostout'

    buildout_python = env.hostout.options.get('executable')
    bootstrap_python = (
        env.hostout.options.get('bootstrap-python') or buildout_python
    )

    # Bootstrap
    with lcd(hostout_path):
        cmd = '{0:s} bootstrap.py --distribute'.format(bootstrap_python)
        cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
        if local_sudo:
            cmd = 'sudo {0:s}'.format(cmd)
        if output.running:
            print('[localhost] bootstrap: %s' % cmd)

        with settings(warn_only=True):
            res = local(cmd)
            if res.failed:
                print('First bootstrap failed: we have a new bootstrap which '
                      'has --distribute option now default. Trying again...')
                cmd = '{0:s} bootstrap.py'.format(bootstrap_python)
                cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
                if local_sudo:
                    cmd = 'sudo {0:s}'.format(cmd)
                if output.running:
                    print('[localhost] bootstrap: %s' % cmd)
                local(cmd)


def annotate():
    """Read buildout configuration and returns 'buildout' section as a dict."""

    buildout = Buildout("%s/%s" % (env.hostout.options['path'],
                                   env.hostout.options['buildout']), [])
    return buildout.get('buildout')


def buildout(*args):
    """Executes the local buildout and chowns it for the effective user."""

    buildout_directory = env.hostout.options['path']
    effective_user = env.hostout.options.get('effective-user', "root")

    # Configure
    offline = "-o" in args and " -o" or ""
    parts = filter(lambda x: not x.startswith("-"), args)
    parts = parts and " install %s" % " ".join(parts) or ""

    # Buildout
    with lcd(buildout_directory):
        cmd = "bin/buildout%s%s" % (parts, offline)
        if env.hostout.options.get('local-sudo') == "true":
            cmd = "sudo %s" % cmd
        elif env.hostout.options.get('buildout-user'):
            cmd = "su %s -c '%s'" % (env.hostout.options.get('buildout-user'),
                                     cmd)
        if output.running:
            print("[localhost] buildout: %s" % cmd)
        local(cmd)

    # Chown
    annotations = annotate()
    bin_directory = os.path.join(buildout_directory,
                                 annotations['bin-directory'])
    eggs_directory = os.path.join(buildout_directory,
                                  annotations['eggs-directory'])
    parts_directory = os.path.join(buildout_directory,
                                   annotations['parts-directory'])

    chown_directorys = [bin_directory, parts_directory, eggs_directory]

    for folder in chown_directorys:
        cmd = "chown -R %s %s" % (effective_user, folder)

        if env.hostout.options.get('local-sudo') == "true":
            cmd = "sudo %s" % cmd
        if output.running:
            print("[localhost] buildout: %s" % cmd)
        local(cmd)

    # Chown "etc" (created by some buildout scripts)
    etc_directory = os.path.join(buildout_directory, "etc")
    if os.path.exists(etc_directory):
        cmd = "chown -R %s %s" % (effective_user, etc_directory)
        if env.hostout.options.get('local-sudo') == "true":
            cmd = "sudo %s" % cmd
        if output.running:
            print("[localhost] buildout: %s" % cmd)
        local(cmd)


def pull():
    """Pulls the data from the remote site into the local buildout."""

    var_directory = os.path.join(env.hostout.options['path'], "var")
    effective_user = env.hostout.options.get('effective-user',
                                             env.user or "root")

    # Create filestorage
    if not os.path.exists(os.path.join(var_directory, 'filestorage')):
        cmd = "mkdir -p %s" % os.path.join(var_directory, 'filestorage')
        if env.hostout.options.get('local-sudo') == "true":
            cmd = "sudo %s" % cmd
        if output.running:
            print("[localhost] pull: %s" % cmd)
        local(cmd)

    # Pull filestorage
    rsync(os.path.join(var_directory, "filestorage", "Data.fs"),
          os.path.join(var_directory, "filestorage", "Data.fs"),
          delete=True)

    # Pull blobstorage
    rsync(os.path.join(var_directory, "blobstorage"),
          var_directory,
          delete=True)

    # Chown
    cmd = "chown -R %s %s" % (effective_user, var_directory)
    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] pull: %s" % cmd)
    local(cmd)


def restart():
    """Restarts the local buildout. The restart command must be defined
    by setting a hostout-option ``restart``."""

    # Restart
    cmd = env.hostout.options['restart']
    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] restart: %s" % cmd)
    local(cmd)


def stage():
    """Updates the local staged buildout"""

    # Pull
    pull()

    # Update
    update()

    # Bootstrap
    bootstrap()

    # Buildout
    buildout()

    # Restart
    # restart()


def cook_resources():
    """Cook plone resources on remote."""
    annotations = annotate()
    buildoutname = annotations['buildoutname']

    buildout_directory = env.hostout.options["path"]

    res = sudo("%s/bin/instance -O %s run `which resourcecooker.py`" %
               (buildout_directory, buildoutname), warn_only=True)
    if res.failed:
        res = sudo("%s/bin/instance1 -O %s run `which resourcecooker.py`" %
                   (buildout_directory, buildoutname), warn_only=True)


def push():
    """Pushes the local buildout results (without data) to the remote site."""

    buildout_directory = env.hostout.options["path"]
    effective_user = env.hostout.options.get('effective-user',
                                             env.user or "root")

    # Make sure that the buildout directory exists on the remote
    if env.hostout.options.get('remote-sudo') == "true":
        sudo("mkdir -p %s" % buildout_directory)
        sudo("chown %s %s" % (effective_user, buildout_directory))
    else:
        run("mkdir -p %s" % buildout_directory)
        run("chown %s %s" % (effective_user, buildout_directory))

    # Push
    annotations = annotate()

    bin_directory = os.path.join(buildout_directory,
                                 annotations['bin-directory'])
    eggs_directory = os.path.join(buildout_directory,
                                  annotations['eggs-directory'])
    parts_directory = os.path.join(buildout_directory,
                                   annotations['parts-directory'])

    products_directory = os.path.join(buildout_directory, 'products')

    var_directory = os.path.join(buildout_directory, 'var')

    chown_directorys = [bin_directory, parts_directory, eggs_directory,
                        var_directory]

    rsync(bin_directory,
          os.path.join(bin_directory, "*"),
          reverse=True, delete=False)

    rsync(eggs_directory,
          os.path.join(eggs_directory, "*"),
          reverse=True, delete=False)

    rsync(parts_directory,
          os.path.join(parts_directory, "*"),
          reverse=True, delete=False)

    if os.path.isdir(products_directory):
        chown_directorys.append(products_directory)
        rsync(products_directory,
              os.path.join(products_directory, "*"),
              reverse=True, delete=False)

    rsync(var_directory,
          os.path.join(var_directory, "*"),
          reverse=True, delete=False,
          exclude=('blobstorage*', '*.fs', '*.old', '*.zip', '*.log',
                   '*.backup'),
          extra_opts='--ignore-existing')

    for folder in chown_directorys:
        cmd = "chown -R %s %s" % (effective_user, folder)

        if env.hostout.options.get('remote-sudo') == "true":
            sudo(cmd)
        else:
            run(cmd)

    # Push "etc" (created by some buildout scripts)
    etc_directory = os.path.join(buildout_directory, "etc")
    if os.path.exists(etc_directory):
        rsync(etc_directory,
              os.path.join(etc_directory, "*"),
              reverse=True, delete=False)

    # Chown
    if os.path.exists(etc_directory):
        if env.hostout.options.get('remote-sudo') == "true":
            sudo("chown -R %s %s" % (effective_user, etc_directory))
        else:
            run("chown -R %s %s" % (effective_user, etc_directory))


def deploy_etc():
    """Copies system config from parts/system/etc to /etc."""

    buildout_directory = env.hostout.options["path"]
    annotations = annotate()
    parts_directory = os.path.join(buildout_directory,
                                   annotations['parts-directory'])

    if os.path.isdir("%s/system/etc" % parts_directory):
        cmd = "cp -R %s /etc;supervisorctl reread;supervisorctl update" % \
              (parts_directory + '/system/etc/*')

        if env.hostout.options.get('remote-sudo') == "true":
            sudo(cmd)
        else:
            run(cmd)


def stop(site):
    """Stop the remote site."""
    sudo("supervisorctl stop %s:*" % site)


def start(site):
    """Start the remote site."""
    sudo("supervisorctl start %s:*" % site)


def site_restart(site):
    """Restart the remote site."""
    sudo("supervisorctl restart %s:*" % site)


def deploy():
    """Deploys the local buildout to the remote site."""

    # Push the code
    push()
    deploy_etc()

    # Restart the site
    if env.hostout.options.get('remote-sudo') == "true":
        sudo(env.hostout.options['restart'])
    else:
        run(env.hostout.options['restart'])


def stage_supervisor():
    """Updates the local supervisor configuration. Supervisord configuration
    path must be defined by setting a hostout-option ``supervisor-conf``."""

    supervisor_conf = env.hostout.options['supervisor-conf']

    # Configure
    annotations = annotate()
    parts_directory = annotations['parts-directory']

    cmd = "cp %s %s" \
          % (os.path.join(parts_directory, os.path.basename(supervisor_conf)),
             supervisor_conf)
    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] stage_supervisor: %s" % cmd)
    local(cmd)

    # Update
    cmd = "supervisorctl update"
    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] stage_supervisor: %s" % cmd)
    local(cmd)


def deploy_supervisor():
    """Updates the remote supervisor configuration. Supervisord configuration
    path must be defined by setting a hostout-option ``supervisor-conf``."""

    supervisor_conf = env.hostout.options['supervisor-conf']

    # Sync
    annotations = annotate()
    parts_directory = annotations['parts-directory']

    rsync(supervisor_conf,
          os.path.join(parts_directory,
                       os.path.basename(supervisor_conf)),
          reverse=True, delete=False)

    # Update
    if env.hostout.options.get('remote-sudo') == "true":
        sudo("supervisorctl update")
    else:
        run("supervisorctl update")
