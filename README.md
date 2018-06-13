![](https://img.shields.io/badge/python-2.7%2C%203.6-blue.svg)

Git log tool for git and [git-repo] project
============================================

The tool works as [krep] plug-ins to generate `git log` report in both HTML
and plain text.

It can operate with the `git` and `git-repo` project with the `topics`
components provided by [krep]. So it need integrate as the sub-commands with
the `krep` core. And `RepoSubcmd` has been referred because the sub-command
for [git-repo] likes to use its `static` method to open the [git-repo]
manifest file in a normal way.

[krep] starts supporting to lead outside plug-ins with the commit
[krep: support to load files dynamically with environ variables](
https://github.com/cadappl/krep/commit/915f6c8eff1cddbf99bff96d646bba16249e68e7
). The tool need the `krep` branch of [krep] and has the commit to change
the argument of `RepoSubcmd.get_manifest`.

As the tool involves both `subcmds` and `topics`, the variable
`KREP_EXTRA_PATH` need to be set to point to the location of the git.

```sh
├── LICENSE
├── README.md
├── subcmds
│   ├── git_diff_subcmd.py
│   └── repo_diff_subcmd.py
└── topics
    └── format_file.py
```

The more details of the sub-commands can be referred with the command
`krep help` and the help output of the sub-commands.

[krep]: https://github.com/cadappl/krep
[git-repo]: https://gerrit.googlesource.com/git-repo

