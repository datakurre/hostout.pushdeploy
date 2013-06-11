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
    """Perform rsync from some remote location to some local location.
    Optionally does exactly the reverse (syncs from some local location
    to some remote location)

    """
    # Adapted from:
    # https://github.com/fabric/fabric/blob/master/fabric/contrib/project.py

    # Create --exclude options from exclude list
    exclude_opts = ' --exclude "%s"' * len(exclude)

    # Double-backslash-escape
    exclusions = tuple([str(s).replace('"', '\\\\"') for s in exclude])

    # Honor SSH key(s)
    key_string = ''
    keys = key_filenames()
    if keys:
        key_string = '-i ' + ' -i '.join(keys)

    # Port
    user, host, port = normalize(env.host_string)
    if host.startswith('@'):
        host = host[1:]
    port_string = '-p {0:s}'.format(port)

    # RSH
    rsh_string = ''
    rsh_parts = [key_string, port_string, ssh_opts]
    if any(rsh_parts):
        rsh_string = '--rsh="ssh {0:s}"'.format(' '.join(rsh_parts))

    # Set remote sudo
    if env.hostout.options.get('remote-sudo') == 'true':
        remote_sudo = ' --rsync-path="sudo rsync"'
        extra_opts = (extra_opts + remote_sudo).strip()

    # Set up options part of string
    options_map = {
        'delete': '--delete' if delete else '',
        'exclude': exclude_opts % exclusions,
        'rsh': rsh_string,
        'extra': extra_opts
    }

    options = ('%(delete)s%(exclude)s -pthlrz '
               '%(extra)s %(rsh)s') % options_map

    # Interpret direction and define command
    if not reverse:
        cmd = 'rsync {0:s} {1:s}@{2:s}:{3:s} {4:s}'.format(
            options, user, host, from_path, to_path)
    else:
        cmd = 'rsync {0:s} {1:s} {2:s}@{3:s}:{4:s}'.format(
            options, to_path, user, host, from_path)

    if env.hostout.options.get('local-sudo') == 'true':
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] rsync: {0:s}'.format(cmd))
    return local(cmd, capture=capture)


def clone(repository, branch=None):
    """Clone a new local buildout from a mercurial repository.
    """

    buildout_directory = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert buildout_directory, u'No path found for the selected hostout'

    # Clone
    branch = branch and ' -r {0:s}'.format(branch) or ''
    cmd = 'hg clone {0:s}{1:s} {2:s}'.format(repository, branch, buildout_directory)
    cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] clone: {0:s}'.format(cmd))
    local(cmd)


def update(branch=None):
    """Update the local buildout from its mercurial repository.
    """

    buildout_directory = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert buildout_directory, u'No path found for the selected hostout'

    # Pull
    with lcd(buildout_directory):
        cmd = 'hg pull'
        cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
        if local_sudo:
            cmd = 'sudo {0:s}'.format(cmd)
        if output.running:
            print('[localhost] update: {0:s}'.format(cmd))
        local(cmd)

    # Update
    branch = bool(branch) and ' {0:s}'.format(branch) or ''
    with lcd(buildout_directory):
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
    buildout_directory = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert buildout_directory, u'No path found for the selected hostout'

    buildout_python = env.hostout.options.get('executable')
    bootstrap_python = (
        env.hostout.options.get('bootstrap-python') or buildout_python
    )

    # Bootstrap
    with lcd(buildout_directory):
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
    """Read buildout configuration and returns 'buildout' section as a dict.
    """

    buildout_directory = env.hostout.options.get('path')

    assert buildout_directory, u'No path found for the selected hostout'

    buildout = Buildout(
        '{0:s}/{1:s}'.format(buildout_directory, env.hostout.options['buildout']), []
    )
    return buildout.get('buildout')


def buildout(*args):
    """Execute the local buildout
    """

    buildout_directory = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    effective_user = env.hostout.options.get('effective-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert buildout_directory, u'No path found for the selected hostout'

    # Configure
    offline = '-o' in args and ' -o' or ''
    parts = [arg for arg in args if not arg.startswith('-')]
    parts = parts and ' install {0:s}'.format(' '.join(parts)) or ''

    # Buildout
    with lcd(buildout_directory):
        cmd = 'bin/buildout{0:s}{1:s}'.format(parts, offline)
        cmd = 'su {0:s} -c "{1:s}"'.format(buildout_user, cmd)
        if local_sudo:
            cmd = 'sudo {0:s}'.format(cmd)
        if output.running:
            print('[localhost] buildout: {0:s}'.format(cmd))
        local(cmd)

    # Chown var-directory
    var_directory = os.path.join(buildout_directory, 'var')
    cmd = 'chown -R {0:s} {1:s}'.format(effective_user, var_directory)
    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] pull: {0:s}'.format(cmd))
    local(cmd)


