
import os
import re
import time
import shutil

from collections import namedtuple
from synchronize import synchronized

try:
  from urllib.parse import urlparse
except ImportError:
  from urlparse import urlparse

from topics import FormattedFile, GitProject, Pattern, \
  RaiseExceptionIfOptionMissed, SubCommand


CommitInfo = namedtuple('CommitInfo', 'sha1,date,author,committer,title,info')


class Persist(object):
  def __init__(self, full, no_merge, filter, filter_no_merge):
    self.full = full
    self.no_merge = no_merge
    self.filter = filter
    self.filter_no_merge = filter_no_merge

  def __len__(self):
    return len(self.full) + len(self.no_merge) \
      + len(self.filter) + len(self.filter_no_merge)

class Result(Persist):
  def __init__(self, remote=None, full=0, no_merge=0,
               filter=0, filter_no_merge=0):

    Persist.__init__(self, full, no_merge, filter, filter_no_merge)

    self.remote = remote

  def __len__(self):
    return self.full + self.no_merge + self.filter + self.filter_no_merge

  def __str__(self):
    return '<%r remote=%s full=%d no_merge=%s filter=%d filter_no_merge=%d>' \
        % (self, self.remote, self.full, self.no_merge, self.filter,
           self.filter_no_merge)

  def update(self, full=None, no_merge=None, filter=None, filter_no_merge=None,
             result=None, override=True, increase=False):
    if override:
      if full is not None: self.full = full
      if no_merge is not None: self.no_merge = no_merge
      if filter is not None: self.filter = filter
      if filter_no_merge is not None: self.filter_no_merge = filter_no_merge
    elif increase:
      self.full += full or 0
      self.no_merge += no_merge or 0
      self.filter += filter or 0
      self.filter_no_merge += filter_no_merge or 0
    else:
      if full is not None: self.full |= full
      if no_merge is not None: self.no_merge |= no_merge
      if filter is not None: self.filter |= filter
      if filter_no_merge is not None: self.filter_no_merge |= filter_no_merge

    if result:
      self.update(
        full=self.full, no_merge=self.no_merge, filter=self.filter,
        filter_no_merge=self.filter_no_merge, override=override)


