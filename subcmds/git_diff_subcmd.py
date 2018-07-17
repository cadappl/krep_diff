
import os
import shutil

from collections import namedtuple
from synchronize import synchronized

try:
  from urllib.parse import urlparse
except ImportError:
  from urlparse import urlparse

from topics import FormattedFile, GitProject, Pattern, SubCommand


CommitInfo = namedtuple('CommitInfo', 'sha1,author,committer,title,info')


class Results:
  def __init__(self):
    self.changes = dict()

  @synchronized
  def put(self, name, value):
    self.changes[name] = value

  def get(self, name=None, item=None):
    if name:
      if item:
        alt = {'full': 0, 'no_merge': 1, 'filter': 2, 'filter_no_merge': 3}
        if name in self.changes:
          return self.changes[name][alt[item]]
        else:
          return 0
      else:
        return self.changes.get(name)
    else:
      return self.changes


class GitDiffSubcmd(SubCommand):
  COMMAND = 'git-diff'

  help_summary = 'Generate report of the git commits between two SHA-1s'
  help_usage = """\
%prog [options] SHA-1 [SHA-1] ...

Generates the report of the commits between two SHA-1s in purposed format.

The sub-command provides to list the commits between SHA-1s. If only one SHA-1
provided, the scope would be all the heads to the commit. If specific email or
email pattern provided, the matched commits will be categorized into a
separated report either.

The output format would be set to the plain text or HTML with link to the
gerrit server which can provide a query of the commit if gerrit is enabled."""

  def options(self, optparse):
    SubCommand.options(self, optparse, modules=globals())

    options = optparse.add_option_group('Remote options')
    options.add_option(
      '-r', '--remote',
      dest='remote', action='store',
      help='Set the remote server location')

    options = optparse.get_option_group('--hook-dir') or \
      optparse.add_option_group('File options')
    options.add_option(
      '-o', '--output',
      dest='output', action='store', default='out',
      help='Set the output directory, default: %default')

    options = optparse.add_option_group('Format options')
    options.add_option(
      '--generate-no-merge',
      dest='generate_no_merge', action='store_true',
      help='Generate the table without merge')

    options = optparse.add_option_group('Format options')
    options.add_option(
      '--gitiles',
      dest='gitiles', action='store_true',
      help='Enable gitiles links within the SHA-1')
    options.add_option(
      '--format',
      dest='format', metavar='TEXT, HTML, ALL',
      action='store', default='html',
      help='Set the report format. default: %default')

  def execute(self, options, *args, **kws):
    SubCommand.execute(self, options, *args, **kws)

    name, remote = None, options.remote
    project = GitProject(None, worktree=options.working_dir)

    ulp = None
    if options.remote:
      ulp = urlparse(options.remote)
    else:
      ret, urlproj = project.ls_remote('--get-url')
      if ret == 0 and urlproj:
        ulp = urlparse(urlproj)

    if ulp and ulp.path:
      name = ulp.path.strip('/')
      remote = '%s://%s' % (ulp.scheme, ulp.hostname)
      if ulp.port:
        remote += ':%d' % ulp.port

    format = options.format and options.format.lower()  # pylint: disable=W0622
    pattern = GitDiffSubcmd.get_patterns(options)  # pylint: disable=E1101
    GitDiffSubcmd.generate_report(
      args, project,
      name or '', options.output, options.output, format,
      pattern, remote, options.gitiles, options.gen_no_merge)

  @staticmethod
  @synchronized
  def deploy(script, root, refer):
    origin = os.path.realpath(
      '%s/../%s' % (os.path.dirname(__file__), script))
    target = os.path.join(root, script)

    if not os.path.exists(target):
      dirname = os.path.dirname(target)
      if not os.path.exists(dirname):
        os.makedirs(dirname)

      shutil.copyfile(origin, target)

    return os.path.relpath(target, refer)

  @staticmethod
  def get_commits(project, sref, eref, *options):
    args = list()
    if len(options) > 0:
        args.extend(options)
    args.append('--pretty=%H')
    args.append('%s..%s' % (sref, eref))

    ret, sha1s = project.log(*args)
    if ret == 0:
      vals = list()
      for sha1 in sha1s.split('\n'):
        sha1 = sha1.strip('"')
        if sha1:
            vals.append(sha1)

      return vals
    else:
      return list()

  @staticmethod
  def get_commit_detail(project, sha1):
    vals = list()
    wrong = '!!Wrong decoded!!'

    for item in ('%ae', '%ce', '%s'):
      try:
        _, val = project.show(
          '--no-patch', '--oneline', '--format=%s' % item, sha1)
      except UnicodeDecodeError:
        val = wrong

      vals.append(val)

    try:
      _, info = project.show('--name-only', sha1)
    except UnicodeDecodeError:
      info = wrong

    return CommitInfo(sha1, vals[0], vals[1], vals[2], info)

  @staticmethod
  def get_commits_detail(project, sref, eref, *options):
    details = dict()
    sha1s = GitDiffSubcmd.get_commits(project, sref, eref, *options)
    for sha1 in sha1s:
      details[sha1] = GitDiffSubcmd.get_commit_detail(project, sha1)

    return details

  @staticmethod
  def get_commit_ci(project, details, sha1):
    if sha1 not in details:
      details[sha1] = GitDiffSubcmd.get_commit_detail(project, sha1)

    return details[sha1]

  @staticmethod
  def update_table(
      accord, details, logs, id, title, remote=None,
      name=None, gitiles=True):
    tid = 'div_%d' % id
    hid = 'header_%d' % id

    with accord.div(clazz='card w-90', id='entire_%d' % id) as dcard:
      with dcard.div(clazz='card-header', id=hid) as dhd:
        with dhd.wh5(clazz='mb-0') as h5:
          with h5.wbutton(
              title,
              clazz='btn btn-link', data_toggle='collapse',
              data_target='#%s' % tid, aria_expanded='true',
              aria_controls=tid) as wb:
            wb.span(len(logs), clazz='badge badge-info')

      with dcard.div(
          clazz='collapse show', id=tid, aria_labelledby=hid,
          data_parent='#%s' % tid) as cont:
        with cont.div(clazz='card-body') as cbd:
          with cbd.table(clazz='table table-hover table-striped') as table:
            with table.tr() as tr:
              tr.th('SHA-1', scope='col')
              tr.th('Author', scope='col')
              #tr.th('Committer', scope='col')
              tr.th('Title', scope='col')

            for sha1 in logs:
              with table.tr() as tr:
                with tr.wtd() as td:
                  if name:
                      with td.wpre(_nowrap=True) as pre:
                        if gitiles:
                          pre.a(
                            sha1[:20],
                            href='%s/#/q/%s' % (remote, sha1))
                          pre.a(
                            sha1[20:],
                            href='%s/plugins/gitiles/%s/+/%s^!' %
                              (remote, name, sha1))
                        else:
                          pre.a(sha1, href='%s/#/q/%s' % (remote, sha1))
                  else:
                    td.pre(sha1)

                if sha1 in details:
                  commit = details[sha1]
                else:
                  commit = CommitInfo(sha1, 'Unknown', 'Unknown', '')

                with tr.wtd() as td:
                  td.a(commit.author, href='mailto:%s' % commit.author)

                if commit.info:
                  tr.td(
                    commit.title, data_toggle='tooltip', data_html='true',
                    title="%s" % tr.escape_str(commit.info))
                else:
                  tr.td(commit.title, clazz='align-middle')

  @staticmethod
  def generate_report(  # pylint: disable=R0915
      args, project, name, root, output, format,  # pylint: disable=W0622
      pattern, remote=None, gitiles=True, gen_no_merge=False, results=None):
    def _secure_sha(gitp, refs):
      ret, sha1 = gitp.rev_parse(refs)
      if ret == 0:
        return sha1
      else:
        ret, sha1 = gitp.rev_parse('%s/%s' % (project.remote, refs))
        if ret == 0:
          return sha1
        else:
          return ''

    EXTENSIONS = {'txt': '.txt', 'html': '.html', 'all': ''}
    if format not in EXTENSIONS:
      print('Error: Unknown format to generate ....')
      return None

    num = 0
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
      # if two sha-1s are equaling, return
      if erefs == brefs[-1]:
        if results:
          results.put(name, 0)

        return

    if not os.path.exists(output):
      os.makedirs(output)

    GitDiffSubcmd._generate_html(
      brefs, erefs, args, project, name, root, output,
      os.path.join(output, 'index.html'),
      pattern, remote, gitiles, gen_no_merge, results, full=True)

    fresults = Results()
    filter_name = os.path.join(output, 'filter.html')
    GitDiffSubcmd._generate_html(
      brefs, erefs, args, project, name, root, output,
      filter_name, pattern, remote, gitiles, gen_no_merge, fresults)

    if fresults.get(name, 'filter') == 0:
      os.unlink(filter_name)

    # try cleaning the directory and parents
    def file_num_in_dir(dname):
      if os.path.exists(dname):
        return len(filter(lambda d: d not in ['.', '..'], os.listdir(dname)))
      else:
        return -1

    dirname = os.path.dirname(filter_name)
    while len(dirname) > len(root) and file_num_in_dir(dirname) == 0:
      os.rmdir(dirname)
      dirname = os.path.dirname(dirname)

  @staticmethod
  def _generate_html(  # pylint: disable=R0915
      brefs, erefs, args, project, name, root, output, filename,  # pylint: disable=W0622
      pattern, remote=None, gitiles=True, gen_no_merge=False,
      results=None, full=False):

    fulla, fullm, filtera, filterm = 0, 0, 0, 0
    with FormattedFile.open(filename, 'html') as outfile:
      with outfile.head() as head:
        head.meta(charset='utf-8')
        head.title(name)

        head.comment(' Boot strap core CSS ')
        head.link(
          href=GitDiffSubcmd.deploy(
            'asserts/css/bootstrap.min.css', root, output),
          rel='stylesheet')
        head.link(
          href=GitDiffSubcmd.deploy(
            'asserts/css/krep-diff.css', root, output),
          rel='stylesheet')

      with outfile.body() as bd:
        with bd.nav(clazz="nav navbar-dark bg-dark") as nav:
          with nav.wbutton(clazz="navbar-toggler", type="button") as bnav:
            bnav.span('', clazz="navbar-toggler-icon")

        bd.p()
        with bd.div(clazz='card w-75') as bdiv:
          with bdiv.div(clazz='card-block') as block:
            with block.table(clazz='table') as btb:
              for title, refss in (
                  ('Start Refs', brefs), ('End Refs', [erefs])):
                with btb.tr() as tr:
                  tr.td(title)

                  with tr.wtd(_nowrap=True) as td:
                    for m, ref in enumerate(refss):
                      if m:
                        td.br()

                      if gitiles:
                        td.a(
                          ref,
                          href='%s/plugins/gitiles/%s/+/%s^!' %
                            (remote, name, ref))
                      else:
                        td.write(ref)

                      # avaiable in 1.7.10
                      ret, tags = project.tag('--points-at', ref)
                      if ret == 0 and tags.strip():
                        td.write(' (')
                        for k, tag in enumerate(tags.split('\n')):
                          if k > 0:
                            td.write(', ')

                          if gitiles:
                            td.a(
                              tag,
                              href='%s/plugins/gitiles/%s/+/%s' %
                                (remote, name, tag))
                          else:
                            td.write(tag)

                        td.write(')')

        bd.p()
        with bd.div(id='accordion') as acc:
          details = GitDiffSubcmd.get_commits_detail(project, ref, erefs)

          index = 1
          # full log
          if full:
            for ref in brefs:
              logs = GitDiffSubcmd.get_commits(project, ref, erefs)
              if logs:
                fulla += len(logs)
                GitDiffSubcmd.update_table(
                  acc, details, logs, index, '%s..%s' % (ref, erefs),
                  remote, name, gitiles)
                index += 1

            # log with no merge
            if gen_no_merge:
              for ref in brefs:
                logs = GitDiffSubcmd.get_commits(
                  project, ref, erefs, '--no-merges')
                if logs:
                  fullm += len(logs)
                  GitDiffSubcmd.update_table(
                    acc, details, logs, index,
                    '%s..%s (No merges)' % (ref, erefs),
                    remote, name, gitiles)
                  index += 1

          if pattern:
            # full log with pattern
            bd.pre('Filtered Results')
            for ref in brefs:
              logs = GitDiffSubcmd.get_commits(project, ref, erefs)

              filtered = list()
              for li in logs:
                ci = GitDiffSubcmd.get_commit_ci(project, details, li)
                if pattern.match('e,email', ci.committer):
                  filtered.append(li)

              if filtered:
                filtera += len(filtered)
                GitDiffSubcmd.update_table(
                  acc, details, filtered, index, '%s..%s' % (ref, erefs),
                  remote, name, gitiles)
                index += 1

            # log with pattern and no merge
            if gen_no_merge:
              for ref in brefs:
                logs = GitDiffSubcmd.get_commits(
                  project, ref, erefs, '--no-merges')

                filtered = list()
                for li in logs:
                  ci = GitDiffSubcmd.get_commit_ci(project, details, li)
                  if pattern.match('e,email', ci.committer):
                    filtered.append(li)

                if filtered:
                  filterm += len(filtered)
                  GitDiffSubcmd.update_table(
                    acc, details, filtered, index,
                    '%s..%s (No merges)' % (ref, erefs),
                    remote, name, gitiles)
                  index += 1

        bd.script(
          "window.jQuery || document.write('<script src=\"%s\">"
          "<\/script>')" % GitDiffSubcmd.deploy(
            'asserts/js/vendor/jquery-slim.min.js', root, output),
          _escape=False)
        # write an empty string to keep <script></script> to make js working
        bd.script(
          '',
          src=GitDiffSubcmd.deploy(
            'asserts/js/bootstrap.min.js', root, output))

    if results:
      res = results.get(name) or [0, 0, 0, 0]
      results.put(
        name, [
          res[0] or fulla,
          res[1] or fullm,
          res[2] or filtera,
          res[3] or filterm])
