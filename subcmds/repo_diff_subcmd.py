
import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from git_diff_subcmd import GitDiffSubcmd
from krep_subcmds.repo_subcmd import RepoSubcmd
from topics import GitProject, FormattedFile, RaiseExceptionIfOptionMissed


class RepoDiffSubcmd(GitDiffSubcmd):
    COMMAND = 'repo-diff'

    INDEX_HTML = 'index.html'

    help_summary = 'Generate the diff report for a repo project'
    help_usage = """\
%prog [options] manifest.xml [diff-manifest.xml] ...

Handle the git-repo project git commits diff and generate the reports in
purposed formats."""

    def options(self, optparse):
        GitDiffSubcmd.options(self, optparse)

    def execute(self, options, *args, **kws):

        RaiseExceptionIfOptionMissed(options.output, 'output is not set')

        logger = self.get_logger()  # pylint: disable=E1101

        pattern = GitDiffSubcmd.build_pattern(options.pattern)
        format = options.format and options.format.lower()  # pylint: disable=W0622
        if not os.path.exists(options.output):
            os.makedirs(options.output)

        with FormattedFile(
            os.path.join(options.output, RepoDiffSubcmd.INDEX_HTML),
            'Repo Diff', FormattedFile.HTML, css=GitDiffSubcmd.HTML_CSS) as fp:

            pdiff = None
            if len(args) > 1:
                mandiff = RepoSubcmd.get_manifest(options, args[0])
                pdiff = dict()
                for node in mandiff.get_projects():
                    pdiff[node.name] = node

                manifest = RepoSubcmd.get_manifest(options, args[1])
            elif len(args) == 1:
                manifest = RepoSubcmd.get_manifest(options, args[0])
            else:
                manifest = RepoSubcmd.get_manifest(options, '.repo/manifest.xml')

            for k, node in enumerate(manifest.get_projects()):
                if not os.path.exists(node.path):
                    logger.warning('%s not existed, ignored', node.path)
                    continue
                #elif not pattern.match('p,project', node.name) and \
                #        not pattern.match('p,project', node.path):
                #    logger.warning('%s: ignored with pattern', node.name)
                #    continue

                print('Project %s' % node.name)

                remote = options.remote
                if not remote:
                    iremote = manifest.get_remote(
                        node.remote or manifest.get_default().remote)
                    if iremote:
                        remote = iremote.review

                if remote:
                    ulp = urlparse(remote)
                    if not ulp.scheme:
                        remote = 'http://%s' % remote

                project = GitProject(
                    node.name,
                    worktree=os.path.join(
                        self.get_absolute_working_dir(options), node.path),
                    revision=node.revision)

                revisions = list()
                if pdiff and node.name in pdiff:
                    revisions.append(pdiff[node.name].revision)

                revisions.append(node.revision)
                outputdir = os.path.join(options.output, node.name)
                commits = GitDiffSubcmd.generate_report(
                    revisions, project, node.name, outputdir, format,
                    options.pattern, remote, options.gitiles)

                if commits:
                    def _linked_item(fp, dirpath, name):
                        return fp.item(
                            name, os.path.join(dirpath, name))

                    column = list()
                    column.append(
                        fp.item(
                            node.name, os.path.join(options.output, node.name)))

                    if format in ('all', 'html'):
                        column.append(
                            _linked_item(
                                fp, outputdir, GitDiffSubcmd.REPORT_HTML))
                    if format in ('all', 'text'):
                        column.append(
                            _linked_item(
                                fp, outputdir, GitDiffSubcmd.REPORT_TEXT))

                    if options.pattern:
                        if format in ('all', 'html'):
                            column.append(
                                _linked_item(
                                    fp, outputdir, GitDiffSubcmd.FILTER_HTML))
                        if format in ('all', 'text'):
                            column.append(
                                _linked_item(
                                    fp, outputdir, GitDiffSubcmd.FILTER_TEXT))

                    #- hide
                    column.append(
                        fp.item('(%d)' % len(commits),
                        '#hide%d' % k, id='#hide%d' % k, css='hide'))
                    #- show
                    column.append(
                        fp.item('(%d)' % len(commits),
                        '#show%d' % k, id='#show%d' % k, css='show'))
                    with fp.div():
                      fp.section(' '.join([str(col) for col in column]))
                      with fp.div(css='details'):
                        with fp.table(css='hoverTable') as table:
                            for sha1, author, committer, subject in commits:
                                if not remote:
                                    table.row(
                                        sha1, author, committer, subject,
                                        td_csses=GitDiffSubcmd.TABLE_CSS)
                                    continue

                                if options.gitiles:
                                    sha1a = fp.item(
                                        sha1[:20], '%s#q,%s' % (remote, sha1))
                                    sha1b = fp.item(
                                        sha1[20:],
                                        '%s/plugins/gitiles/%s/+/%s^!'
                                        % (remote, node.name, sha1))

                                    table.row(
                                        fp.item((sha1a, sha1b), tag='pre'),
                                        author, committer, subject,
                                        td_csses=GitDiffSubcmd.TABLE_CSS)
                                else:
                                    link = fp.item(
                                        sha1, '%s#q,%s' % (remote, sha1),
                                        tag='pre')
                                    table.row(
                                        link, author, committer, subject,
                                        td_csses=GitDiffSubcmd.TABLE_CSS)

        return True

