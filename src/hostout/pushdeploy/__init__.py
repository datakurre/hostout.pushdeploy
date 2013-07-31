# -*- coding: utf-8 -*-
"""This is hostout.pushdeploy.

It provides (and overrides the default) hostout-commands for running buildout
on a local staging server and pushing the results to the remote production
server.

"""


class Recipe(object):
    """Dummy recipe to provide defaults for a pushdeploy-configuration
    """

    def __init__(self, buildout, name, options):
        self.name, self.options, self.buildout = name, options, buildout

        # Set 'local-sudo'
        local_sudo = self.options.get('local-sudo')
        if local_sudo in (True, 'True', 'true', 'Yes', 'yes', 1, '1'):
            self.options['local-sudo'] = 'true'
        else:
            self.options['local-sudo'] = 'false'

        # Set 'remote-sudo'
        remote_sudo = self.options.get('remote-sudo')
        if remote_sudo in (True, 'True', 'true', 'Yes', 'yes', 1, '1'):
            self.options['remote-sudo'] = 'true'
        else:
            self.options['remote-sudo'] = 'false'

        # Set 'local-restart'
        local_sudo = self.options.get('local-restart')
        if local_sudo in (True, 'True', 'true', 'Yes', 'yes', 1, '1'):
            self.options['local-restart'] = 'true'
        else:
            self.options['local-restart'] = 'false'

    def install(self):
        return []

    def update(self):
        return []
