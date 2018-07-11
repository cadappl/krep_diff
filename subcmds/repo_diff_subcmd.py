
import os

from synchronize import synchronized
from git_diff_subcmd import GitDiffSubcmd
from krep_subcmds.repo_subcmd import RepoSubcmd
from krep_subcmds.repo_mirror_subcmd import RepoMirrorSubcmd
from topics import FormattedFile, SubCommandWithThread


class RepoDiffSubcmd(GitDiffSubcmd, SubCommandWithThread):
  COMMAND = 'repo-diff'

  INDEX_HTML = 'index.html'

  help_summary = 'Generate the diff report for a repo project'
  help_usage = """\
%prog [options] manifest.xml [diff-manifest.xml] ...

Handle the git-repo project git commits diff and generate the reports in
purposed formats."""

  def options(self, optparse):
    GitDiffSubcmd.options(self, optparse)

    options = optparse.add_option_group('Repo-tool options')
    options.add_option(
      '--mirror',
      dest='mirror', action='store_true',
      help='Set to work with a git-repo mirror project')

  def execute(self, options, *args, **kws):
    pattern = RepoDiffSubcmd.get_patterns(options)  # pylint: disable=E1101
    if not os.path.exists(options.output):
      os.makedirs(options.output)

    def make_projects(projects):
      rets = dict()

      for project in projects:
        rets[project.uri] = project

      return rets

    if options.mirror:
      manifestf = RepoMirrorSubcmd.fetch_projects_in_manifest
    else:
      manifestf = RepoSubcmd.fetch_projects_in_manifest

    if len(args) > 1:
      first = make_projects(manifestf(options, args[0]))
      second = make_projects(manifestf(options, args[1]))
    else:
      first = dict()
      if len(args) > 0:
        second = make_projects(manifestf(options, args[0]))
      else:
        second = make_projects(manifestf(options))

    class Results:
      def __init__(self):
        self.changes = dict()

      @synchronized
      def put(self, name, value):
        self.changes[name] = value

      def get(self, name=None):
        if name:
          return self.changes[name]
        else:
          return self.changes

    results = Results()

    def generate_report(
        project, remote, options, origins, references, pattern, results):
      print("Generating for %s ..." % origins[project])

      argp = list()
      if project in references:
        argp.append(references[project].revision)

      argp.append(origins[project].revision)
      GitDiffSubcmd.generate_report(
        argp, origins[project],
        project, options.output,
        os.path.join(options.output, project), options.format,
        pattern, remote, options.gitiles, options.gen_no_merge, results)

    self.run_with_thread(
      options.job, second, generate_report, options.remote, options,
      second, first, pattern, results)

    new_projects = list()
    modified_projects = list()
    removed_projects = list()
    noupdate_projects = list()

    projects = results.get()
    for project in projects:
      if project in first:
        if results.get(project) == 0:
          noupdate_projects.append(project)
        else:
          modified_projects.append(project)
      else:
        new_projects.append(project)

    for project in first:
      if project not in second:
        removed_projects.append(project)

    with FormattedFile.open(
        os.path.join(options.output, 'index.html'), 'html') as outfile:
      with outfile.head() as head:
        head.meta(charset='utf-8')
        head.title('Git-repo Report for manifest difference')

        head.comment(' Boot strap core CSS ')
        head.link(
          href=GitDiffSubcmd.deploy(
            'asserts/css/bootstrap.min.css', options.output, options.output),
          rel='stylesheet')
        head.link(
          href=GitDiffSubcmd.deploy(
            'asserts/css/krep-diff.css', options.output, options.output),
          rel='stylesheet')

      with outfile.body() as bd:
        with bd.nav(clazz="nav navbar-dark bg-dark") as nav:
          with nav.wbutton(clazz="navbar-toggler", type="button") as bnav:
            bnav.span('', clazz="navbar-toggler-icon")

        bd.p()
        with bd.div(id='accordion') as acc:
          index = 1
          if new_projects:
            with acc.div(clazz='card w-75', id='entire_%d' % index) as newp:
              name = 'new_project'
              hid = 'head_%d' % index
              with newp.div(clazz='card-header', id=hid) as dhd:
                with dhd.wh5(clazz='mb-0') as h5:
                  with h5.wbutton(
                      'New Projects',
                      clazz='btn btn-link', data_toggle='collapse',
                      data_target='#%s' % name, aria_expanded='true',
                      aria_controls=name) as wb:
                    wb.span(len(new_projects), clazz='badge badge-info')

              with newp.div(
                  clazz='collapse show', id=name, aria_labelledby=hid,
                  data_parent='#%s' % name) as cont:
                with cont.div(clazz='card-body') as cbd:
                  with cbd.table(clazz='table table-hover table-striped') \
                      as table:
                    for pname in sorted(new_projects):
                      project = second[pname]
                      with table.tr() as tr:
                        with tr.wtd() as td:
                          td.a(project.uri, href='%s/index.html' % project.uri)
                          td.span(
                            results.get(project.uri), clazz='badge badge-info')

          if modified_projects:
            index += 1
            with acc.div(clazz='card w-75', id='entire_%d' % index) as modp:
              name = 'mod_project'
              hid = 'head_%d' % index
              with modp.div(clazz='card-header', id=hid) as dhd:
                with dhd.wh5(clazz='mb-0') as h5:
                  with h5.wbutton(
                      'Modified Projects',
                      clazz='btn btn-link', data_toggle='collapse',
                      data_target='#%s' % name, aria_expanded='true',
                      aria_controls=name) as wb:
                    wb.span(len(modified_projects), clazz='badge badge-info')

              with modp.div(
                  clazz='collapse show', id=name, aria_labelledby=hid,
                  data_parent='#%s' % name) as cont:
                with cont.div(clazz='card-body') as cbd:
                  with cbd.table(clazz='table table-hover table-striped') \
                      as table:
                    for pname in sorted(modified_projects):
                      project = second[pname]
                      with table.tr() as tr:
                        with tr.wtd() as td:
                          td.a(project.uri, href='%s/index.html' % project.uri)
                          td.span(
                            results.get(project.uri), clazz='badge badge-info')

          if noupdate_projects:
            index += 1
            with acc.div(clazz='card w-75', id='entire_%d' % index) as noupdt:
              name = 'noupdt_project'
              hid = 'head_%d' % index
              with noupdt.div(clazz='card-header', id=hid) as dhd:
                with dhd.wh5(clazz='mb-0') as h5:
                  with h5.wbutton(
                      'Non-updated Projects',
                      clazz='btn btn-link', data_toggle='collapse',
                      data_target='#%s' % name, aria_expanded='true',
                      aria_controls=name) as wb:
                    wb.span(len(noupdate_projects), clazz='badge badge-info')

              with noupdt.div(
                  clazz='collapse show', id=name, aria_labelledby=hid,
                  data_parent='#%s' % name) as cont:
                with cont.div(clazz='card-body') as cbd:
                  with cbd.table(clazz='table table-hover table-striped') \
                      as table:
                    for pname in sorted(noupdate_projects):
                      with table.tr() as tr:
                        with tr.wtd() as td:
                          td.a(pname)

          if removed_projects:
            index += 1
            with acc.div(clazz='card w-75', id='entire_%d' % index) as remp:
              name = 'rm_project'
              hid = 'head_%d' % index
              with remp.div(clazz='card-header', id=hid) as dhd:
                with dhd.wh5(clazz='mb-0') as h5:
                  with h5.wbutton(
                      'Removed Projects',
                      clazz='btn btn-link', data_toggle='collapse',
                      data_target='#%s' % name, aria_expanded='true',
                      aria_controls=name) as wb:
                    wb.span(len(removed_projects), clazz='badge badge-info')

              with remp.div(
                  clazz='collapse show', id=name, aria_labelledby=hid,
                  data_parent='#%s' % name) as cont:
                with cont.div(clazz='card-body') as cbd:
                  with cbd.table(clazz='table table-hover table-striped') \
                      as table:
                    for pname in sorted(removed_projects):
                      with table.tr() as tr:
                        with tr.wtd() as td:
                          td.a(pname)

        bd.script(
          "window.jQuery || document.write('<script src=\"%s\">"
          "<\/script>')" % GitDiffSubcmd.deploy(
            'asserts/js/vendor/jquery-slim.min.js',
            options.output, options.output),
          _escape=False)
        # write an empty string to keep <script></script> to make js working
        bd.script(
          '',
          src=GitDiffSubcmd.deploy(
            'asserts/js/bootstrap.min.js', options.output, options.output))

    return True

