from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in smart_court/__init__.py
from smart_court import __version__ as version

setup(
	name="supportsystem",
	version=version,
	description="Support System",
	author="Bizmap",
	author_email="hemangi.gajjar79@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
