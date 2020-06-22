from setuptools import find_packages, setup
import os

def parse_requirements(filename):
    """ load requirements from a pip requirements file """
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]

reqs = parse_requirements(os.path.join(os.path.dirname(__file__), 'requirements.txt'))

setup(
    name='runquery',
    version='0.1',
    author='Oliver Kurth',
    author_email='okurth@gmail.com',
    url='http://github.com/oliverkurth/runquery',
    license='Apache',
    description='Web App to search strava activities',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=reqs
)

