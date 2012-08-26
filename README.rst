collective.pushdeploy
=====================

Traditionally, Plone has been deployed using buildout. That's also how
`collective.hostout <http://pypi.python.org/pypi/collective.hostout>`_ works
by default.

*collective.pushdeploy* takes a new approach. We assume that you have
separate staging and deployment servers, and those servers are identical
in any reasonable way. At least, make sure that all used buildout paths
and Python-paths are identical.

With *collective.pushdeploy*, you could:

* pull production data from your deploymnet server your staging server
* run your buildout locally on the staging server
* push the pre-built buildout directory (mainly *bin*, *parts* and *eggs*)
  onto the deployment server (using rsync)
* restart your site on the deployment server

Note! *collective.pushdeploy* overwrites a lot of default *collective.hostout*
commands.

Usage
-----

An example *buildout.cfg* for pushdeployment for two separate sites could look
like::

    [buildout]
    parts =
        first-site
        another-site
    versions = versions
    unzip = true

    [versions]
    zc.buildout = 1.6.2
    collective.hostout = 1.0a5

    [pushdeploy-defaults]
    recipe = collective.hostout
    extends = hostout.pushdeploy

    user = root
    effective-user = zope

    [first-site]
    <= pushdeploy-defaults

    host = example.com
    path = /var/buildout/first_site

    restart = supervisorctl restart first-site:*

    [another-site]
    <= pushdeploy-defaults

    host = another-example.com
    path = /var/buildout/first_site

    restart = supervisorctl restart another-site:*

    effective-user = m3user
    bootstrap-python = /usr/local/virtualenvs/Plone4.2/bin/python

Be aware, that you can use the complete magic of buildout to abstract your
configuration into separate buildout-files.

After buildout, you could use *bin/hostout* command to update your
site through staging:

bin/hostout first-site stage
    * rsync data (*blobstorage* and *Data.fs*) from your deployment server
    * update your staging buildout from its repository (only
      hg is supported)
    * run the staging buildout locally

bin/hostout first-site deploy
    * rsync your staged buildout (bin*, *parts*, *eggs*) onto your
      deployment server
    * restart your site on the deployment server

All sub-commands can also be run separately, as follows:

bin/hostout first-site checkout http://dev.example.com/myrepo mybranch
    checkout the buildout

bin/hostout first-site update mybranch
    update the staging buildout from its repository (only hg is supported)

bin/hostout first-site bootstrap
    bootstrap the buildout; either the python of the  current buildout or using
    the configured *bootstrap-python*

bin/hostout first-site buildout
    run the staging buildout locally

bin/hostout first-site pull
    rsync data (*blobstorage* and *Data.fs*) from the deployment server

bin/hostout first-site push
    rsync your staged buildout (bin*, *parts*, *eggs*) onto your deployment
    server

bin/hostout first-site restart
    restart site on the deployment server

All of the commands above include proper *chowning* of updated files.
