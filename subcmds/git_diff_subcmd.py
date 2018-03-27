
import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from topics import FormattedFile, GitProject, KrepError, Pattern, \
    RaiseExceptionIfOptionMissed, SubCommand


class RevisionError(KrepError):
    """Indicates the unknown revision."""


class GitDiffSubcmd(SubCommand):
    COMMAND = 'git-diff'

    REPORT_TEXT = 'report.txt'
    REPORT_HTML = 'report.html'

    FILTER_TEXT = 'filter.txt'
    FILTER_HTML = 'filter.html'

    IMMEDIATE_FILE = 'immediate.log'

    help_summary = 'Generate report of the git commits between two SHA-1s'
    help_usage = """\
%prog [options] SHA-1 [SHA-1] ...

Generates the report of the commits between two SHA-1s in purposed format.

The sub-command provides to list the commits between SHA-1s. If only one SHA-1
provided, the scope would be all the heads to the commit. If specific email or
email pattern provided, the matched commits will be categorized into a
separated report either.

The output format would be set to the plain text or HTML with link to the
gerrit server which can provide a query of the commit if gerrit is enabled.
"""

    def options(self, optparse):
        SubCommand.options(self, optparse, modules=globals())

        options = optparse.add_option_group('Remote options')
        options.add_option(
            '-r', '--remote',
            dest='remote', action='store',
            help='Set the remote server location')

        options = optparse.add_option_group('Output options')
        options.add_option(
            '-o', '--output',
            dest='output', action='store',
            help='Set the output directory')
        options.add_option(
            '--immediate',
            dest='immediate', action='store_true',
            help='Set the immediate directory to store the immediate files')
        options.add_option(
            '--gitiles',
            dest='gitiles', action='store_true',
            help='Enable gitiles links within the SHA-1')
        options.add_option(
            '--format',
            dest='format', metavar='TEXT, HTML, ALL',
            action='store', default='text',
            help='Set the report format')

    def execute(self, options, *args, **kws):
        SubCommand.execute(self, options, *args, **kws)

        RaiseExceptionIfOptionMissed(options.output, 'output is not set')

        name, remote = None, options.remote
        if options.remote:
            ulp = urlparse.urlparse(options.remote)
            if ulp.path:
                name = ulp.path.strip('/')
                remote = '%s://%s' % (ulp.scheme, ulp.hostname)
                if ulp.port:
                    remote += ':%d' % ulp.port

        format = options.format and options.format.lower()  # pylint: disable=W0622
        GitDiffSubcmd.generate_report(
            args, GitProject(None, worktree=options.working_dir),
            name or '', options.output, format, options.pattern,
            remote, options.immediate, options.gitiles)

    @staticmethod
    def build_pattern(patterns):
        if patterns:
            pats = list()
            for pat in patterns:
                if pat.find(':') > 0:
                    pats.append(pat)
                else:
                    pats.append('email:%s' % pat)

            pattern = Pattern(pats)
        else:
            pattern = Pattern()

        return pattern

    @staticmethod
    def generate_report(  # pylint: disable=R0915
            args, project, name, output, format,  # pylint: disable=W0622
            patterns, remote=None, immediate=False,
            gitiles=True):
        def _secure_sha(gitp, refs):
            ret, sha1 = gitp.rev_parse(refs)
            if ret == 0:
                return sha1
            else:
                raise RevisionError('Unknown %s' % refs)

        pattern = GitDiffSubcmd.build_pattern(patterns)

        brefs = list()
        if len(args) < 2:
            if len(args) == 0:
                print('No SHA-1 provided, use HEAD by default')

            erefs = _secure_sha(project, args[0] if args else 'HEAD')
            ret, head = project.rev_list('--max-parents=0', erefs)
            if ret == 0:
                brefs.extend(head.split('\n'))
        else:
            erefs = _secure_sha(project, args[1])
            brefs.append(_secure_sha(project, args[0]))

        ftext = None
        fhtml = None
        ftextp = None
        fhtmlp = None
        if not os.path.exists(output):
            os.makedirs(output)

        # pylint: disable=W0622
        if format:
            if format in ('all', 'text'):
                ftext = FormattedFile.open(
                    os.path.join(output, GitDiffSubcmd.REPORT_TEXT),
                    name, FormattedFile.TEXT)
                if pattern:
                    ftextp = FormattedFile.open(
                        os.path.join(output, GitDiffSubcmd.FILTER_TEXT),
                        name, FormattedFile.TEXT)

            if format in ('all', 'html'):
                fhtml = FormattedFile.open(
                    os.path.join(output, GitDiffSubcmd.REPORT_HTML),
                    name, FormattedFile.HTML)
                if pattern:
                    fhtmlp = FormattedFile.open(
                        os.path.join(output, GitDiffSubcmd.FILTER_HTML),
                        name, FormattedFile.HTML)
        # pylint: enable=W0622

        if immediate:
            GitDiffSubcmd._immediate(output, '', clean=True)

        for ref in brefs:
            refs = '%s..%s' % (ref, erefs) \
                if len(brefs) > 0 and len(args) > 1 else '%s' % erefs
            ret, log = project.log(
                '--format="%H %ae %ce %s"', '%s..%s' % (ref, erefs))

            logs = list()
            if ret == 0:
                for line in log.split('\n'):
                    line = line.strip('"').strip()
                    if line:
                        logs.append(line.split(' ', 3))

            if ftext:
                column = [0, 0, 0, 0]
                for item in logs:
                    for k, col in enumerate(item):
                        length = len(col)
                        if length > column[k]:
                            column[k] = length

                ftext.section(refs)
                with ftext.table(column) as table:
                    for sha1, author, committer, subject in logs:
                        table.row(sha1, author, committer, subject)

                if ftextp:
                    ftextp.section(refs)
                    with ftextp.table(column) as table:
                        for sha1, author, committer, subject in logs:
                            if pattern.match('e,email', committer):
                                table.row(sha1, author, committer, subject)

            if fhtml:
                fhtml.section(refs)
                with fhtml.table() as table:
                    for sha1, author, committer, subject in logs:
                        hauthor = fhtml.item(author, 'mailto:%s' % author)
                        hcommitter = fhtml.item(
                            committer, 'mailto:%s' % committer)
                        if not remote:
                            table.row(
                                sha1, hauthor, hcommitter, subject)
                            continue

                        if gitiles and name:
                            sha1a = fhtml.item(
                                sha1[:20], '%s#/q/%s' % (remote, sha1))
                            sha1b = fhtml.item(
                                sha1[20:], '%s/plugins/gitiles/%s/+/%s^!'
                                % (remote, name, sha1))

                            table.row(
                                fhtml.item((sha1a, sha1b), tag='pre'),
                                hauthor, hcommitter, subject)
                        else:
                            link = fhtml.item(
                                sha1, '%s#/q/%s' % (remote, sha1), tag='pre')
                            table.row(
                                link, hauthor, hcommitter, subject)

                if fhtmlp:
                    fhtmlp.section(refs)
                    with fhtmlp.table() as table:
                        for sha1, author, committer, subject in logs:
                            if not pattern.match('e,email', committer):
                                continue

                            hauthor = fhtml.item(author, 'mailto:%s' % author)
                            hcommitter = fhtml.item(
                                committer, 'mailto:%s' % committer)
                            if not remote:
                                table.row(sha1, hauthor, hcommitter, subject)
                                continue

                            if gitiles and name:
                                sha1a = fhtmlp.item(
                                    sha1[:20], '%s#q,%s' % (remote, sha1))
                                sha1b = fhtmlp.item(
                                    sha1[20:], '%s/plugins/gitiles/%s/+/%s^!'
                                    % (remote, name, sha1))

                                table.row(
                                    fhtmlp.item((sha1a, sha1b), tag='pre'),
                                    hauthor, hcommitter, subject)
                            else:
                                link = fhtmlp.item(
                                    sha1, '%s#q,%s' % (remote, sha1),
                                    tag='pre')
                                table.row(link, hauthor, hcommitter, subject)

            if immediate:
                GitDiffSubcmd._immediate(output, '## %s' % refs)
                GitDiffSubcmd._immediate(output, '-' * (len(refs) + 3))
                GitDiffSubcmd._immediate(output, log)

        if ftextp:
            ftextp.close()
        if fhtmlp:
            fhtmlp.close()
        if ftext:
            ftext.close()
        if fhtml:
            fhtml.close()

        return True

    @staticmethod
    def _immediate(path, text, clean=False):
        filename = os.path.join(path, GitDiffSubcmd.IMMEDIATE_FILE)
        if clean and os.path.exists(filename):
            os.unlink(filename)

        if text:
            with open(filename, 'wb') as fp:
                fp.write(text)
