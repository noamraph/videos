from setuptools import setup
setup(
    name="revbranch",
    version="0.1",
    modules=["revbranch"],
    entry_points={
        "console_scripts": [
            "revbranch = revbranch:main",
        ]
    },

    install_requires=["dulwich"],
    extras_require={
        'dev': [
            'pytest',
        ]
    },

    # metadata to display on PyPI
    author="Noam Yorav-Raphael",
    author_email="noamraph@gmail.com",
    description="Attach branch names to git revisions, to help understand repository history",
    keywords="git",
    url="https://github.com/noamraph/revbranch",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Version Control :: Git",
    ],

    # TODO: add long_description
)