def pull():
    """Pull the data from the remote site into the local buildout.
    """

    buildout_directory = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    buildout_user = env.hostout.options.get('buildout-user', fallback_user)
    effective_user = env.hostout.options.get('effective-user', fallback_user)
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    assert buildout_directory, u'No path found for the selected hostout'

    var_directory = os.path.join(buildout_directory, 'var')
    filestorage_directory = os.path.join(var_directory, 'filestorage')

    # Ensure filestorage
    if not os.path.exists(var_directory):
        cmd = 'mkdir -p {0:s}'.format(filestorage_directory)
        if local_sudo:
            cmd = 'sudo {0:s}'.format(cmd)
        if output.running:
            print('[localhost] pull: {0:s}'.format(cmd))
        local(cmd)

    # Chown var-directory
    var_directory = os.path.join(buildout_directory, 'var')
    cmd = 'chown -R {0:s} {1:s}'.format(buildout_user, var_directory)
    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] pull: {0:s}'.format(cmd))
    local(cmd)

    # Pull filestorage
    rsync(os.path.join(filestorage_directory, 'Data.fs'),
          os.path.join(filestorage_directory, 'Data.fs'),
          delete=True)

    # Pull blobstorage
    rsync(os.path.join(var_directory, 'blobstorage'), var_directory,
          delete=True)

    # Chown var-directory
    var_directory = os.path.join(buildout_directory, 'var')
    cmd = 'chown -R {0:s} {1:s}'.format(effective_user, var_directory)
    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] pull: {0:s}'.format(cmd))
    local(cmd)


def restart():
    """Restart the local buildout. The restart command must be defined
    by setting a hostout-option ``restart``

    """
    local_sudo = env.hostout.options.get('local-sudo') == "true"

    # Restart
    cmd = env.hostout.options.get('restart')

    assert cmd, u'No restart command found for the selected hostout'

    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] restart: {0:s}'.format(cmd))
    local(cmd)


def stage():
    """Update the local staged buildout
    """

    # Pull
    pull()

    # Update
    update()

    # Bootstrap
    bootstrap()

    # Buildout
    buildout()

    # Restart
    if env.hostout.options.get('local-restart') == "true":
        restart()


def cook_resources():
    """Cook plone resources on remote
    """

    buildout_directory = env.hostout.options.get('path')

    assert buildout_directory, u'No path found for the selected hostout'

    annotations = annotate()
    buildout_name = annotations['buildoutname']

    cmd = '{0:s}/bin/instance -O {1:s} run `which resourcecooker.py`'.format(
        buildout_directory, buildout_name
    )
    res = sudo(cmd, warn_only=True)
    if res.failed:
        cmd = cmd.replace('/bin/instance -O', '/bin/instance1 -O')
        sudo(cmd, warn_only=True)


