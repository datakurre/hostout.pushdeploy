from setuptools import setup, find_packages

version = "1.0.0"

setup(name="hostout.pushdeploy",
      version=version,
      description="",
      long_description=open("README.rst").read() + "\n" +
                       open("HISTORY.txt").read(),
      # Get more strings from
      # http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
          "Programming Language :: Python",
      ],
      keywords="",
      author="Asko Soukka",
      author_email="asko.soukka@iki.fi",
      url="",
      license="GPL",
      packages=find_packages("src", exclude=["ez_setup"]),
      package_dir={"": "src"},
      namespace_packages=["hostout"],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          "setuptools",
          "Fabric",
          "collective.hostout>=1.0a5",
      ],
      entry_points = {
          'zc.buildout':['default = hostout.pushdeploy:Recipe'],
                         'fabric': ['fabfile = hostout.pushdeploy.fabfile']
      },
      )
