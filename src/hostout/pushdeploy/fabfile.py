# -*- coding: utf-8 -*-
"""Fabfile for hostout.pushdeploy to describe all the magic."""

import re
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

from fabric.context_managers import lcd


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

    options = ("%(delete)s%(exclude)s --progress -pthlrvz "
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
    """Clones a new local buildout from a mercurial repository."""

    path = env.hostout.options['path']
    effective_user = env.hostout.options.get('effective-user',
                                             env.user or 'root')

    # Clone
    branch = branch and " -r %s" % branch or ""
    cmd = "hg clone %s%s %s" % (repository, branch, path)
    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] clone: %s" % cmd)
    local(cmd)

    # Chown
    cmd = "chown %s %s" % (effective_user, path)
    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] clone: %s" % cmd)
    local(cmd)


def update(branch=None):
    """Updates the local buildout from its mercurial repository."""

    # Pull
    with lcd(env.hostout.options['path']):
        cmd = "hg pull"
        if env.hostout.options.get('local-sudo') == "true":
            cmd = "sudo %s" % cmd
        if output.running:
            print("[localhost] update: %s" % cmd)
        local(cmd)

    # Update
    branch = branch and " %s" % branch or ""
    with lcd(env.hostout.options['path']):
        cmd = "hg update -C%s" % branch
        if env.hostout.options.get('local-sudo') == "true":
            cmd = "sudo %s" % cmd
        if output.running:
            print("[localhost] update: %s" % cmd)
        local(cmd)


def bootstrap(*args):
    """Executes bootstrap for the local buildout.

    The default effective python could be overridden by setting
    ``bootstrap-python`` hostout-option with a path to an another python
    executable."""

    buildout_python = env.hostout.options.get('executable')
    python = env.hostout.options.get('bootstrap-python', buildout_python)

    # Configure
    distribute = not "--easy-install" in args
    distribute = distribute and " --distribute" or ""

    # Bootstrap
    with lcd(env.hostout.options['path']):
        cmd = "%s bootstrap.py%s" % (python, distribute)
        if env.hostout.options.get('local-sudo') == "true":
            cmd = "sudo %s" % cmd
        elif env.hostout.options.get('buildout-user'):
            cmd = "sudo -i -u %s %s" % (env.hostout.options.get('buildout-user'),
                                  cmd)
        if output.running:
            print("[localhost] bootstrap: %s" % cmd)
        local(cmd)


def annotate():
    """Read buildout configuration and returns 'buildout' section as a dict."""

    buildout = Buildout("%s/%s" % (env.hostout.options['path'],
                                   env.hostout.options['buildout']), [])
    return buildout['buildout']


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
            cmd = "sudo -i -u %s %s" % (env.hostout.options.get('buildout-user'),
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

    cmd = "chown %s -R %s %s %s" % (effective_user, bin_directory,
                                    parts_directory, eggs_directory)
    if env.hostout.options.get('local-sudo') == "true":
        cmd = "sudo %s" % cmd
    if output.running:
        print("[localhost] buildout: %s" % cmd)
    local(cmd)

    # Chown "etc" (created by some buildout scripts)
    etc_directory = os.path.join(buildout_directory, "etc")
    if os.path.exists(etc_directory):
        cmd = "chown %s -R %s" % (effective_user, etc_directory)
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
    cmd = "chown %s -R %s" % (effective_user, var_directory)
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
    restart()


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

    rsync(bin_directory,
          os.path.join(bin_directory, "*"),
          reverse=True, delete=False)

    rsync(eggs_directory,
          os.path.join(eggs_directory, "*"),
          reverse=True, delete=False)

    rsync(parts_directory,
          os.path.join(parts_directory, "*"),
          reverse=True, delete=False)

    # Chown
    cmd = "chown %s -R %s %s %s" % (effective_user, bin_directory,
                                    parts_directory, eggs_directory)
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
            sudo("chown %s -R %s" % (effective_user, etc_directory))
        else:
            run("chown %s -R %s" % (effective_user, etc_directory))


def deploy_etc():
    """Copies system config from parts/system/etc to /etc."""

    buildout_directory = env.hostout.options["path"]
    annotations = annotate()
    parts_directory = os.path.join(buildout_directory,
                                   annotations['parts-directory'])

    if os.path.isdir("%s/system/etc" % parts_directory):
        cmd = "cp -R %s /etc" % (parts_directory + '/system/etc/*')

        if env.hostout.options.get('remote-sudo') == "true":
            sudo(cmd)
        else:
            run(cmd)


def deploy():
    """Deploys the local buildout to the remote site."""

    # Push the code
    push()

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

    cmd = "cp %s %s"\
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