def push():
    """Push the local buildout results (without data) to the remote site.
    """

    # TODO: Currently all remote directories are chown for effective-user.
    # We should remote this for everything else except var-directory and
    # only chown the directories for effective-group.

    buildout_directory = env.hostout.options.get('path')
    fallback_user = env.user or 'root'
    effective_user = env.hostout.options.get('effective-user', fallback_user)
    effective_group = env.hostout.options.get('effective-group', '')
    remote_sudo = env.hostout.options.get('remote-sudo') == "true"

    assert buildout_directory, u'No path found for the selected hostout'

    # Make sure that the buildout directory exists on the remote
    if remote_sudo:
        sudo('mkdir -p {0:s}'.format(buildout_directory))
        sudo('chown {0:s}:{1:s} {2:s}'.format(
            effective_user, effective_group, buildout_directory))
    else:
        run('mkdir -p {0:s}'.format(buildout_directory))
        run('chown {0:s}:{1:s} {2:s}'.format(
            effective_user, effective_group, buildout_directory))

    # Push
    annotations = annotate()

    buildout_sub_directory = lambda x: os.path.join(buildout_directory, x)

    bin_directory = buildout_sub_directory(annotations['bin-directory'])
    eggs_directory = buildout_sub_directory(annotations['eggs-directory'])
    parts_directory = buildout_sub_directory(annotations['parts-directory'])
    products_directory = buildout_sub_directory('products')
    var_directory = buildout_sub_directory('var')

    for directory in [bin_directory, eggs_directory, parts_directory]:
        rsync(directory, os.path.join(directory, '*'),
              reverse=True, delete=False)
        # Chown
        cmd = 'chown -R {0:s}:{1:s} {2:s}'.format(
            effective_user, effective_group, directory)
        if remote_sudo:
            sudo(cmd)
        else:
            run(cmd)

    if os.path.isdir(products_directory):
        rsync(products_directory, os.path.join(products_directory, '*'),
              reverse=True, delete=False)
        # Chown
        cmd = 'chown -R {0:s}:{1:s} {2:s}'.format(
            effective_user, effective_group, products_directory)
        if remote_sudo:
            sudo(cmd)
        else:
            run(cmd)

    rsync(var_directory, os.path.join(var_directory, '*'),
          reverse=True, delete=False,
          exclude=('blobstorage*', '*.fs', '*.old', '*.zip', '*.log',
                   '*.backup'),
          extra_opts='--ignore-existing')
    # Chown
    cmd = 'chown -R {0:s}:{1:s} {2:s}'.format(
        effective_user, effective_group, var_directory)
    if remote_sudo:
        sudo(cmd)
    else:
        run(cmd)

    # Push 'etc' (created by some buildout scripts)
    etc_directory = os.path.join(buildout_directory, 'etc')
    if os.path.exists(etc_directory):
        rsync(etc_directory, os.path.join(etc_directory, '*'),
              reverse=True, delete=False)
    # Chown
    if os.path.exists(etc_directory):
        cmd = 'chown -R {0:s}:{1:s} {2:s}'.format(
            effective_user, effective_group, etc_directory)
        if remote_sudo:
            sudo(cmd)
        else:
            run(cmd)


def deploy_etc():
    """Copy system config from parts/system/etc to /etc
    """

    buildout_directory = env.hostout.options['path']

    annotations = annotate()

    buildout_sub_directory = lambda x: os.path.join(buildout_directory, x)
    parts_directory = buildout_sub_directory(annotations['parts-directory'])

    if os.path.isdir('%s/system/etc' % parts_directory):
        cmd = 'cp -R %s /etc;supervisorctl reread;supervisorctl update' % \
              (parts_directory + '/system/etc/*')

        if env.hostout.options.get('remote-sudo') == 'true':
            sudo(cmd)
        else:
            run(cmd)


def stop(site):
    """Stop the remote site
    """
    sudo('supervisorctl stop {0:s}:*'.format(site))


def start(site):
    """Start the remote site
    """
    sudo('supervisorctl start %s:*' % site)


def site_restart(site):
    """Restart the remote site
    """
    sudo('supervisorctl restart %s:*' % site)


def deploy():
    """Deploys the local buildout to the remote site
    """

    # Push the code
    push()
    deploy_etc()

    # Restart
    cmd = env.hostout.options.get('restart')

    assert cmd, u'No restart command found for the selected hostout'

    if env.hostout.options.get('remote-sudo') == 'true':
        sudo(cmd)
    else:
        run(cmd)


def stage_supervisor():
    """Update the local supervisor configuration. Supervisord configuration
    path must be defined by setting a hostout-option ``supervisor-conf``.

    """
    supervisor_conf = env.hostout.options.get('supervisor-conf')

    assert supervisor_conf, \
        u'No supervisor_conf found for the selected hostout'

    local_sudo = env.hostout.options.get('local-sudo') == "true"

    # Configure
    annotations = annotate()
    parts_directory = annotations['parts-directory']

    cmd = 'cp {0:s} {1:s}'.format(
        os.path.join(parts_directory, os.path.basename(supervisor_conf)),
        supervisor_conf
    )
    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] stage_supervisor: {0:s}'.format(cmd))
    local(cmd)

    # Update
    cmd = 'supervisorctl update'
    if local_sudo:
        cmd = 'sudo {0:s}'.format(cmd)
    if output.running:
        print('[localhost] stage_supervisor: {0:s}'.format(cmd))
    local(cmd)


def deploy_supervisor():
    """Update the remote supervisor configuration. Supervisord configuration
    path must be defined by setting a hostout-option ``supervisor-conf``.

    """
    supervisor_conf = env.hostout.options.get('supervisor-conf')

    assert supervisor_conf,\
        u'No supervisor_conf found for the selected hostout'

    # Sync
    annotations = annotate()
    parts_directory = annotations.get('parts-directory')

    rsync(supervisor_conf, os.path.join(parts_directory,
                                        os.path.basename(supervisor_conf)),
          reverse=True, delete=False)

    # Update
    if env.hostout.options.get('remote-sudo') == 'true':
        sudo('supervisorctl update')
    else:
        run('supervisorctl update')
