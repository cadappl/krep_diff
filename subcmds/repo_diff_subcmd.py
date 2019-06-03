
import os
import time

from synchronize import synchronized
from git_diff_subcmd import GitDiffSubcmd
from krep_subcmds.repo_subcmd import RepoSubcmd
from krep_subcmds.repo_mirror_subcmd import RepoMirrorSubcmd
from topics import FormattedFile, RaiseExceptionIfOptionMissed, \
  SubCommandWithThread


class RepoDiffSubcmd(GitDiffSubcmd, SubCommandWithThread):
  COMMAND = 'repo-diff'

  INDEX_HTML = 'index.html'

  help_summary = 'Generate the diff report for a repo project'
  help_usage = """\
%prog [options] manifest.xml [diff-manifest.xml] ...

Handle the git-repo project git commits diff and generate the reports in
purposed formats."""

  def options(self, optparse):
    GitDiffSubcmd.options(self, optparse, inherited=True)

    options = optparse.add_option_group('Repo-tool options')
    options.add_option(
      '--mirror',
      dest='mirror', action='store_true',
      help='Set to work with a git-repo mirror project')

  def execute(self, options, *args, **kws):
    if options.gitiles:
      RaiseExceptionIfOptionMissed(
        options.remote, "remote need set for gitiles")

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

    results = dict()

    def generate_report(
        project, remote, options, origins, references, pattern, results):
      print("Generating for %s ..." % origins[project])

      argp = list()
      if project in references:
        argp.append(references[project].revision)

      argp.append(origins[project].revision)

      start = time.time()
      GitDiffSubcmd.generate_report(
        argp, origins[project],
        project, options.output,
        os.path.join(options.output, project),
        pattern, remote, options.gitiles, options.gen_no_merge, results,
        quiet=True)

      print('Handle %s with %s' % (
        origins[project], GitDiffSubcmd.time_diff(time.time(), start)))

    self.run_with_thread(
      options.job, second, generate_report, options.remote, options,
      second, first, pattern, results)

    new_projects = list()
    modified_projects = list()
    removed_projects = list()
    noupdate_projects = list()

    for project, result in results.items():
      if project in first:
        if result.full or result.filter:
          modified_projects.append(project)
        else:
          noupdate_projects.append(project)
      else:
        new_projects.append(project)

    for project in first:
      if project not in second:
        removed_projects.append(project)

    with FormattedFile.open(
        os.path.join(options.output, 'index.html')) as outfile:
      with outfile.head() as head:
        head.meta(charset='utf-8')
        head.title('Log Report for Manifest Difference')

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
          index = 0
          for pinfo, title in (
              (new_projects, 'New Projects'),
              (modified_projects, 'Modified Projects')):
            if not pinfo:
              continue

            index += 1
            with acc.div(clazz='card w-75', id='entire_%d' % index) as pdiv:
              name = 'project_%d' % index
              hid = 'head_%d' % index
              with pdiv.div(clazz='card-header', id=hid) as dhd:
                with dhd.wh5(clazz='mb-0') as h5:
                  with h5.wbutton(
                      title,
                      clazz='btn btn-link', data_toggle='collapse',
                      data_target='#%s' % name, aria_expanded='true',
                      aria_controls=name) as wb:
                    wb.span(len(pinfo), clazz='badge badge-info')

              with pdiv.div(
                  clazz='collapse show', id=name, aria_labelledby=hid,
                  data_parent='#%s' % name) as cont:
                with cont.div(clazz='card-body') as cbd:
                  with cbd.table(clazz='table table-hover table-striped') \
                      as table:
                    for pname in sorted(pinfo):
                      project = second[pname]
                      with table.tr() as tr:
                        with tr.wtd() as td:
                          result = results.get(pname)
                          if options.gitiles and result and result.remote:
                            td.a(
                              pname, href='%s/plugins/gitiles/%s' % (
                                result.remote, pname))
                          else:
                            td.span(pname)

                          for item, badge, page in (
                              ('full', 'primary', 'index.html'),
                              ('filter', 'secondary', 'filter.html')):
                            val = getattr(result, item)
                            if val:
                              td.a(
                                val, href='%s/%s' % (pname, page),
                                clazz='badge badge-%s' % badge)

          if noupdate_projects:
            index += 1
            with acc.div(clazz='card w-75', id='entire_%d' % index) as pdiv:
              name = 'noupdt_project'
              hid = 'head_%d' % index
              with pdiv.div(clazz='card-header', id=hid) as dhd:
                with dhd.wh5(clazz='mb-0') as h5:
                  with h5.wbutton(
                      'Non-updated Projects',
                      clazz='btn btn-link', data_toggle='collapse',
                      data_target='#%s' % name, aria_expanded='true',
                      aria_controls=name) as wb:
                    wb.span(len(noupdate_projects), clazz='badge badge-info')

              with pdiv.div(
                  clazz='collapse show', id=name, aria_labelledby=hid,
                  data_parent='#%s' % name) as cont:
                with cont.div(clazz='card-body') as cbd:
                  with cbd.table(clazz='table table-hover table-striped') \
                      as table:
                    for pname in sorted(noupdate_projects):
                      with table.tr() as tr:
                        with tr.wtd() as td:
                          result = results.get(pname)
                          if options.gitiles and result and result.remote:
                            td.a(
                              pname, href='%s/plugins/gitiles/%s' % (
                                result.remote, pname))
                          else:
                            td.span(pname)

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
                          result = results.get(pname)
                          if options.gitiles and result and result.remote:
                            td.a(
                              pname, href='%s/plugins/gitiles/%s' % (
                                result.remote, pname))
                          else:
                            td.span(pname)

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

