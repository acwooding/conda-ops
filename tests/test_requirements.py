import json
from conda_ops.requirements import LockSpec, PackageSpec
from conda_ops.commands_env import env_delete


def test_from_pip_dict_parsing():
    test_case = json.loads(
        """{
      "download_info": {
        "url": "https://files.pythonhosted.org/packages/d8/f0/a2ee543a96cc624c35a9086f39b1ed2aa403c6d355dfe47a11ee5c64a164/annotated_types-0.5.0-py3-none-any.whl",
        "archive_info": {
          "hash": "sha256=58da39888f92c276ad970249761ebea80ba544b77acddaa1a4d6cf78287d45fd",
          "hashes": {
            "sha256": "58da39888f92c276ad970249761ebea80ba544b77acddaa1a4d6cf78287d45fd"
          }
        }
      },
      "is_direct": false,
      "requested": false,
      "metadata": {
        "metadata_version": "2.1",
        "name": "annotated-types",
        "version": "0.5.0",
        "summary": "Reusable constraint types to use with typing.Annotated",
        "description": "descr text",
        "description_content_type": "text/markdown",
        "author_email": "Samuel Colvin <s@muelcolvin.com>, Adrian Garcia Badaracco <1755071+adriangb@users.noreply.github.com>, Zac Hatfield-Dodds <zac@zhd.dev>",
        "classifier": [
          "Development Status :: 4 - Beta",
          "Environment :: Console",
          "Environment :: MacOS X",
          "Intended Audience :: Developers",
          "Intended Audience :: Information Technology",
          "License :: OSI Approved :: MIT License",
          "Operating System :: POSIX :: Linux",
          "Operating System :: Unix",
          "Programming Language :: Python :: 3 :: Only",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3.11",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Typing :: Typed"
        ],
        "requires_dist": [
          "typing-extensions>=4.0.0; python_version < '3.9'"
        ],
        "requires_python": ">=3.7"
      }
    }
  """
    )

    p = LockSpec.from_pip_report(test_case)

    assert p.name == "annotated-types"
    assert p.version == "0.5.0"
    assert p.url == "https://files.pythonhosted.org/packages/d8/f0/a2ee543a96cc624c35a9086f39b1ed2aa403c6d355dfe47a11ee5c64a164/annotated_types-0.5.0-py3-none-any.whl"
    assert p.sha256_hash == "58da39888f92c276ad970249761ebea80ba544b77acddaa1a4d6cf78287d45fd"
    assert p.manager == "pip"


def test_from_conda_dict_parsing():
    test_case = json.loads(
        """{
        "base_url": "https://conda.anaconda.org/pypi",
        "build_number": 0,
        "build_string": "pypi_0",
        "channel": "pypi",
        "dist_name": "texttable-1.6.7-pypi_0",
        "name": "texttable",
        "platform": "pypi",
        "version": "1.6.7"
      }"""
    )

    p = LockSpec.from_conda_list(test_case)

    assert p.name == "texttable"
    assert p.version == "1.6.7"
    assert p.manager == "pip"


def test_to_explicit():
    test_cases = json.loads(
        """[
  {
    "channel": "pypi",
    "manager": "pip",
    "name": "igraph",
    "hash": {
      "sha256": "eb97640e9e71913015e7073341a5f6b4017fe025222950873c507d4ee97670f9"
    },
    "url": "https://files.pythonhosted.org/packages/0d/29/e931551821bca836300deba16090ebec37030b285322b3763916843fefcd/igraph-0.10.6-cp39-abi3-macosx_10_9_x86_64.whl",
    "version": "0.10.6"
  },
  {
    "channel": "pkgs/main",
    "hash": {
      "md5": "2cc7f4d64fba19f5be1a594c8cbad73e"
    },
    "manager": "conda",
    "name": "ipython",
    "url": "https://repo.anaconda.com/pkgs/main/osx-64/ipython-8.12.0-py311hecd8cb5_0.conda",
    "version": "8.12.0"
  }]"""
    )
    results = []
    for test in test_cases:
        results.append(LockSpec(test).to_explicit())

    assert results == [
        "igraph @ https://files.pythonhosted.org/packages/0d/29/e931551821bca836300deba16090ebec37030b285322b3763916843fefcd/igraph-0.10.6-cp39-abi3-macosx_10_9_x86_64.whl --hash=sha256:eb97640e9e71913015e7073341a5f6b4017fe025222950873c507d4ee97670f9",
        "https://repo.anaconda.com/pkgs/main/osx-64/ipython-8.12.0-py311hecd8cb5_0.conda#2cc7f4d64fba19f5be1a594c8cbad73e",
    ]


def test_package_parsing():
    p = PackageSpec("git+https://github.com/lmcinnes/pynndescent.git", manager="pip")
    assert p.spec == "git+https://github.com/lmcinnes/pynndescent.git"
    assert str(p) == "git+https://github.com/lmcinnes/pynndescent.git"