class Details(object):
  REVERTED_MATCHER = re.compile(
    r"This reverts commit ([a-f0-9]+)\.", re.MULTILINE)

  def __init__(self):
    self.info = dict()
    self.reverted = set()

  def __contains__(self, sha1):
    return sha1 in self.info

  def __getattr__(self, sha1):
    return self.info.get(sha1)

  def put(self, sha1, commit):
    self.info[sha1] = commit
    # detect the reverted commit
    if commit.title and commit.title.startswith('Revert "'):
      revisions = re.findall(Details.REVERTED_MATCHER, commit.info)
      if revisions:
        self.reverted.add(sha1)
        for rev in revisions:
          self.reverted.add(rev)

  def get(self, sha1):
    return self.info.get(sha1)

  def is_reverted(self, sha1):
    return sha1 in self.reverted


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

  def options(self, optparse, inherited=False):
    SubCommand.options(self, optparse, modules=globals())

    options = optparse.add_option_group('Remote options')
    options.add_option(
      '-r', '--remote',
      dest='remote', action='store',
      help='Set the remote server location')
    if not inherited:
      options.add_option(
        '-n', '--name',
        dest='name', action='store',
        help='Set the git repository name')

    options = optparse.get_option_group('--hook-dir') or \
      optparse.add_option_group('File options')
    options.add_option(
      '-o', '--output',
      dest='output', action='store', default='out',
      help='Set the output directory, default: %default')

    options = optparse.add_option_group('Format options')
    options.add_option(
      '--no-merge',
      dest='gen_no_merge', action='store_true',
      help='Generate the table without merge')

    options = optparse.add_option_group('Format options')
    options.add_option(
      '--gitiles',
      dest='gitiles', action='store_true',
      help='Enable gitiles links within the SHA-1')

  def execute(self, options, *args, **kws):
    SubCommand.execute(self, options, *args, **kws)

    if options.gitiles:
      RaiseExceptionIfOptionMissed(
        options.remote, "remote need set for gitiles")

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

    pattern = GitDiffSubcmd.get_patterns(options)  # pylint: disable=E1101
    GitDiffSubcmd.generate_report(
      args, project,
      options.name or name or '', options.output, options.output,
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
  def time_diff(tia, tib):
    out = ''

    hours, secs = divmod(tia - tib, 3600)
    if hours > 1:
      out += '%d hours ' % hours
    elif hours == 1:
      out += '%d hour ' % hours

    mins, secs = divmod(secs, 60)
    if mins > 1:
      out += '%d minutes ' % mins
    elif mins == 1:
      out += '%d minutes ' % mins

    if secs > 1:
      out += '%d seconds' % secs
    else:
      out += '%d second' % secs

    return out

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

    for item in ('%ai', '%ae', '%ce', '%s'):
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

    return CommitInfo(sha1, vals[0], vals[1], vals[2], vals[3], info)

  @staticmethod
  def get_commits_with_detail(project, sref, eref, details=None, *options):
    if details is None:
      details = Details()

    sha1s = GitDiffSubcmd.get_commits(project, sref, eref, *options)
    for sha1 in sha1s:
      if sha1 not in details:
        details.put(sha1, GitDiffSubcmd.get_commit_detail(project, sha1))

    return sha1s, details

  @staticmethod
  def get_commit_ci(project, details, sha1):
    if sha1 not in details:
      details.put(sha1, GitDiffSubcmd.get_commit_detail(project, sha1))

    return details.get(sha1)

  @staticmethod
  def update_table(
      accord, details, logs, id, title, remote=None,
      name=None, gitiles=True):
    tid = 'div_%d' % id
    hid = 'header_%d' % id

    with accord.div(clazz='card w-95', id='entire_%d' % id) as dcard:
      with dcard.div('%s ' % title, clazz='card-header', id=hid) as dhd:
        dhd.span(len(logs), clazz='badge badge-info',
          data_toggle='collapse', data_target='#%s' % tid,
          aria_expanded='true', aria_controls=tid)

      with dcard.div(
          clazz='collapse show', id=tid, aria_labelledby=hid,
          data_parent='#%s' % tid) as cont:
        with cont.div(clazz='card-body') as cbd:
          with cbd.table(clazz='table table-hover table-striped') as table:
            with table.tr() as tr:
              tr.th('SHA-1', scope='col')
              tr.th('Date', scope='col')
              tr.th('Author', scope='col')
              tr.th('Title', scope='col')

            for sha1 in logs:
              with table.tr() as tr:
                reverted = details.is_reverted(sha1)
                with tr.wtd() as td:
                  if name:
                    if reverted:
                      with td.wpre(_nowrap=True) as pre:
                        if gitiles or remote:
                          with pre.ws() as ws:
                            if gitiles:
                              ws.a(
                                sha1[:20], href='%s/#/q/%s' % (remote, sha1))
                              ws.a(
                                sha1[20:],
                                href='%s/plugins/gitiles/%s/+/%s^!' %
                                  (remote, name, sha1))
                            else:
                              ws.a(sha1, href='%s/#/q/%s' % (remote, sha1))
                        else:
                          pre.s(sha1)
                    else:
                      if gitiles or remote:
                        with td.wpre(_nowrap=True) as pre:
                          if gitiles:
                            pre.a(
                              sha1[:20], href='%s/#/q/%s' % (remote, sha1))
                            pre.a(
                              sha1[20:],
                              href='%s/plugins/gitiles/%s/+/%s^!' %
                                (remote, name, sha1))
                          else:
                            pre.a(sha1, href='%s/#/q/%s' % (remote, sha1))
                      else:
                        td.pre(sha1)
                  else:
                    if reverted:
                      with td.wpre(_nowrap=True) as pre:
                        pre.s(sha1)
                    else:
                      td.pre(sha1)

                if sha1 in details:
                  commit = details.get(sha1)
                else:
                  commit = CommitInfo(
                    sha1, '-', 'Unknown', 'Unknown', 'Unknown', '')

                date = re.split(' [+-]', commit.date)[0] # ignore timezone
                if reverted:
                  with tr.wtd() as td:
                    td.s(date)
                else:
                  tr.td(date)

                with tr.wtd() as td:
                  td.a(commit.author, href='mailto:%s' % commit.author)

                if commit.info:
                  if reverted:
                    with tr.wtd(data_toggle='tooltip', data_html='true',
                        title="%s" % tr.escape_str(commit.info)) as td:
                      td.s(commit.title)
                  else:
                    tr.td(
                      commit.title, data_toggle='tooltip', data_html='true',
                      title="%s" % tr.escape_str(commit.info))
                else:
                  if reverted:
                    with tr.wtd(clazz='align-middle') as td:
                      td.s(commit.title)
                  else:
                    tr.td(commit.title, clazz='align-middle')

  @staticmethod
  def generate_report(  # pylint: disable=R0915
      args, project, name, root, output, # pylint: disable=W0622
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
          results.put(name, [0, 0, 0, 0])

        return

    start = time.time()
    if not os.path.exists(output):
      os.makedirs(output)

    details = Details()
    GitDiffSubcmd._generate_html(
      brefs, erefs, args, project, name, root, output,
      os.path.join(output, 'index.html'),
      pattern, remote, gitiles, details, gen_no_merge, results, full=True)

    GitDiffSubcmd._generate_html(
      brefs, erefs, args, project, name, root, output,
      os.path.join(output, 'filter.html'),
      pattern, remote, gitiles, details, gen_no_merge, results)

    # try cleaning the directory and parents
    def file_num_in_dir(dname):
      if os.path.exists(dname):
        return len(filter(lambda d: d not in ['.', '..'], os.listdir(dname)))
      else:
        return -1

    dirname = output
    while len(dirname) > len(root) and file_num_in_dir(dirname) == 0:
      os.rmdir(dirname)
      dirname = os.path.dirname(dirname)

    if dirname != output:
      print(' > %s cleaned' % name)

    print('Totally cost: %s' % GitDiffSubcmd.time_diff(time.time(), start))

  @staticmethod
  def _generate_html(  # pylint: disable=R0915
      brefs, erefs, args, project, name, root, output, filename,  # pylint: disable=W0622
      pattern, remote=None, gitiles=True, details=None, gen_no_merge=False,
      results=None, full=False):

    res = Result(remote)
    with FormattedFile.open(filename, 'html') as outfile:
      with outfile.head() as head:
        head.meta(charset='utf-8')
        head.title('Logs of %s' % name)

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

        counts = Result()
        persists = dict()
        for ref in brefs:
          full_logs, _ = GitDiffSubcmd.get_commits_with_detail(
            project, ref, erefs, details)
          full_no_merged_logs = GitDiffSubcmd.get_commits(
            project, ref, erefs, '--no-merges')

          counts.update(
            full=len(full_logs), no_merge=len(full_no_merged_logs),
            increase=True)

          filtered_logs = list()
          filtered_no_merged_logs = list()
          if pattern:
            for li in full_logs:
              ci = GitDiffSubcmd.get_commit_ci(project, details, li)
              if pattern.match('e,email', ci.committer):
                filtered_logs.append(li)
                counts.update(filter=len(filtered_logs), increase=True)

                if li in full_no_merged_logs:
                  filtered_no_merged_logs.append(li)
                  counts.update(
                    filter_no_merge=len(filtered_no_merged_logs),
                    increase=True)

          persists[ref] = Persist(
            full_logs, full_no_merged_logs, filtered_logs,
            filtered_no_merged_logs)

        bd.p()
        with bd.div(clazz='card w-75') as bdiv:
          with bdiv.div(clazz='card-block') as block:
            with block.table(clazz='table') as btb:
              for title, refss in (
                  ('Start Refs', brefs), ('End Refs', [erefs])):
                with btb.tr() as tr:
                  tr.td(title, clazz='table-active', scope='row')

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
          index = 1
          # full log
          if full and counts.full:
            for ref in brefs:
              logs = persists[ref].full
              if logs:
                res.update(full=len(logs))
                GitDiffSubcmd.update_table(
                  acc, details, logs, index, 'Logs of %s..%s' % (ref, erefs),
                  remote, name, gitiles)
                index += 1

            # log with no merge
            if gen_no_merge and counts.no_merge:
              for ref in brefs:
                logs = persists[ref].no_merge
                if logs:
                  res.update(no_merge=len(logs))
                  GitDiffSubcmd.update_table(
                    acc, details, logs, index,
                    '%s..%s (No merges)' % (ref, erefs),
                    remote, name, gitiles)
                  index += 1

          if pattern and counts.filter:
            # full log with pattern
            for ref in brefs:
              logs = persists[ref].filter
              if logs:
                res.update(filter=len(logs))
                GitDiffSubcmd.update_table(
                  acc, details, logs, index,
                  'Filtered logs of %s..%s' % (ref, erefs),
                  remote, name, gitiles)
                index += 1

            # log with pattern and no merge
            if gen_no_merge and counts.filter_no_merge:
              for ref in brefs:
                logs = persists[ref].filtered_no_merged_logs
                if logs:
                  res.update(filter_no_merge=len(logs))
                  GitDiffSubcmd.update_table(
                    acc, details, logs, index,
                    'Filtered logs of %s..%s (No merges)' % (ref, erefs),
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

    # remove the generated file if all counts are zero
    if not res:
      os.unlink(filename)

    if results is not None:
      orig = results.get(name, res)
      orig.update(result=res, override=False)
      results[name] = orig
